"""
Re-export универсального генератора doc_number из apps/common.
Оставлен для обратной совместимости с тестами/импортами из purchases.
"""
from apps.common.services.numbering import next_doc_number  # noqa: F401
