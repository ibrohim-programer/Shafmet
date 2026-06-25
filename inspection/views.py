from drf_spectacular.utils import extend_schema, OpenApiExample
from rest_framework import generics, parsers, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from django.contrib.auth import get_user_model

from core.permissions import IsAdmin

from .models import Attendance, WorkZone
from .serializers import (
    AttendanceSerializer,
    CheckInSerializer,
    CreateWorkerSerializer,
    WorkZoneSerializer,
)
from .services import calculate_cosine_similarity, compare_faces, compare_faces_direct, is_inside_zone

User = get_user_model()

# Yuz o'xshashlik chegarasi (cosine similarity)
FACE_SIMILARITY_THRESHOLD = 0.85


# ─────────────────────────────────────────────
# 1. Ishchi yaratish (faqat admin)
# ─────────────────────────────────────────────
class CreateWorkerView(APIView):
    """Admin yangi ishchi yaratadi — yuz rasmi bilan."""
    permission_classes = [IsAdmin]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    @extend_schema(
        tags=["Inspection - Workers"],
        summary="Yangi ishchi yaratish (yuz bilan)",
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "phone":     {"type": "string",  "example": "+998901112233"},
                    "full_name": {"type": "string",  "example": "Karimov Jasur"},
                    "password":  {"type": "string",  "example": "securepass123"},
                    "photo":     {"type": "string",  "format": "binary"},
                },
                "required": ["phone", "full_name", "password", "photo"],
            }
        },
        responses={201: CreateWorkerSerializer},
    )
    def post(self, request, *args, **kwargs):
        serializer = CreateWorkerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            CreateWorkerSerializer(user).data,
            status=status.HTTP_201_CREATED,
        )


# ─────────────────────────────────────────────
# 2. Check-in — IKKITA REJIM:
#    A) Embedding rejimi  (mobil ML model)
#    B) Photo rejimi      (server-side)
# ─────────────────────────────────────────────
class CheckInView(APIView):
    """
    Ishchi check-in qiladi (rasm fayli yuborish orqali).
    """
    permission_classes = [permissions.AllowAny]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    @extend_schema(
        tags=["Inspection - Attendance"],
        summary="Ishchi check-in (rasm yuklash orqali)",
        description=(
            "Ishchi yuz rasmini yuboradi. Server tomonida face_recognition kutubxonasi "
            "yordamida bazadagi rasm bilan solishtiriladi va GPS joylashuvi tekshiriladi."
        ),
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "user_id":   {"type": "integer", "description": "Foydalanuvchi IDsi (Ixtiyoriy — token bo'lsa shart emas)", "example": 42},
                    "photo":     {"type": "string", "format": "binary", "description": "Xodimning yuz rasmi"},
                    "latitude":  {"type": "number", "example": 41.311081, "description": "Kenglik koordinatasi"},
                    "longitude": {"type": "number", "example": 69.240562, "description": "Uzunlik koordinatasi"},
                },
                "required": ["photo", "latitude", "longitude"],
            },
        },
        responses={
            200: {
                "type": "object",
                "properties": {
                    "success":           {"type": "boolean"},
                    "face_verified":     {"type": "boolean"},
                    "location_verified": {"type": "boolean"},
                    "distance_meters":   {"type": "number"},
                    "message":           {"type": "string"},
                },
            },
            401: {"description": "Yuz mos kelmadi yoki foydalanuvchi topilmadi."},
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = CheckInSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user_id = data.get("user_id") or (request.user.id if request.user.is_authenticated else None)
        user = User.objects.filter(pk=user_id).select_related("face_profile").first()

        if user is None:
            return Response(
                {"detail": "Bunday foydalanuvchi topilmadi."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not hasattr(user, "face_profile"):
            return Response(
                {"detail": "Avval yuz ro'yxatdan o'tkazilmagan."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        photo     = data["photo"]
        latitude  = data["latitude"]
        longitude = data["longitude"]

        # ── Yuz solishtirish (Birinchi navbatda bazadagi real rasm bilan, xatolik bo'lsa encoding bilan) ──
        face_matched = False
        face_distance = 999.0
        
        # 1. Real rasm fayli bilan solishtirishga urinish
        res = compare_faces_direct(user.face_profile.photo.path, photo)
        if res is not None:
            face_matched, face_distance = res
        else:
            # 2. Agar bazadagi rasm bo'lmasa yoki xato bo'lsa, saqlangan encoding bilan solishtirish
            face_matched, face_distance = compare_faces(
                user.face_profile.encoding, photo
            )

        # ── Ish hududi tekshiruvi ──
        zone = WorkZone.objects.filter(is_active=True).first()
        if zone is None:
            return Response(
                {"detail": "Faol ish hududi topilmadi. Admin bilan bog'laning."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        in_zone, distance_meters = is_inside_zone(latitude, longitude, zone)
        is_success = face_matched and in_zone

        # ── Davomat yozuvi ──
        Attendance.objects.create(
            user=user,
            latitude=latitude,
            longitude=longitude,
            distance_meters=round(distance_meters, 2),
            face_verified=face_matched,
            location_verified=in_zone,
            is_success=is_success,
        )

        # ── Javob xabari ──
        if is_success:
            message = "Davomat muvaffaqiyatli qayd etildi."
        elif not face_matched and not in_zone:
            message = "Yuz tasdiqlanmadi va siz ish hududidan tashqaridasiz."
        elif not face_matched:
            message = "Yuz tasdiqlanmadi. Iltimos, qaytadan urinib ko'ring."
        else:
            message = "Siz ish hududidan tashqaridasiz."

        return Response(
            {
                "success":           is_success,
                "face_verified":     face_matched,
                "location_verified": in_zone,
                "distance_meters":   round(distance_meters, 2),
                "message":           message,
            },
            status=status.HTTP_200_OK if is_success else status.HTTP_401_UNAUTHORIZED,
        )



# ─────────────────────────────────────────────
# 3. Ish hududlarini boshqarish (admin)
# ─────────────────────────────────────────────
@extend_schema(
    tags=["Inspection - Work Zones"],
    summary="Ish hududlari ro'yxati va yaratish",
)
class WorkZoneListCreateView(generics.ListCreateAPIView):
    queryset = WorkZone.objects.all()
    serializer_class = WorkZoneSerializer
    permission_classes = [IsAdmin]


# ─────────────────────────────────────────────
# 4. Davomat ro'yxati (admin)
# ─────────────────────────────────────────────
@extend_schema(
    tags=["Inspection - Attendance"],
    summary="Davomatlar ro'yxati (admin)",
)
class AttendanceListView(generics.ListAPIView):
    queryset = Attendance.objects.select_related("user").all()
    serializer_class = AttendanceSerializer
    permission_classes = [IsAdmin]