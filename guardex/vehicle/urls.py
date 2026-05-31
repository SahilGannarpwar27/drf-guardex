from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'tractors', views.TractorViewSet, basename='tractors')
router.register(r'trailers', views.TrailerViewSet, basename='trailers')
router.register(r'trips', views.TripViewSet, basename='trips')

urlpatterns = [
    path('', include(router.urls)),
]