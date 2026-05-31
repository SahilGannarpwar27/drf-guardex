from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.decorators import action
from guardex.utils.permission import IsSuperAdmin
from user.models import User, Organization, UserRole
from rest_framework import viewsets
from .serializers import LoginSerializer, UserRoleSerializer, UserSerializer, OrganizationSerializer

class LoginView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        return Response({
            "access": serializer.validated_data["access"],
            "refresh": serializer.validated_data["refresh"],
            "user": serializer.validated_data["user"]
        }, status=status.HTTP_200_OK)
        
class logoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            print(refresh_token)
            if not refresh_token:
                return Response(
                    {"error": "Refresh token is required to logout."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"message": "Logged out successfully"}, status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response({"error": "Invalid token"}, status=status.HTTP_400_BAD_REQUEST)

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.filter(is_active=True)
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
    def destroy(self, request, *args, **kwargs):        
        instance = self.get_object()
        instance.is_active = False
        instance.save()
        return Response({"message": "User deactivated"}, status=status.HTTP_200_OK)
    
    @action(detail=False, url_path="me", methods=["GET", "PATCH", "PUT"], permission_classes=[IsAuthenticated])
    def me(self, request):
        user = request.user
        
        if request.method == "GET":
            serializer = self.get_serializer(user)
        
        elif request.method in ["PATCH", "PUT"]:
            serializer = self.get_serializer(user, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()

        return Response(serializer.data)

class OrganizationUserViewSet(viewsets.ModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]
    
class UserRoleView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        roles = UserRole.objects.all()
        serializer = UserRoleSerializer(roles, many=True)
        return Response(serializer.data)
    