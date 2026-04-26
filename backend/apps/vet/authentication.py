"""
Кастомный аутентификатор для public-эндпоинтов вет.аптеки.

`SellerTokenAuthentication` — Bearer <seller-token> в заголовке.
Токен ищется в `SellerDeviceToken`. При успехе:
  - request.user = token.user
  - request.organization = token.organization (для совместимости с view'ами,
    которые ожидают `request.organization`).
  - last_used_at обновляется.
"""
from __future__ import annotations

from django.utils import timezone
from rest_framework import authentication, exceptions

from .models import SellerDeviceToken


class SellerTokenAuthentication(authentication.BaseAuthentication):
    """
    Authorization: Bearer <seller_token>

    Возвращает (User, SellerDeviceToken) или None если заголовок не содержит Bearer.
    Бросает AuthenticationFailed если токен невалиден/отозван.
    """

    keyword = "Bearer"

    def authenticate(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header:
            return None
        parts = auth_header.split()
        if len(parts) != 2 or parts[0] != self.keyword:
            return None

        raw = parts[1]
        try:
            tok = SellerDeviceToken.objects.select_related(
                "user", "organization"
            ).get(token=raw)
        except SellerDeviceToken.DoesNotExist:
            raise exceptions.AuthenticationFailed("Invalid seller token")

        if not tok.is_active or tok.revoked_at is not None:
            raise exceptions.AuthenticationFailed("Seller token revoked")

        # Обновляем last_used_at без сохранения в auth-flow (без транзакции)
        tok.last_used_at = timezone.now()
        tok.save(update_fields=["last_used_at"])

        # Прикрепляем organization к request — view ожидают request.organization
        request.organization = tok.organization

        return (tok.user, tok)

    def authenticate_header(self, request):
        return self.keyword
