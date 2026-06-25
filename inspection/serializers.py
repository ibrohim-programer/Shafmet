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
    # ── Embedding rejimi maydonlari ──
    user_id = serializers.IntegerField(
        required=False,
        help_text="Embedding rejimida ixtiyoriy — token orqali ham aniqlanadi.",
    )
    embedding = serializers.ListField(
        child=serializers.FloatField(),
        required=False,
        allow_empty=False,
        help_text="Mobildan kelgan 128 ta float vektor (L2-normalized).",
    )

    # ── Photo rejimi maydoni ──
    photo = serializers.ImageField(
        required=False,
        help_text="Server-side yuz tahlili uchun rasm fayli.",
    )

    # ── Ikkala rejimda ham qabul qilinadigan lokatsiya ──
    latitude = serializers.FloatField(
        required=False,
        help_text="GPS kenglik. Embedding rejimida ixtiyoriy, photo rejimida majburiy.",
    )
    longitude = serializers.FloatField(
        required=False,
        help_text="GPS uzunlik. Embedding rejimida ixtiyoriy, photo rejimida majburiy.",
    )

    def validate(self, attrs):
        has_embedding = bool(attrs.get("embedding"))
        has_photo = bool(attrs.get("photo"))

        # ── Hech biri yuborilmagan ──
        if not has_embedding and not has_photo:
            raise serializers.ValidationError(
                {"detail": "'embedding' yoki 'photo' maydonlaridan biri yuborilishi shart."}
            )

        # ── Ikkisi birga yuborilgan — buni taqiqlaymiz ──
        if has_embedding and has_photo:
            raise serializers.ValidationError(
                {"detail": "'embedding' va 'photo' bir vaqtda yuborib bo'lmaydi."}
            )

        # ── Embedding rejimi validatsiyasi ──
        if has_embedding:
            if len(attrs["embedding"]) != 128:
                raise serializers.ValidationError(
                    {"embedding": f"Embedding 128 ta sondan iborat bo'lishi kerak. Keldi: {len(attrs['embedding'])}."}
                )
            # Lokatsiya ixtiyoriy — agar biri yuborilsa ikkalasi ham kerak
            has_lat = "latitude" in attrs and attrs["latitude"] is not None
            has_lon = "longitude" in attrs and attrs["longitude"] is not None
            if has_lat != has_lon:
                raise serializers.ValidationError(
                    {"detail": "Lokatsiya uchun latitude va longitude ikkalasi ham yuborilishi kerak."}
                )

        # ── Photo rejimi validatsiyasi ──
        if has_photo:
            if "latitude" not in attrs or attrs.get("latitude") is None:
                raise serializers.ValidationError(
                    {"latitude": "Photo rejimida latitude majburiy."}
                )
            if "longitude" not in attrs or attrs.get("longitude") is None:
                raise serializers.ValidationError(
                    {"longitude": "Photo rejimida longitude majburiy."}
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