from drf_spectacular.utils import OpenApiExample, extend_schema
from drf_spectacular.types import OpenApiTypes
from rest_framework import generics, parsers, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsAdmin

from .models import Attendance, WorkZone
from .serializers import (
    AttendanceSerializer,
    CheckInSerializer,
    CreateWorkerSerializer,
    WorkZoneSerializer,
)
from .services import compare_faces, is_inside_zone


# ─────────────────────────────────────────────
# 1. Ishchi yaratish (faqat admin)
# ─────────────────────────────────────────────
class CreateWorkerView(APIView):
    """Admin yangi ishchi yaratadi — yuz rasmi bilan."""
    permission_classes = [IsAdmin]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    @extend_schema(
        tags=["Inspection - Workers"],
        summary="Yangi ishchi yaratish (yuz bilan)",
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "phone": {"type": "string", "example": "+998901112233"},
                    "full_name": {"type": "string", "example": "Karimov Jasur"},
                    "password": {"type": "string", "example": "securepass123"},
                    "photo": {"type": "string", "format": "binary"},
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
# 2. Check-in (ishchi o'zi)
# ─────────────────────────────────────────────
class CheckInView(APIView):
    """Ishchi check-in qiladi: yuz + joylashuv tekshiruvi."""
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    @extend_schema(
        tags=["Inspection - Attendance"],
        summary="Ishchi check-in (yuz + lokatsiya)",
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "photo": {"type": "string", "format": "binary"},
                    "latitude": {"type": "number", "example": 41.311081},
                    "longitude": {"type": "number", "example": 69.240562},
                },
                "required": ["photo", "latitude", "longitude"],
            }
        },
        responses={
            200: {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "face_verified": {"type": "boolean"},
                    "location_verified": {"type": "boolean"},
                    "distance_meters": {"type": "number"},
                    "message": {"type": "string"},
                },
            }
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = CheckInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        photo = serializer.validated_data["photo"]
        latitude = serializer.validated_data["latitude"]
        longitude = serializer.validated_data["longitude"]

        # Yuz profili mavjudligini tekshirish
        if not hasattr(user, "face_profile"):
            return Response(
                {"detail": "Avval yuz ro'yxatdan o'tkazilmagan."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # STEP 1: Yuzni solishtirish
        face_matched, face_distance = compare_faces(
            user.face_profile.encoding, photo
        )

        # STEP 2: Joylashuvni tekshirish
        zone = WorkZone.objects.filter(is_active=True).first()
        if zone is None:
            return Response(
                {"detail": "Ish hududi belgilanmagan."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        in_zone, distance_meters = is_inside_zone(latitude, longitude, zone)

        # Natija
        is_success = face_matched and in_zone

        # Davomat yozuvini saqlash (muvaffaqiyatli bo'lmasa ham)
        Attendance.objects.create(
            user=user,
            latitude=latitude,
            longitude=longitude,
            distance_meters=round(distance_meters, 2),
            face_verified=face_matched,
            location_verified=in_zone,
            is_success=is_success,
        )

        # Xabar tayyorlash
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
                "success": is_success,
                "face_verified": face_matched,
                "location_verified": in_zone,
                "distance_meters": round(distance_meters, 2),
                "message": message,
            },
            status=status.HTTP_200_OK,
        )


# ─────────────────────────────────────────────
# 3. Ish hududlarini boshqarish (admin)
# ─────────────────────────────────────────────
@extend_schema(
    tags=["Inspection - Work Zones"],
    summary="Ish hududlari ro'yxati va yaratish",
)
class WorkZoneListCreateView(generics.ListCreateAPIView):
    """Admin: ish hududlarini ko'rish va yaratish."""
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
    """Admin: barcha davomat yozuvlarini ko'rish."""
    queryset = Attendance.objects.select_related("user").all()
    serializer_class = AttendanceSerializer
    permission_classes = [IsAdmin]
