from rest_framework import serializers
from rest_framework.validators import UniqueValidator  
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate

User = get_user_model()

# Register orqali faqat boss, admin, manager yaratish mumkin (worker alohida endpoint orqali)
REGISTER_ROLE_CHOICES = [
    ("boss", "Boss"),
    ("admin", "Admin"),
    ("manager", "Manager"),
]


class RegisterSerializers(serializers.ModelSerializer):
    role = serializers.ChoiceField(choices=REGISTER_ROLE_CHOICES, required=True)

    class Meta:
        model = User
        fields = [
            "id",
            "phone",
            "password",
            "full_name",
            "role",
            "avatar",
            "is_active",
            "is_staff",
        ]
        read_only_fields = ["id", "is_staff"]
        extra_kwargs = {
            'password' : {'write_only' : True},
            'phone' : {
                'required': True,
                "validators" : [
                    UniqueValidator(
                        queryset=User.objects.all(),
                        message = "Bu telefon raqam allaqachon ro'yxatdan o'tgan."
                    )
                ]
            },
        }

    def validate_phone(self, value):
        phone = str(value).strip()
        if not phone.startswith("+998"):
            raise serializers.ValidationError("Telefon raqam +998 bilan boshlanishi shart.")
        return phone

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)
        return user
           
class LoginSerializers(serializers.Serializer):
    phone = serializers.CharField(required = True)
    password = serializers.CharField(write_only = True , required = True)
    def validate(self, data):
        user = authenticate(phone = data.get('phone'), password = data.get('password'))
        if not user or not user.is_active:
            raise serializers.ValidationError("Invalid credentials or disabled account.")
        return {"user" : user}     
    
class UserMinimalSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model  = User
        fields = ["id", "phone", "full_name"]
        
        
        

class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "phone",
            "full_name",
            "role",
            "avatar",
            "is_active",
            "is_staff",
            "created_at",
        ]
        read_only_fields = ["id", "phone", "role", "is_active", "is_staff", "created_at"]
        
        
