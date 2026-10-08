from celery.result import AsyncResult
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from vehicle.models import Tractor
from vehicle.serializers import TractorSerializer

from .tasks import log_tractor_status


class TriggerTractorStatusLogView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        tractor_id = request.data.get('tractor_id')
        result = log_tractor_status.delay(tractor_id)
        return Response({
            "task_id": result.id,
            "message": "Task queued",
        }, status=status.HTTP_202_ACCEPTED)


class TaskStatusView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, task_id):
        result = AsyncResult(task_id)
        return Response({
            "task_id": task_id,
            "status": result.status,
            "result": result.result if result.ready() else None,
        })

# for testing only
class TractorListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        tractors = Tractor.objects.all()
        serializer = TractorSerializer(tractors, many=True)
        return Response(serializer.data)
