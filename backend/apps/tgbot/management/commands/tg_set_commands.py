"""
manage.py tg_set_commands — синхронизирует список публичных команд бота
с Telegram BotFather через POST /bot{TOKEN}/setMyCommands.

В клиенте Telegram это даёт автокомплит при вводе `/` и кнопку «Меню».
Запускается вручную после деплоя (не в beat — список меняется редко).

Команды с `private=True` (legacy /report /balance /stock /cashflow /production)
из выдачи скрыты — пользователю предлагаем `/menu` для inline-навигации.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.tgbot.bot import set_my_commands
# импорт регистрирует все команды в COMMANDS реестре через декораторы.
from apps.tgbot import handlers  # noqa: F401
from apps.tgbot.dispatcher import COMMANDS


class Command(BaseCommand):
    help = "Sync bot command list with Telegram (setMyCommands)."

    def handle(self, *args, **options):
        seen_handlers: set[int] = set()
        payload: list[dict] = []
        for spec in sorted(COMMANDS.values(), key=lambda s: s.name):
            if spec.private:
                continue
            # Дедуп для alias-ов: одна функция могла попасть под двумя именами.
            if id(spec.handler) in seen_handlers:
                continue
            seen_handlers.add(id(spec.handler))
            # Telegram требует команду без leading slash.
            payload.append({
                "command": spec.name.lstrip("/"),
                "description": spec.help_line[:256] or spec.name,
            })

        ok = set_my_commands(payload)
        if ok:
            self.stdout.write(self.style.SUCCESS(
                f"setMyCommands → ok ({len(payload)} команд)."
            ))
            for c in payload:
                self.stdout.write(f"  /{c['command']} — {c['description']}")
        else:
            self.stdout.write(self.style.ERROR(
                "setMyCommands → не удалось. Проверьте TELEGRAM_BOT_TOKEN."
            ))
