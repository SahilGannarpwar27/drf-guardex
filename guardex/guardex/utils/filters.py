import django_filters
from vehicle.models import Tractor


class TractorFilter(django_filters.FilterSet):

    maker = django_filters.CharFilter(lookup_expr='icontains')
    axle_count = django_filters.NumberFilter(field_name='axle_count', lookup_expr='gte')

    class Meta:
        model = Tractor
        fields = [
            'status',
            'maker',
            'model',
            'axle_count'
        ]