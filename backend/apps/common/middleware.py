"""
No-op middleware: ставит request.organization / request.membership = None.

DRF-аутентификация срабатывает ПОСЛЕ django middleware, поэтому реальная
логика резолвинга организации живёт в `OrganizationContextMixin.initial()`
(apps/common/viewsets.py), который выполняется в APIView после
perform_authentication.
"""
from django.utils.deprecation import MiddlewareMixin


class OrganizationMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.organization = None
        request.membership = None
        return None
