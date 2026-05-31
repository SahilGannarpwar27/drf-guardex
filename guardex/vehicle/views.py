from guardex.utils.permission import IsAdmin
from rest_framework import viewsets
from .models import Tractor, Trailer, Trip
from .serializers import TractorSerializer, TrailerSerializer, TripSerializer
from guardex.utils.pagination import CustomPagination
from django_filters.rest_framework import DjangoFilterBackend
from guardex.utils.filters import TractorFilter
from rest_framework.filters import SearchFilter
from rest_framework.filters import OrderingFilter

class TractorViewSet(viewsets.ModelViewSet):
    queryset = Tractor.objects.all()
    serializer_class = TractorSerializer
    permission_classes = [IsAdmin]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = TractorFilter 
    search_fields = [
        '=tractor_id',
        'vin',
        'maker',
        'model'
    ]   
    ordering_fields = [
        'created_at',
        'updated_at',
        'status'
    ]
    
class TrailerViewSet(viewsets.ModelViewSet):
    queryset = Trailer.objects.all()
    serializer_class = TrailerSerializer
    permission_classes = [IsAdmin]
    
class TripViewSet(viewsets.ModelViewSet):
    queryset = Trip.objects.select_related(
        'tractor',
        'driver'
    ).prefetch_related(
        'trailer'
    )
    serializer_class = TripSerializer
    permission_classes = [IsAdmin]