from drf_spectacular.utils import extend_schema, OpenApiExample
from rest_framework import generics, parsers, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from django.contrib.auth import get_user_model
from django.db.models import Q

from core.permissions import IsAdmin, IsAdminOrManager, IsWorker

from .models import Attendance, WorkZone
from .serializers import (
    AttendanceSerializer,
    CheckInSerializer,
    CreateWorkerSerializer,
    WorkZoneSerializer,
    WorkerDetailSerializer,
)
from .services import calculate_cosine_similarity, compare_faces, compare_faces_direct, is_inside_zone
from .throttling import CheckInRateThrottle
from notifications.services import send_push_notification

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
    Ishchi check-in/out qiladi (rasm fayli yuborish orqali).
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [CheckInRateThrottle]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    @extend_schema(
        tags=["Inspection - Attendance"],
        summary="Ishchi check-in/out (rasm yuklash orqali)",
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
                    "attendance_type": {"type": "string", "enum": ["in", "out"], "default": "in", "description": "Davomat turi (kirish/chiqish)"},
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
                    "attendance_type":   {"type": "string"},
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
        attendance_type = data.get("attendance_type", "in")

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
        active_zones = WorkZone.objects.filter(is_active=True)
        if not active_zones.exists():
            return Response(
                {"detail": "Faol ish hududi topilmadi. Admin bilan bog'laning."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        in_zone = False
        min_distance = float('inf')

        for zone in active_zones:
            inside, dist = is_inside_zone(latitude, longitude, zone)
            if dist < min_distance:
                min_distance = dist
            if inside:
                in_zone = True

        distance_meters = min_distance
        is_success = face_matched and in_zone

        # ── Davomat yozuvi ──
        Attendance.objects.create(
            user=user,
            attendance_type=attendance_type,
            latitude=latitude,
            longitude=longitude,
            distance_meters=round(distance_meters, 2),
            face_verified=face_matched,
            location_verified=in_zone,
            is_success=is_success,
        )

        # ── Javob xabari ──
        type_str = "Kirish" if attendance_type == "in" else "Chiqish"
        if is_success:
            message = f"{type_str} davomati muvaffaqiyatli qayd etildi."
        elif not face_matched and not in_zone:
            message = f"Yuz tasdiqlanmadi va siz ish hududidan tashqaridasiz ({type_str} rad etildi)."
        elif not face_matched:
            message = f"Yuz tasdiqlanmadi. Iltimos, qaytadan urinib ko'ring ({type_str} rad etildi)."
        else:
            message = f"Siz ish hududidan tashqaridasiz ({type_str} rad etildi)."

        # ── Push bildirishnoma yuborish ──
        try:
            send_push_notification(
                user=user,
                title="Davomat Tizimi",
                body=message,
                data={
                    "success": str(is_success),
                    "attendance_type": attendance_type,
                    "distance_meters": str(round(distance_meters, 2))
                }
            )
        except Exception:
            pass

        return Response(
            {
                "success":           is_success,
                "face_verified":     face_matched,
                "location_verified": in_zone,
                "distance_meters":   round(distance_meters, 2),
                "attendance_type":   attendance_type,
                "message":           message,
            },
            status=status.HTTP_200_OK if is_success else status.HTTP_401_UNAUTHORIZED,
        )



# ─────────────────────────────────────────────
# 3. Ish hududlarini boshqarish (admin/manager)
# ─────────────────────────────────────────────
@extend_schema(
    tags=["Inspection - Work Zones"],
    summary="Ish hududlari ro'yxati va yaratish (Admin/Manager)",
)
class WorkZoneListCreateView(generics.ListCreateAPIView):
    queryset = WorkZone.objects.all()
    serializer_class = WorkZoneSerializer
    permission_classes = [IsAdminOrManager]


@extend_schema(
    tags=["Inspection - Work Zones"],
    summary="Ish hududini ko'rish, tahrirlash va o'chirish (Admin/Manager)",
)
class WorkZoneRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = WorkZone.objects.all()
    serializer_class = WorkZoneSerializer
    permission_classes = [IsAdminOrManager]


# ─────────────────────────────────────────────
# 4. Ishchilarni boshqarish (admin/manager)
# ─────────────────────────────────────────────
@extend_schema(
    tags=["Inspection - Workers"],
    summary="Ishchilar ro'yxati (Admin/Manager)",
)
class WorkerListView(generics.ListAPIView):
    serializer_class = WorkerDetailSerializer
    permission_classes = [IsAdminOrManager]

    def get_queryset(self):
        queryset = User.objects.filter(role="worker").select_related("face_profile").order_by("-created_at")
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(full_name__icontains=search) | Q(phone__icontains=search)
            )
        return queryset


@extend_schema(
    tags=["Inspection - Workers"],
    summary="Ishchi ma'lumotlarini ko'rish, yangilash va o'chirish (Admin/Manager)",
)
class WorkerRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = User.objects.filter(role="worker").select_related("face_profile")
    serializer_class = WorkerDetailSerializer
    permission_classes = [IsAdminOrManager]


# ─────────────────────────────────────────────
# 5. Davomatlar tizimi
# ─────────────────────────────────────────────
@extend_schema(
    tags=["Inspection - Attendance"],
    summary="Barcha davomatlar ro'yxati (Admin/Manager)",
)
class AttendanceListView(generics.ListAPIView):
    serializer_class = AttendanceSerializer
    permission_classes = [IsAdminOrManager]

    def get_queryset(self):
        queryset = Attendance.objects.select_related("user").all().order_by("-created_at")
        
        user_id = self.request.query_params.get("user_id")
        phone = self.request.query_params.get("phone")
        is_success = self.request.query_params.get("is_success")
        attendance_type = self.request.query_params.get("attendance_type")
        date = self.request.query_params.get("date")
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")

        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if phone:
            queryset = queryset.filter(user__phone__icontains=phone)
        if is_success is not None:
            if is_success.lower() in ["true", "1"]:
                queryset = queryset.filter(is_success=True)
            elif is_success.lower() in ["false", "0"]:
                queryset = queryset.filter(is_success=False)
        if attendance_type:
            queryset = queryset.filter(attendance_type=attendance_type)
        if date:
            queryset = queryset.filter(created_at__date=date)
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)

        return queryset


@extend_schema(
    tags=["Inspection - Attendance"],
    summary="Bitta davomat yozuvi tafsilotlari (Admin/Manager/Worker)",
)
class AttendanceRetrieveView(generics.RetrieveAPIView):
    queryset = Attendance.objects.select_related("user").all()
    serializer_class = AttendanceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        obj = super().get_object()
        if self.request.user.role == "worker" and obj.user != self.request.user:
            raise permissions.exceptions.PermissionDenied("Sizda ushbu davomat ma'lumotlarini ko'rish huquqi yo'q.")
        return obj


@extend_schema(
    tags=["Inspection - Attendance"],
    summary="Xodimning o'z davomatlari ro'yxati (Faqat Worker)",
)
class MyAttendanceListView(generics.ListAPIView):
    serializer_class = AttendanceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Attendance.objects.filter(user=self.request.user).order_by("-created_at")


@extend_schema(
    tags=["Inspection - Attendance"],
    summary="Davomat statistikasi (Admin/Manager)",
)
class AttendanceStatsView(APIView):
    permission_classes = [IsAdminOrManager]

    def get(self, request, *args, **kwargs):
        from django.utils import timezone
        
        today = timezone.localtime().date()
        today_attendances = Attendance.objects.filter(created_at__date=today)
        today_total = today_attendances.count()
        today_success = today_attendances.filter(is_success=True).count()
        today_failed = today_attendances.filter(is_success=False).count()
        
        today_unique_users = today_attendances.values("user").distinct().count()
        total_workers = User.objects.filter(role="worker").count()
        active_zones_count = WorkZone.objects.filter(is_active=True).count()

        data = {
            "date": today,
            "total_workers": total_workers,
            "active_zones_count": active_zones_count,
            "today_stats": {
                "total_checkins": today_total,
                "successful_checkins": today_success,
                "failed_checkins": today_failed,
                "unique_workers_checked_in": today_unique_users,
                "absent_workers": max(0, total_workers - today_unique_users)
            },
            "overall_stats": {
                "total_checkins_all_time": Attendance.objects.count(),
                "successful_checkins_all_time": Attendance.objects.filter(is_success=True).count()
            }
        }
        return Response(data, status=status.HTTP_200_OK)