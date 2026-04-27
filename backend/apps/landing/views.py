from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import DemoLeadSerializer
from .tasks import notify_demo_lead_task


class DemoLeadView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = DemoLeadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lead = serializer.save()
        notify_demo_lead_task.delay(str(lead.id))
        return Response({"ok": True}, status=status.HTTP_201_CREATED)
