"""
/org — переключатель активной организации (multi-org owner).

Сохраняет выбор в `TgLink.active_organization`. Все handlers дёргают
`ctx.org()` который возвращает active_organization или fallback на
link.organization.
"""
from __future__ import annotations

from ..bot import send_message
from ..dispatcher import HandlerCtx, command, on_callback
from ..keyboards import kb


@command("/org", help="Переключить активную организацию", category="org")
def handle_org_cmd(ctx: HandlerCtx) -> None:
    from apps.organizations.models import Organization

    user = ctx.link.user
    orgs = list(
        Organization.objects.filter(
            memberships__user=user, memberships__is_active=True, is_active=True,
        ).order_by("code").distinct()
    )
    if not orgs:
        send_message(ctx.chat_id, "Нет доступных организаций.")
        return
    if len(orgs) == 1:
        send_message(
            ctx.chat_id,
            f"У вас одна организация: <b>{orgs[0].name}</b>. Переключать нечего.",
        )
        return

    active = ctx.org()
    buttons = [
        (
            f"{'• ' if o.id == active.id else ''}{o.name} ({o.code})",
            f"org:set:{o.id}",
        )
        for o in orgs
    ]
    send_message(
        ctx.chat_id,
        "🏢 <b>Выберите организацию:</b>",
        reply_markup=kb(buttons, cols=1),
    )


@on_callback("org:set")
def handle_org_set(ctx: HandlerCtx) -> None:
    from apps.organizations.models import Organization

    # callback_data: «org:set:<uuid>» → после фикса dispatcher (args = всё
    # ПОСЛЕ matched prefix `org:set`) ctx.args = [<uuid>].
    if not ctx.args:
        return
    org_id = ctx.args[0]
    user = ctx.link.user
    org = (
        Organization.objects
        .filter(id=org_id, memberships__user=user, memberships__is_active=True)
        .first()
    )
    if org is None:
        send_message(ctx.chat_id, "❌ У вас нет доступа к этой организации.")
        return

    ctx.link.active_organization = org
    ctx.link.save(update_fields=["active_organization"])
    send_message(
        ctx.chat_id,
        f"✅ Активная организация: <b>{org.name}</b>\n\nОтправьте /menu.",
    )
