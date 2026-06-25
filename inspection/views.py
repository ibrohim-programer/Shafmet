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
from .services import calculate_cosine_similarity, compare_faces, is_inside_zone

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
    Ishchi check-in qiladi.

    REJIM A — Embedding (mobil tomondan ML model):
        Content-Type: application/json
        {
            "user_id": 42,                          ← ixtiyoriy (token bo'lsa shart emas)
            "embedding": [0.21, -0.84, 0.13, ...], ← 128 ta float, L2-normalized
            "latitude": 41.311081,                  ← ixtiyoriy
            "longitude": 69.240562                  ← ixtiyoriy
        }

    REJIM B — Photo (server-side face_recognition):
        Content-Type: multipart/form-data
        photo=<file>, latitude=41.31, longitude=69.24
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    @extend_schema(
        tags=["Inspection - Attendance"],
        summary="Ishchi check-in (embedding yoki rasm)",
        description=(
            "**Rejim A — Embedding (tavsiya etiladi):** Mobil ML model yuz embeddingini "
            "hisoblab JSON formatda yuboradi. Lokatsiya ixtiyoriy.\n\n"
            "**Rejim B — Photo:** Rasm server tomonida tahlil qilinadi. "
            "Lokatsiya majburiy."
        ),
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "user_id":   {"type": "integer", "example": 42},
                    "embedding": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 128,
                        "maxItems": 128,
                        "example": [0.21, -0.84, 0.13, 0.67, -0.45, 0.92],
                    },
                    "latitude":  {"type": "number", "example": 41.311081},
                    "longitude": {"type": "number", "example": 69.240562},
                },
                "required": ["embedding"],
            },
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "photo":     {"type": "string", "format": "binary"},
                    "latitude":  {"type": "number", "example": 41.311081},
                    "longitude": {"type": "number", "example": 69.240562},
                },
                "required": ["photo", "latitude", "longitude"],
            },
        },
        examples=[
            OpenApiExample(
                "Embedding rejimi (muvaffaqiyatli)",
                value={
                    "success": True,
                    "face_verified": True,
                    "location_verified": True,
                    "similarity": 0.9234,
                    "distance_meters": 45.2,
                    "message": "Davomat muvaffaqiyatli qayd etildi.",
                },
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Yuz mos kelmadi",
                value={
                    "success": False,
                    "face_verified": False,
                    "location_verified": True,
                    "similarity": 0.6102,
                    "distance_meters": 30.5,
                    "message": "Yuz mos kelmadi.",
                },
                response_only=True,
                status_codes=["401"],
            ),
        ],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "success":           {"type": "boolean"},
                    "face_verified":     {"type": "boolean"},
                    "location_verified": {"type": "boolean"},
                    "similarity":        {"type": "number", "description": "Cosine similarity (0–1)"},
                    "distance_meters":   {"type": "number"},
                    "message":           {"type": "string"},
                },
            },
            401: {"description": "Yuz mos kelmadi yoki foydalanuvchi topilmadi."},
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = CheckInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if data.get("embedding"):
            return self._handle_embedding(request, data)

        return self._handle_photo(request, data)

    # ── REJIM A: Embedding ────────────────────────────────────────────
    def _handle_embedding(self, request, data):
        """
        Mobildan kelgan 128-o'lchamli embedding vektori bilan
        DBdagi profil vektori cosine similarity orqali solishtiriladi.
        """
        # Foydalanuvchini aniqlash: avval token, keyin user_id
        user_id = data.get("user_id") or request.user.id
        user = User.objects.filter(pk=user_id).select_related("face_profile").first()

        if user is None:
            return Response(
                {"detail": "Bunday foydalanuvchi topilmadi."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not hasattr(user, "face_profile"):
            return Response(
                {"detail": "Avval yuz ro'yxatdan o'tkazilmagan."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # ── Cosine similarity hisoblash ──
        similarity = calculate_cosine_similarity(
            user.face_profile.encoding,
            data["embedding"],
        )
        face_verified = similarity >= FACE_SIMILARITY_THRESHOLD

        # ── Lokatsiya tekshiruvi (yuborilgan bo'lsa) ──
        latitude  = data.get("latitude")
        longitude = data.get("longitude")
        location_verified = False
        distance_meters   = 0.0

        if latitude is not None and longitude is not None:
            zone = WorkZone.objects.filter(is_active=True).first()
            if zone:
                location_verified, distance_meters = is_inside_zone(
                    latitude, longitude, zone
                )
                distance_meters = round(distance_meters, 2)

        # Umumiy muvaffaqiyat: yuz + (lokatsiya yuborilgan bo'lsa u ham)
        has_location = latitude is not None
        is_success = face_verified and (location_verified if has_location else True)

        # ── Davomat yozuvi ──
        Attendance.objects.create(
            user=user,
            latitude=latitude  or 0.0,
            longitude=longitude or 0.0,
            distance_meters=distance_meters,
            face_verified=face_verified,
            location_verified=location_verified,
            is_success=is_success,
        )

        # ── Javob xabari ──
        if is_success:
            message = "Davomat muvaffaqiyatli qayd etildi."
            http_status = status.HTTP_200_OK
        elif not face_verified:
            message = "Yuz mos kelmadi."
            http_status = status.HTTP_401_UNAUTHORIZED
        else:
            message = "Siz ish hududidan tashqaridasiz."
            http_status = status.HTTP_401_UNAUTHORIZED

        return Response(
            {
                "success":           is_success,
                "face_verified":     face_verified,
                "location_verified": location_verified,
                "similarity":        round(similarity, 4),
                "distance_meters":   distance_meters,
                "message":           message,
            },
            status=http_status,
        )

    # ── REJIM B: Photo (server-side face_recognition) ─────────────────
    def _handle_photo(self, request, data):
        """
        Rasm serverda face_recognition kutubxonasi orqali tahlil qilinadi.
        Lokatsiya ham tekshiriladi.
        """
        user      = request.user
        photo     = data["photo"]
        latitude  = data["latitude"]
        longitude = data["longitude"]

        if not hasattr(user, "face_profile"):
            return Response(
                {"detail": "Avval yuz ro'yxatdan o'tkazilmagan."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Yuz solishtirish ──
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