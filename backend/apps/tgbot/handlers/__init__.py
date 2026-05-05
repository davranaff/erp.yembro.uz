"""Регистрация всех handler-модулей.

Импорт этого пакета регистрирует все `@command` / `@on_callback` декораторы
в реестрах из `dispatcher.py`. Последовательность не критична, но `legacy`
импортится первым чтобы старые `/report /balance ...` сохранили back-compat.
"""
from . import legacy  # noqa: F401  — /report /balance /cashflow /production
from . import help_cmd  # noqa: F401  — /help
from . import menu  # noqa: F401  — /menu + home:* callbacks
from . import finance  # noqa: F401  — /sales /cash /debt /pnl + fin:* callbacks
from . import production  # noqa: F401  — /feedlot /batch /herd + prod:* callbacks
from . import reports  # noqa: F401  — reports:* callbacks
from . import org  # noqa: F401  — /org + org:* callbacks
from . import digest  # noqa: F401  — /digest /digest_on /digest_off
from . import counterparty  # noqa: F401  — /buyurtmalar /qarz /holat для cp-link
