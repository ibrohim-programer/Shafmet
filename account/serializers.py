from rest_framework import serializers
from rest_framework.validators import UniqueValidator  
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate
from django.db import transaction
from .models import Lavozim

User = get_user_model()

class LavozimSerializer(serializers.ModelSerializer):
    code = serializers.CharField(source='slug', read_only=True)

    class Meta:
        model = Lavozim
        fields = ["id", "name", "slug", "code", "description", "show_in_diagram", "is_default", "created_at"]

REGISTER_ROLE_CHOICES = [
    ("boss", "Boss"),
    ("admin", "Admin"),
    ("manager", "Manager"),
    ("worker", "Worker"),
]


class RegisterSerializers(serializers.ModelSerializer):
    role = serializers.ChoiceField(choices=REGISTER_ROLE_CHOICES, required=True)
    photo = serializers.ImageField(write_only=True, required=False, allow_null=True)
    photo_url = serializers.SerializerMethodField(read_only=True)
    department_detail = LavozimSerializer(source='department', read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "phone",
            "password",
            "full_name",
            "role",
            "avatar",
            "photo",
            "photo_url",
            "branch",
            "department",
            "department_detail",
            "salary",
            "balance",
            "work_start_time",
            "work_end_time",
            "is_active",
            "is_staff",
        ]
        read_only_fields = ["id", "photo_url", "is_staff"]
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

    def validate(self, attrs):
        role = attrs.get("role")
        photo = attrs.get("photo")

        if role == "worker" and not photo:
            raise serializers.ValidationError(
                {"photo": "Worker yaratish uchun yuz rasmi (photo) yuborilishi shart."}
            )
        return attrs

    def create(self, validated_data):
        photo = validated_data.pop("photo", None)
        password = validated_data.pop("password")

        encoding = None
        if photo:
            from inspection.services import get_face_encoding

            try:
                encoding = get_face_encoding(photo)
            except Exception:
                raise serializers.ValidationError(
                    {"photo": "Yuz rasmini o'qib bo'lmadi. Iltimos, aniq yuz rasmi yuklang."}
                )
            if encoding is None:
                raise serializers.ValidationError(
                    {"photo": "Rasmda yuz topilmadi. Iltimos, aniq yuz rasmi yuklang."}
                )
            try:
                photo.seek(0)
            except Exception:
                pass

        with transaction.atomic():
            user = User.objects.create_user(password=password, **validated_data)
            if photo:
                from inspection.models import FaceProfile

                FaceProfile.objects.create(
                    user=user,
                    encoding=encoding,
                    photo=photo,
                )
        return user

    def get_photo_url(self, obj):
        request = self.context.get("request")
        image = None

        try:
            face_profile = obj.face_profile
        except Exception:
            face_profile = None

        if face_profile and face_profile.photo:
            image = face_profile.photo
        elif obj.avatar:
            image = obj.avatar

        if not image:
            return None

        url = image.url
        if request:
            return request.build_absolute_uri(url)
        return url
           
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
    department_detail = LavozimSerializer(source='department', read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "phone",
            "full_name",
            "role",
            "avatar",
            "branch",
            "department",
            "department_detail",
            "salary",
            "balance",
            "work_start_time",
            "work_end_time",
            "is_active",
            "is_staff",
            "created_at",
        ]
        read_only_fields = ["id", "phone", "role", "is_active", "is_staff", "created_at", "salary", "balance"]


class UserAdminSerializer(serializers.ModelSerializer):
    department_detail = LavozimSerializer(source='department', read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "phone",
            "full_name",
            "role",
            "avatar",
            "branch",
            "department",
            "department_detail",
            "salary",
            "balance",
            "work_start_time",
            "work_end_time",
            "is_active",
            "is_staff",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
        
        
