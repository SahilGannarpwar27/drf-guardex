from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from user.choices import ROLE_CHOICES
from user.models import Organization, User, UserRole
from guardex.utils.authenticate import authenticate

class LoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        phone = attrs.get("phone_number")
        password = attrs.get("password")

        user = authenticate(phone_number=phone, password=password)
        if not user:
            raise serializers.ValidationError("Invalid credentials")

        if not user.is_active:
            raise serializers.ValidationError("User is inactive")

        refresh = RefreshToken.for_user(user)

        return {
            "user": UserSerializer(user).data,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }
    
class UserSerializer(serializers.ModelSerializer):
    user_role = serializers.SlugRelatedField(
        slug_field='name',
        queryset=UserRole.objects.all(),
        allow_null=True,
        required=False
    )

    class Meta:
        model = User
        fields = "__all__"
        extra_kwargs = {
            'password': {'write_only': True} 
        }

    def validate_user_role(self, value):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("You must be logged in to assign roles.")

        request_user = request.user
        
        request_user_role = request_user.user_role.name if request_user.user_role else None

        if self.instance and self.instance.user_role == value:
            return value

        assigned_role_name = value.name if value else None

        if request_user_role == 'super_admin':
            return value
            
        elif request_user_role == 'admin':
            if assigned_role_name == 'super_admin':
                raise serializers.ValidationError("Admins cannot assign the 'super_admin' role.")
            return value
            
        elif request_user_role in ['driver', 'field_assistant']:
            raise serializers.ValidationError("You do not have permission to assign or modify user roles.")
            
        raise serializers.ValidationError("You lack the required permissions to assign roles.")
    
    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = super().create(validated_data)
        
        if password:
            user.set_password(password)
            user.save()
            
        return user

    # 3. Override update to handle password changes safely (e.g., via your /me endpoint)
    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        user = super().update(instance, validated_data)
        
        if password:
            user.set_password(password)
            user.save()
            
        return user
    
class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ['name']
        
    def validate_name(self, value):
        if Organization.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError("Organization with this name already exists")
        return value
    
class UserRoleSerializer(serializers.ModelSerializer):
    value = serializers.CharField(source='name', read_only=True)
    
    label = serializers.CharField(source='get_name_display', read_only=True)

    class Meta:
        model = UserRole
        fields = ['value', 'label']
