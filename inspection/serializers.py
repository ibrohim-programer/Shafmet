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
        phone = str(value).strip()
        if not phone.startswith("+998"):
            raise serializers.ValidationError("Telefon raqam +998 bilan boshlanishi shart.")
        if User.objects.filter(phone=phone).exists():
            raise serializers.ValidationError(
                "Bu telefon raqam allaqachon ro'yxatdan o'tgan."
            )
        return phone

    def create(self, validated_data):
        photo = validated_data["photo"]

        encoding = get_face_encoding(photo)
        if encoding is None:
            raise serializers.ValidationError(
                {"photo": "Rasmda yuz topilmadi. Iltimos, aniq yuz rasmi yuklang."}
            )

        with transaction.atomic():
            user = User.objects.create_user(
                phone=validated_data["phone"],
                password=validated_data["password"],
                full_name=validated_data["full_name"],
                role="worker",
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


# ─────────────────────────────────────────────────────────────────
# CheckInSerializer — ikkita rejim:
#   1) EMBEDDING rejimi  → mobil ML model ishlatadi
#      { user_id, embedding, latitude*, longitude* }   (* optional)
#
#   2) PHOTO rejimi → eski server-side face_recognition
#      { photo, latitude, longitude }
# ─────────────────────────────────────────────────────────────────
class CheckInSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(
        required=False,
        help_text="Foydalanuvchi IDsi. Ixtiyoriy — token orqali ham aniqlanadi.",
    )
    photo = serializers.ImageField(
        required=True,
        help_text="Server-side yuz tahlili uchun rasm fayli.",
    )
    latitude = serializers.FloatField(
        required=True,
        help_text="GPS kenglik.",
    )
    longitude = serializers.FloatField(
        required=True,
        help_text="GPS uzunlik.",
    )

    def validate(self, attrs):
        # ── Foydalanuvchini aniqlash tekshiruvi ──
        request = self.context.get("request")
        user_id = attrs.get("user_id")
        is_authenticated = request and request.user and request.user.is_authenticated
        if not is_authenticated and not user_id:
            raise serializers.ValidationError(
                {"detail": "Foydalanuvchini aniqlash uchun token yoki 'user_id' yuborilishi shart."}
            )

        return attrs




class WorkZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkZone
        fields = ["id", "name", "latitude", "longitude", "radius_meters", "is_active"]
        read_only_fields = ["id"]


class AttendanceSerializer(serializers.ModelSerializer):
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