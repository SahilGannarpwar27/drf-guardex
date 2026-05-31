from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'organization', views.OrganizationUserViewSet, basename='organization-users')
router.register(r'', views.UserViewSet, basename='user')

urlpatterns = [
    path('login', views.LoginView.as_view(), name='login'),
    path('logout', views.logoutView.as_view(), name='logout'),
    path('', include(router.urls)),
    path('roles', views.UserRoleView.as_view(), name='user-roles'),
]