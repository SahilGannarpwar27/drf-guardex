from user.models import User

def authenticate(phone_number=None, password=None):
        try:
            user = User.objects.get(phone_number=phone_number)
        except User.DoesNotExist:
            return None

        if user.check_password(password):
            return user
        return None