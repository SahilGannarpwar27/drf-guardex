from django.urls import path

from .views import CachedUserRolesView, CachedTractorListView

urlpatterns = [
    path('roles/', CachedUserRolesView.as_view(), name='cached-roles'),
    path('tractors/', CachedTractorListView.as_view(), name='cached-tractors'),
]
