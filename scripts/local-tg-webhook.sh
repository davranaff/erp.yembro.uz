#!/usr/bin/env bash
# Поднимает HTTPS-tunnel над локальным API (порт 30000) и регистрирует
# webhook в Telegram через `tg_set_webhook`.
#
# Использование:
#   ./scripts/local-tg-webhook.sh           # запустить tunnel + register
#   ./scripts/local-tg-webhook.sh stop      # остановить tunnel и отвязать webhook
#
# Tunnel:
#   1. ngrok (приоритет — стабильный DNS у Telegram). Требует ngrok config
#      add-authtoken <YOUR>; см. https://dashboard.ngrok.com/get-started/setup
#   2. cloudflared quick-tunnel — fallback если ngrok недоступен. Иногда
#      не резолвится из сети Telegram (Bad Request: Failed to resolve host).
#
# Tunnel держится пока процесс работает. При Ctrl+C в `start` — остаётся
# в фоне, используй `stop`.

set -euo pipefail

API_CONTAINER="yembrotech-api-1"
LOCAL_PORT=30000
LOG_FILE="/tmp/local-tg-tunnel.log"
PID_FILE="/tmp/local-tg-tunnel.pid"

# ── stop ────────────────────────────────────────────────────────────────
case "${1:-start}" in
  stop)
    if [ -f "$PID_FILE" ]; then
      PID=$(cat "$PID_FILE")
      if kill -0 "$PID" 2>/dev/null; then
        echo "→ Останавливаю tunnel PID=$PID..."
        kill "$PID" || true
        pkill -P "$PID" 2>/dev/null || true
      fi
      rm -f "$PID_FILE"
    fi
    pkill -x ngrok 2>/dev/null || true
    pkill -x cloudflared 2>/dev/null || true
    echo "→ Снимаю webhook в Telegram..."
    docker exec "$API_CONTAINER" python -c "
import os, urllib.request
token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
if token:
    req = urllib.request.urlopen(
        f'https://api.telegram.org/bot{token}/deleteWebhook'
    )
    print(req.read().decode())
else:
    print('TELEGRAM_BOT_TOKEN пуст — webhook не снимаю.')
" || true
    rm -f "$LOG_FILE"
    echo "✅ Done."
    exit 0
    ;;
esac

# ── sanity ──────────────────────────────────────────────────────────────
if ! docker ps --format '{{.Names}}' | grep -q "^${API_CONTAINER}$"; then
  echo "❌ Контейнер $API_CONTAINER не запущен. Подними docker compose."
  exit 1
fi
if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "⚠ Tunnel уже запущен PID=$(cat "$PID_FILE"). Чтобы перезапустить:"
  echo "   $0 stop && $0"
  exit 1
fi

: > "$LOG_FILE"
URL=""
TUNNEL_KIND=""

# ── ngrok (primary) ────────────────────────────────────────────────────
if command -v ngrok >/dev/null 2>&1; then
  if ngrok config check 2>&1 | grep -q "Valid configuration"; then
    echo "→ Запускаю ngrok HTTP tunnel на ${LOCAL_PORT}..."
    nohup ngrok http --log=stdout --log-format=json "$LOCAL_PORT" \
      > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    TUNNEL_KIND="ngrok"

    echo "→ Жду публичный URL от ngrok..."
    for i in $(seq 1 20); do
      sleep 1
      URL=$(grep -oE '"url":"https://[a-z0-9-]+\.ngrok[^"]*"' "$LOG_FILE" \
        | head -1 \
        | sed 's/"url":"//; s/"$//' || true)
      [ -n "$URL" ] && break
    done
  else
    echo "⚠ ngrok без auth-token. Регистрируйся на https://dashboard.ngrok.com"
    echo "  и выполни: ngrok config add-authtoken <TOKEN>"
  fi
fi

# ── cloudflared (fallback) ──────────────────────────────────────────────
if [ -z "$URL" ] && command -v cloudflared >/dev/null 2>&1; then
  echo "→ Fallback: cloudflared quick-tunnel..."
  : > "$LOG_FILE"
  nohup cloudflared tunnel --no-autoupdate --url "http://localhost:${LOCAL_PORT}" \
    > "$LOG_FILE" 2>&1 &
  echo $! > "$PID_FILE"
  TUNNEL_KIND="cloudflared"

  for i in $(seq 1 30); do
    sleep 1
    URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG_FILE" | head -1 || true)
    [ -n "$URL" ] && break
  done
fi

if [ -z "$URL" ]; then
  echo "❌ Не дождался публичного URL за разумное время."
  echo "   Лог: $LOG_FILE"
  [ -f "$PID_FILE" ] && kill "$(cat "$PID_FILE")" 2>/dev/null || true
  rm -f "$PID_FILE"
  tail -30 "$LOG_FILE"
  exit 1
fi

echo "✅ Tunnel ($TUNNEL_KIND): $URL"
WEBHOOK_URL="${URL}/api/tg/webhook/"

# ── register webhook with retry ─────────────────────────────────────────
echo "→ Регистрирую webhook: $WEBHOOK_URL"
ok=0
for attempt in 1 2 3 4 5 6; do
  if docker exec "$API_CONTAINER" python manage.py tg_set_webhook \
       --url "$WEBHOOK_URL" 2>&1 | tee /tmp/local-tg-webhook-result.txt \
       | grep -q "setWebhook → ok"; then
    ok=1
    break
  fi
  delay=$((attempt * 5))
  echo "  попытка $attempt не прошла, жду ${delay}с..."
  sleep "$delay"
done

if [ $ok -ne 1 ]; then
  echo "❌ setWebhook не прошёл после 6 попыток."
  tail -3 /tmp/local-tg-webhook-result.txt
  echo
  echo "Tunnel остался поднят: $URL"
  echo "Попробуй вручную позже:"
  echo "   docker exec $API_CONTAINER python manage.py tg_set_webhook --url $WEBHOOK_URL"
  exit 1
fi

echo
echo "🎯 Локальный TG webhook готов."
echo "   Tunnel     : $TUNNEL_KIND"
echo "   Public URL : $URL"
echo "   Webhook    : $WEBHOOK_URL"
echo "   API        : http://localhost:${LOCAL_PORT}"
echo "   Лог tunnel : $LOG_FILE"
echo "   PID        : $(cat "$PID_FILE")"
echo
echo "Чтобы остановить и снять webhook: $0 stop"
