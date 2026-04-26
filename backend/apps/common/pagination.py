"""
Общие классы пагинации.
"""
from rest_framework.pagination import PageNumberPagination


class FlexiblePageNumberPagination(PageNumberPagination):
    """
    Пагинация с поддержкой `?page_size=N` в query-string.

    Default: 25 (как глобально). Max: 2000 — для случаев когда клиенту
    нужна вся история (архив курсов, справочник валют).
    """

    page_size_query_param = "page_size"
    max_page_size = 2000
