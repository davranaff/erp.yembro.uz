"""
Signals для синхронизации Telegram-команд с RBAC.

Когда админ выдаёт/отзывает доступ юзеру (UserModuleAccessOverride или
UserRole), его персональный список / команд в Telegram-popup'е должен
обновиться — иначе он будет видеть команды на которые у него больше
нет прав, или НЕ видеть новые. Без этого после смены прав надо просить
юзера переsubmit /link, что неудобно.

Подход: post_save / post_delete на RBAC-моделях → находим все TgLink
этого membership.user → перезаписываем setMyCommands per chat_id.

Идемпотентно: если ничего не изменилось, Telegram примет тот же список
без побочных эффектов. Failures логируются но не падают (TG API down ≠
DB не должна откатываться).
"""
from __future__ import annotations

import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver


logger = logging.getLogger(__name__)


def _refresh_commands_for_membership(membership_id) -> None:
    """Переписать setMyCommands для всех TgLink юзера из этого membership.

    Membership → user → TgLink(s) (может быть в разных org). Для каждого
    линка считаем свежий RBAC scope и шлём setMyCommands per-chat.
    Запускается как fire-and-forget — если TG API недоступен, log + skip.
    """
    from apps.organizations.models import OrganizationMembership

    from .bot import set_my_commands
    from .models import TgLink
    from .services.menu_scope import (
        commands_for_user,
        user_module_levels,
    )

    try:
        membership = OrganizationMembership.objects.select_related(
            "user", "organization",
        ).get(pk=membership_id)
    except OrganizationMembership.DoesNotExist:
        return

    user_id = membership.user_id
    if not user_id:
        return

    # Все admin-линки этого юзера (counterparty не трогаем — у них свой
    # фиксированный набор команд из commands_for_counterparty).
    links = list(
        TgLink.objects
        .filter(user_id=user_id, is_active=True)
        .select_related("organization", "active_organization")
    )
    for link in links:
        try:
            levels = user_module_levels(link)
            cmds = commands_for_user(levels, notify_enabled=link.notify_enabled)
            set_my_commands(cmds, chat_id=link.chat_id)
            logger.info(
                "rbac-sync: setMyCommands updated for chat=%s user=%s commands=%d",
                link.chat_id, user_id, len(cmds),
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "rbac-sync: failed to refresh chat=%s", link.chat_id,
            )


@receiver(post_save, sender="rbac.UserModuleAccessOverride")
@receiver(post_delete, sender="rbac.UserModuleAccessOverride")
def _on_override_change(sender, instance, **kwargs):
    """UserModuleAccessOverride изменился → перепиши команды юзера."""
    _refresh_commands_for_membership(instance.membership_id)


@receiver(post_save, sender="rbac.UserRole")
@receiver(post_delete, sender="rbac.UserRole")
def _on_user_role_change(sender, instance, **kwargs):
    """UserRole изменился → перепиши команды юзера.

    Cascade: изменение RolePermission само по себе не триггерит этот
    сигнал, но в большинстве случаев права меняют через UserRole
    («снять/назначить роль»). Если меняется RolePermission напрямую,
    нужен отдельный bulk-refresh — это редкий админ-флоу, можно
    дождаться следующего /menu юзера.
    """
    _refresh_commands_for_membership(instance.membership_id)
