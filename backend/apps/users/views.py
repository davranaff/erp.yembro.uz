from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework import generics, viewsets
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import AuditLog
from apps.audit.services.writer import audit_log

from .models import UserFavoritePage
from .serializers import (
    ChangePasswordSerializer,
    MeSerializer,
    MeUpdateSerializer,
    UserFavoritePageSerializer,
)


class MeView(generics.RetrieveUpdateAPIView):
    """
    GET   /api/users/me/  — текущий пользователь + memberships + module_permissions.
    PATCH /api/users/me/  — частичное обновление (full_name, phone).

    Не требует X-Organization-Code (пользователь может ещё не выбрать организацию).
    """

    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch", "head", "options"]

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return MeUpdateSerializer
        return MeSerializer

    def get_object(self):
        return self.request.user

    def perform_update(self, serializer):
        instance = serializer.save()
        audit_log(
            organization=getattr(self.request, "organization", None),
            actor=self.request.user,
            action=AuditLog.Action.UPDATE,
            entity=instance,
            action_verb=f"updated profile {instance.email}",
        )

    def update(self, request, *args, **kwargs):
        # После сохранения возвращаем полный MeSerializer (с memberships).
        super().update(request, *args, **kwargs)
        return Response(MeSerializer(self.get_object()).data)


class ChangePasswordView(APIView):
    """POST /api/users/me/change-password/ — смена пароля."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        old = serializer.validated_data["old_password"]
        new = serializer.validated_data["new_password"]

        user = request.user
        if not user.check_password(old):
            raise DRFValidationError({"old_password": ["Неверный текущий пароль."]})
        try:
            validate_password(new, user=user)
        except DjangoValidationError as exc:
            raise DRFValidationError({"new_password": list(exc.messages)})
        if user.check_password(new):
            raise DRFValidationError(
                {"new_password": ["Новый пароль должен отличаться от текущего."]}
            )

        user.set_password(new)
        user.save(update_fields=["password"])

        audit_log(
            organization=getattr(request, "organization", None),
            actor=user,
            action=AuditLog.Action.UPDATE,
            entity=user,
            action_verb=f"changed password for {user.email}",
        )
        return Response({"ok": True})


class UserFavoritePageViewSet(viewsets.ModelViewSet):
    """
    /api/users/me/favorites/ — закреплённые страницы текущего пользователя.

    Не требует X-Organization-Code: список глобальный для пользователя
    (зашёл в любую компанию — закладки те же).
    """

    serializer_class = UserFavoritePageSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None  # список короткий, пагинация не нужна

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return UserFavoritePage.objects.none()
        return UserFavoritePage.objects.filter(user=user)

    def perform_create(self, serializer):
        try:
            serializer.save(user=self.request.user)
        except IntegrityError:
            # unique_together (user, href) — страница уже закреплена
            raise DRFValidationError(
                {"href": "Эта страница уже закреплена."}
            )
