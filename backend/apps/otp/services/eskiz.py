from __future__ import annotations

import logging
from dataclasses import dataclass

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

_TOKEN_CACHE_KEY = "otp:eskiz:token"
# Токен Eskiz живёт ~30 дней. Кешируем чуть меньше, чтобы пере-логиниться
# заранее, а не словить 401 в проде. На реальном 401 всё равно делаем
# force-refresh, так что это просто страховка.
_TOKEN_CACHE_TTL = 60 * 60 * 24 * 25


class EskizError(RuntimeError):
    """Базовая ошибка Eskiz-клиента."""


class EskizConfigError(EskizError):
    """ESKIZ_EMAIL / ESKIZ_PASSWORD не заданы в окружении."""


class EskizAuthError(EskizError):
    """Не удалось получить токен (неверные креды, заблокирован аккаунт)."""


class EskizSendError(EskizError):
    """Eskiz отказался отправлять SMS — баланс, шаблон, sender и т.п."""


@dataclass(frozen=True)
class EskizClient:
    email: str
    password: str
    sender: str
    base_url: str = "https://notify.eskiz.uz"
    timeout: float = 10.0
    callback_url: str = ""

    # ── public ──────────────────────────────────────────────────────────────

    def send_sms(self, phone: str, message: str) -> str:
        """
        Отправляет SMS, возвращает id сообщения от Eskiz.

        При 401 один раз пере-логинимся и повторяем отправку — это
        стандартный кейс «токен внезапно отозван».
        """
        resp = self._authed_request("POST", "/api/message/sms/send", files={
            "mobile_phone": (None, phone),
            "message": (None, message),
            "from": (None, self.sender),
            "callback_url": (None, self.callback_url),
        })

        if resp.status_code != 200:
            raise EskizSendError(
                f"Eskiz send failed: HTTP {resp.status_code} — {resp.text[:300]}"
            )

        data = _safe_json(resp)
        # Eskiz возвращает либо {"id": "..."}, либо
        # {"status": "waiting", "message": "...", "id": "..."} — id есть всегда
        # при успехе.
        message_id = data.get("id") or data.get("data", {}).get("id")
        if not message_id:
            raise EskizSendError(f"Eskiz: id отсутствует в ответе — {data}")
        return str(message_id)

    def get_balance(self) -> int:
        """
        Текущий баланс аккаунта в SMS-кредитах (== UZS, цена 1 SMS ≈ 300 UZS).
        Используется celery-таской мониторинга.
        """
        resp = self._authed_request("GET", "/api/user/get-limit")
        if resp.status_code != 200:
            raise EskizError(
                f"Eskiz balance failed: HTTP {resp.status_code} — {resp.text[:300]}"
            )
        data = _safe_json(resp)
        balance = data.get("data", {}).get("balance")
        if balance is None:
            raise EskizError(f"Eskiz balance: balance отсутствует — {data}")
        return int(balance)

    def get_status(self, message_id: str) -> dict:
        """
        Статус доставки SMS по его id. Используется fallback-поллером, когда
        webhook не пришёл за разумное время.

        Возвращает dict с ключами как минимум: `status` ('DELIVERED'/'FAILED'/...),
        `delivery_sm_at`, `price`, `to`, `message`.
        """
        resp = self._authed_request(
            "GET", f"/api/message/sms/status_by_id/{message_id}",
        )
        if resp.status_code != 200:
            raise EskizError(
                f"Eskiz status failed: HTTP {resp.status_code} — {resp.text[:300]}"
            )
        data = _safe_json(resp)
        # Реальные данные сидят в `data.data` (Eskiz двойную обёртку любит).
        return data.get("data", {}) or {}

    # ── internal ────────────────────────────────────────────────────────────

    def _authed_request(
        self, method: str, path: str, *, files=None, data=None,
    ) -> requests.Response:
        """
        Универсальный обёртка-вызов с auto-relogin при 401.
        """
        token = self._get_token()
        resp = self._raw_request(method, path, token=token, files=files, data=data)
        # 401 = протух токен, перелогинимся. 403 — это аккаунт реально
        # заблокирован/нет прав, перелогин не поможет, не дёргаем зря.
        if resp.status_code == 401:
            logger.info("eskiz: token rejected (401), re-login")
            token = self._get_token(force_refresh=True)
            resp = self._raw_request(method, path, token=token, files=files, data=data)
        return resp

    def _raw_request(
        self, method: str, path: str, *, token: str, files=None, data=None,
    ) -> requests.Response:
        try:
            return requests.request(
                method,
                f"{self.base_url}{path}",
                headers={"Authorization": f"Bearer {token}"},
                files=files,
                data=data,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise EskizError(f"Eskiz {method} {path}: сетевая ошибка — {exc}") from exc

    def _get_token(self, *, force_refresh: bool = False) -> str:
        if not force_refresh:
            cached = cache.get(_TOKEN_CACHE_KEY)
            if cached:
                return cached
        token = self._login()
        cache.set(_TOKEN_CACHE_KEY, token, _TOKEN_CACHE_TTL)
        return token

    def _login(self) -> str:
        try:
            resp = requests.post(
                f"{self.base_url}/api/auth/login",
                data={"email": self.email, "password": self.password},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise EskizAuthError(f"Eskiz login: сетевая ошибка — {exc}") from exc

        if resp.status_code != 200:
            raise EskizAuthError(
                f"Eskiz login: HTTP {resp.status_code} — {resp.text[:300]}"
            )

        data = _safe_json(resp)
        token = data.get("data", {}).get("token") or data.get("token")
        if not token:
            raise EskizAuthError(f"Eskiz login: token отсутствует — {data}")
        return token

def get_eskiz_client() -> EskizClient:
    """Собирает клиент из настроек. Не кеширует — клиент сам легковесный."""
    email = getattr(settings, "ESKIZ_EMAIL", "") or ""
    password = getattr(settings, "ESKIZ_PASSWORD", "") or ""
    if not email or not password:
        raise EskizConfigError(
            "ESKIZ_EMAIL/ESKIZ_PASSWORD не заданы. Укажите в .env "
            "или включите OTP_DEV_PRINT=true для локальной отладки."
        )
    return EskizClient(
        email=email,
        password=password,
        sender=getattr(settings, "ESKIZ_FROM", "4546") or "4546",
        base_url=getattr(settings, "ESKIZ_BASE_URL", "https://notify.eskiz.uz"),
        timeout=getattr(settings, "ESKIZ_TIMEOUT_SECONDS", 10.0),
        callback_url=getattr(settings, "ESKIZ_CALLBACK_URL", "") or "",
    )


def _safe_json(resp: requests.Response) -> dict:
    try:
        out = resp.json()
    except ValueError:
        return {}
    return out if isinstance(out, dict) else {}
