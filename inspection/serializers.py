from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db import transaction

from .models import Attendance, FaceProfile, WorkZone
from .services import get_face_encoding

User = get_user_model()


class CreateWorkerSerializer(serializers.Serializer):
    """Yangi ishchi yaratish — yuz rasmi bilan birga."""
    phone = serializers.CharField(max_length=20)
    full_name = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True)
    photo = serializers.ImageField(write_only=True)

    def validate_phone(self, value):
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError(
                "Bu telefon raqam allaqachon ro'yxatdan o'tgan."
            )
        return value

    def create(self, validated_data):
        phone = validated_data["phone"]
        full_name = validated_data["full_name"]
        password = validated_data["password"]
        photo = validated_data["photo"]

        # Yuzni aniqlash
        encoding = get_face_encoding(photo)
        if encoding is None:
            raise serializers.ValidationError(
                {"photo": "Rasmda yuz topilmadi. Iltimos, aniq yuz rasmi yuklang."}
            )

        # Atomik: foydalanuvchi + yuz profili birga yaratiladi
        with transaction.atomic():
            user = User.objects.create_user(
                phone=phone,
                password=password,
                full_name=full_name,
                role="worker",  # Har doim WORKER
            )
            FaceProfile.objects.create(
                user=user,
                encoding=encoding,
                photo=photo,
            )

        return user

    def to_representation(self, instance):
        return {
            "id": instance.id,
            "phone": instance.phone,
            "full_name": instance.full_name,
            "role": instance.role,
        }


class CheckInSerializer(serializers.Serializer):
    """Check-in uchun kiruvchi ma'lumotlar."""
    user_id = serializers.IntegerField(required=False)
    embedding = serializers.ListField(
        child=serializers.FloatField(),
        required=False,
        allow_empty=False,
    )
    photo = serializers.ImageField(required=False)
    latitude = serializers.FloatField(required=False)
    longitude = serializers.FloatField(required=False)

    def validate(self, attrs):
        has_embedding = "embedding" in attrs and attrs.get("embedding") is not None
        has_photo = "photo" in attrs and attrs.get("photo") is not None

        if has_embedding:
            if len(attrs["embedding"]) != 128:
                raise serializers.ValidationError(
                    {"embedding": "Embedding 128 ta sondan iborat bo'lishi kerak."}
                )
            return attrs

        if has_photo:
            if "latitude" not in attrs or "longitude" not in attrs:
                raise serializers.ValidationError(
                    {"detail": "Photo-based check-in uchun latitude va longitude zarur."}
                )
            return attrs

        raise serializers.ValidationError(
            {"detail": "Embedding yoki photo bilan check-in yuboring."}
        )


class WorkZoneSerializer(serializers.ModelSerializer):
    """Ish hududi CRUD serializer."""
    class Meta:
        model = WorkZone
        fields = ["id", "name", "latitude", "longitude", "radius_meters", "is_active"]
        read_only_fields = ["id"]


class AttendanceSerializer(serializers.ModelSerializer):
    """Davomat yozuvi (o'qish uchun)."""
    user_phone = serializers.CharField(source="user.phone", read_only=True)
    user_full_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = Attendance
        fields = [
            "id",
            "user",
            "user_phone",
            "user_full_name",
            "latitude",
            "longitude",
            "distance_meters",
            "face_verified",
            "location_verified",
            "is_success",
            "created_at",
        ]
        read_only_fields = fields
