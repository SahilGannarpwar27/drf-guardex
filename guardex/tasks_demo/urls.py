from django.urls import path

from .views import TriggerTractorStatusLogView, TaskStatusView, TractorListView

urlpatterns = [
    path('log-tractor-status/', TriggerTractorStatusLogView.as_view(), name='trigger-tractor-status-log'),
    path('task-status/<str:task_id>/', TaskStatusView.as_view(), name='task-status'),
    path('tractors/', TractorListView.as_view(), name='tractor-list'),
]
