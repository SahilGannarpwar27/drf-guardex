import time

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from user.models import UserRole
from user.serializers import UserRoleSerializer
from vehicle.models import Tractor
from vehicle.serializers import TractorSerializer

from .mixins import CacheAsideMixin

CACHE_KEY = "demo_user_roles"
CACHE_TTL_SECONDS = 60 * 60  # UserRole barely ever changes, so a long TTL is safe

TRACTOR_CACHE_KEY = "demo_tractor_list"
TRACTOR_CACHE_TTL_SECONDS = 60 * 60  # long TTL is safe here BECAUSE the signal in
                                     # signals.py invalidates it immediately on any write

SIMULATED_QUERY_DELAY_SECONDS = 1  # artificial slowdown so concurrent requests can race


class CachedUserRolesView(CacheAsideMixin, APIView):
    """Cache-aside demo using the real UserRole table."""
    permission_classes = [AllowAny]
    cache_key = CACHE_KEY
    cache_ttl = CACHE_TTL_SECONDS

    def get_fresh_data(self):
        roles = UserRole.objects.all()
        return UserRoleSerializer(roles, many=True).data

    def get(self, request):
        start = time.perf_counter()
        data, source = self.get_cached_data()
        elapsed_ms = round((time.perf_counter() - start) * 1000, 3)
        return Response({
            "source": source,
            "elapsed_ms": elapsed_ms,
            "roles": data,
        })


class CachedTractorListView(CacheAsideMixin, APIView):
    """
    Cache-aside + stampede protection for Tractor's list, for data that
    actually changes (Tractor.status) - safe here only because the
    signal in signals.py invalidates the cache on every write.
    """
    permission_classes = [AllowAny]
    cache_key = TRACTOR_CACHE_KEY
    cache_ttl = TRACTOR_CACHE_TTL_SECONDS

    def get_fresh_data(self):
        tractors = Tractor.objects.all()
        time.sleep(SIMULATED_QUERY_DELAY_SECONDS)  # pretend this is an expensive query
        return TractorSerializer(tractors, many=True).data

    def get(self, request):
        start = time.perf_counter()
        data, source = self.get_cached_data()
        elapsed_ms = round((time.perf_counter() - start) * 1000, 3)
        return Response({
            "source": source,
            "elapsed_ms": elapsed_ms,
            "tractors": data,
        })
