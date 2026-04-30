import logging

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from .serializers import DemoLeadSerializer
from .tasks import notify_demo_lead_task

logger = logging.getLogger(__name__)


class DemoLeadAnonThrottle(AnonRateThrottle):
    """5 заявок с одного IP в минуту — реальный лид столько никогда не оставит,
    но защищает endpoint от ботов / лавины POST'ов в Telegram-канал.

    Rate берётся из settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['landing-demo'].
    """
    scope = "landing-demo"


class DemoLeadView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [DemoLeadAnonThrottle]

    def post(self, request):
        serializer = DemoLeadSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        # Honeypot: бот заполнил скрытое поле «website» — отбрасываем тихо,
        # чтобы он не понял что попался и не начал подбирать другие приёмы.
        if serializer.context.get("_honeypot_triggered"):
            logger.info(
                "landing demo: honeypot triggered from %s",
                request.META.get("REMOTE_ADDR", "?"),
            )
            return Response({"ok": True}, status=status.HTTP_201_CREATED)

        lead = serializer.save()
        notify_demo_lead_task.delay(str(lead.id))
        return Response({"ok": True}, status=status.HTTP_201_CREATED)
