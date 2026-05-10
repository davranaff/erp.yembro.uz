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
from . import modules_hub  # noqa: F401  — mod:* + rep:* (per-module hub + analytics)
from . import stock  # noqa: F401  — /qoldiq + wh:bal/wh:list + fin:stock
from . import wizard_cmds  # noqa: F401  — /bekor (отмена wizard-сессии)
from . import payroll  # noqa: F401  — /zp /myzp
from .. import wizards  # noqa: F401  — регистрирует wizard-handlers
from ..wizards import feed_purchase  # noqa: F401  — /qabul (приход)
from ..wizards import feed_writeoff  # noqa: F401  — /chiqim (списание)
from ..wizards import feed_mix  # noqa: F401  — /aralash (замес)
from ..wizards import feed_sale  # noqa: F401  — /sotuv (продажа мешков)
from ..wizards import payment_in  # noqa: F401  — /tolov (поступление)
from ..wizards import payment_opex  # noqa: F401  — /xarajat (расход)
