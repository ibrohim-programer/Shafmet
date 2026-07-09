from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiParameter, inline_serializer
from rest_framework import generics, parsers, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from django.contrib.auth import get_user_model
from django.db.models import Q

from core.permissions import IsAdmin, IsAdminUser, IsAdminOrManager, IsWorker

from account.models import Lavozim
from .models import Attendance, WorkZone, WorkSchedule, DailyAttendance
from .serializers import (
    AttendanceSerializer,
    CheckInSerializer,
    CreateWorkerSerializer,
    WorkZoneSerializer,
    WorkerDetailSerializer,
    AttendanceByDateSerializer,
    WorkScheduleSerializer,
    DailyAttendanceSerializer,
    LavozimSerializer,
    LavozimCreateSerializer,
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
    permission_classes = [IsAdminUser]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    @extend_schema(
        tags=["Inspection - Workers"],
        summary="Yangi ishchi yaratish (yuz bilan)",
        request=CreateWorkerSerializer,
        responses={201: CreateWorkerSerializer},
    )
    def post(self, request, *args, **kwargs):
        serializer = CreateWorkerSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            CreateWorkerSerializer(user, context={'request': request}).data,
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

        # ── Davomat yozuvi va Avtomatik Davomat Turini Aniqlash ──
        from django.utils import timezone
        import zoneinfo
        tashkent_tz = zoneinfo.ZoneInfo("Asia/Tashkent")
        today = timezone.localtime().date()
        
        attendance, _ = Attendance.objects.get_or_create(
            worker=user,
            date=today,
        )

        # Davomat turini avtomatik aniqlash (State machine)
        if attendance.check_in_time and attendance.check_in_success:
            if attendance.check_out_time and attendance.check_out_success:
                return Response(
                    {"detail": "Bugungi davomat allaqachon to'liq belgilangan (Kirish va chiqish bajarilgan)."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            attendance_type = "out"
        else:
            attendance_type = "in"

        is_late = False
        if is_success:
            if attendance_type == "in":
                # Calculate lateness
                start_time = None
                if user.work_start_time:
                    start_time = user.work_start_time
                else:
                    schedule = None
                    if user.department:
                        schedule = WorkSchedule.objects.filter(departments=user.department).first()
                    if schedule:
                        start_time = schedule.start_time

                if start_time:
                    now_time = timezone.localtime(timezone.now()).time()
                    if now_time > start_time:
                        is_late = True

                attendance.check_in_time = timezone.now()
                attendance.check_in_success = is_success
                attendance.is_late = is_late
                attendance.save()

                message = "kechikdingiz" if is_late else "muvaffaqiyatli"

            else:  # check-out
                attendance.check_out_time = timezone.now()
                attendance.check_out_success = is_success
                attendance.save()
                message = "muvaffaqiyatli"

        else:
            # Failed attempt
            type_str = "Kirish" if attendance_type == "in" else "Chiqish"
            if not face_matched and not in_zone:
                message = f"Yuz tasdiqlanmadi va siz ish hududidan tashqaridasiz ({type_str} rad etildi)."
            elif not face_matched:
                message = f"Yuz tasdiqlanmadi. Iltimos, qaytadan urinib ko'ring ({type_str} rad etildi)."
            else:
                message = f"Siz ish hududidan tashqaridasiz ({type_str} rad etildi)."

            if attendance_type == "in":
                attendance.check_in_success = False
                attendance.save()
            else:
                attendance.check_out_success = False
                attendance.save()

        # Update or create DailyAttendance if check-in was successful
        if is_success:
            daily_att, created = DailyAttendance.objects.get_or_create(user=user, date=today)
            if attendance_type == "in":
                if not daily_att.check_in_time:
                    daily_att.check_in_time = timezone.now()
                    daily_att.is_late = is_late
                    daily_att.save()
            elif attendance_type == "out":
                daily_att.check_out_time = timezone.now()
                daily_att.save()

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

        def to_local_iso(dt):
            if dt:
                return timezone.localtime(dt, tashkent_tz).isoformat()
            return None

        return Response(
            {
                "success":           is_success,
                "face_verified":     face_matched,
                "location_verified": in_zone,
                "distance_meters":   round(distance_meters, 2),
                "attendance_type":   attendance_type,
                "message":           message,
                "check_in_time":     to_local_iso(attendance.check_in_time),
                "check_out_time":    to_local_iso(attendance.check_out_time),
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
        queryset = User.objects.filter(role="worker").select_related("face_profile", "department").order_by("-created_at")
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(full_name__icontains=search) | Q(phone__icontains=search)
            )
        
        department = self.request.query_params.get("department")
        if department:
            if department.isdigit():
                queryset = queryset.filter(department_id=int(department))
            else:
                queryset = queryset.filter(
                    Q(department__slug=department) |
                    Q(department__slug=department.replace("u", "o")) |
                    Q(department__slug=department.replace("o", "u")) |
                    Q(department__name__icontains=department)
                )
        return queryset


@extend_schema(
    tags=["Inspection - Workers"],
    summary="Ishchi ma'lumotlarini ko'rish, yangilash va o'chirish (Admin/Manager)",
)
class WorkerRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = User.objects.filter(role="worker").select_related("face_profile", "department")
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
        queryset = Attendance.objects.select_related("worker").all().order_by("-date", "-check_in_time")
        
        user_id = self.request.query_params.get("user_id")
        phone = self.request.query_params.get("phone")
        is_success = self.request.query_params.get("is_success")
        date = self.request.query_params.get("date")
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")

        if user_id:
            queryset = queryset.filter(worker_id=user_id)
        if phone:
            queryset = queryset.filter(worker__phone__icontains=phone)
        if is_success is not None:
            if is_success.lower() in ["true", "1"]:
                queryset = queryset.filter(check_in_success=True)
            elif is_success.lower() in ["false", "0"]:
                queryset = queryset.filter(check_in_success=False)
        if date:
            queryset = queryset.filter(date=date)
        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)

        return queryset


@extend_schema(
    tags=["Inspection - Attendance"],
    summary="Bitta davomat yozuvi tafsilotlari (Admin/Manager/Worker)",
)
class AttendanceRetrieveView(generics.RetrieveAPIView):
    queryset = Attendance.objects.select_related("worker").all()
    serializer_class = AttendanceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        obj = super().get_object()
        if self.request.user.role == "worker" and obj.worker != self.request.user:
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
        return Attendance.objects.filter(worker=self.request.user).order_by("-date")


from rest_framework import serializers

@extend_schema(
    tags=["Inspection - Attendance"],
    summary="Davomat statistikasi (Admin/Manager)",
    responses={
        200: inline_serializer(
            name='AttendanceStatsResponse',
            fields={
                'date': serializers.DateField(),
                'total_workers': serializers.IntegerField(),
                'active_zones_count': serializers.IntegerField(),
                'today_stats': inline_serializer(
                    name='TodayStatsInfo',
                    fields={
                        'total_checkins': serializers.IntegerField(),
                        'successful_checkins': serializers.IntegerField(),
                        'failed_checkins': serializers.IntegerField(),
                        'unique_workers_checked_in': serializers.IntegerField(),
                        'absent_workers': serializers.IntegerField(),
                    }
                ),
                'overall_stats': inline_serializer(
                    name='OverallStatsInfo',
                    fields={
                        'total_checkins_all_time': serializers.IntegerField(),
                        'successful_checkins_all_time': serializers.IntegerField(),
                    }
                )
            }
        )
    }
)
class AttendanceStatsView(APIView):
    permission_classes = [IsAdminOrManager]

    def get(self, request, *args, **kwargs):
        from django.utils import timezone
        
        today = timezone.localtime().date()
        today_attendances = Attendance.objects.filter(date=today)
        today_total = today_attendances.count()
        today_success = today_attendances.filter(check_in_success=True).count()
        today_failed = today_attendances.filter(check_in_success=False).count()
        
        today_unique_users = today_attendances.values("worker").distinct().count()
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
                "successful_checkins_all_time": Attendance.objects.filter(check_in_success=True).count()
            }
        }
        return Response(data, status=status.HTTP_200_OK)


class AttendanceByDateView(generics.ListAPIView):
    """
    Sana va bo'lim bo'yicha filtrlangan kunlik davomat ro'yxati (Faqat Admin).
    Agar shu kunda hech qanday davomat yozuvi bo'lmasa, bo'sh ro'yxat qaytaradi.
    """
    serializer_class = AttendanceByDateSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_serializer_context(self):
        context = super().get_serializer_context()
        date_param = self.request.query_params.get('date')
        if date_param:
            from django.utils.dateparse import parse_date
            context['date'] = parse_date(date_param)
        else:
            from django.utils import timezone
            context['date'] = timezone.localtime().date()
        return context

    def get_queryset(self):
        queryset = User.objects.filter(role="worker").select_related("department").order_by("-created_at")

        date_param = self.request.query_params.get('date')
        if not date_param:
            from django.utils import timezone
            target_date = timezone.localtime().date()
        else:
            from django.utils.dateparse import parse_date
            target_date = parse_date(date_param)

        # "Agar tanlangan kunda hech qaysi hodim uchun davomat yozuvi bo'lmasa, jadval bo'sh ko'rsatilishi kerak"
        if not Attendance.objects.filter(date=target_date).exists():
            return User.objects.none()

        department = self.request.query_params.get('department')
        if department:
            if department.isdigit():
                queryset = queryset.filter(department_id=int(department))
            else:
                queryset = queryset.filter(
                    Q(department__slug=department) |
                    Q(department__slug=department.replace("u", "o")) |
                    Q(department__slug=department.replace("o", "u")) |
                    Q(department__name__icontains=department)
                )

        return queryset


@extend_schema(
    tags=["Work Schedules"],
    summary="Ish vaqti jadvallari ro'yxati va yangisini yaratish (Faqat Admin)",
)
class WorkScheduleListCreateView(generics.ListCreateAPIView):
    queryset = WorkSchedule.objects.all()
    serializer_class = WorkScheduleSerializer
    permission_classes = [IsAdminUser]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


@extend_schema(
    tags=["Work Schedules"],
    summary="Ish vaqti jadvalini ko'rish, tahrirlash va o'chirish (Faqat Admin)",
)
class WorkScheduleRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = WorkSchedule.objects.all()
    serializer_class = WorkScheduleSerializer
    permission_classes = [IsAdminUser]


@extend_schema(
    tags=["Inspection - Attendance"],
    summary="Face ID orqali ishga kelish va ketishni qayd etish (Xodimlar uchun)",
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "latitude": {"type": "number", "example": 41.311081},
                "longitude": {"type": "number", "example": 69.240562},
            }
        }
    },
    responses={
        200: {
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "check_in_time": {"type": "string", "format": "date-time"},
                "check_out_time": {"type": "string", "format": "date-time"},
                "is_late": {"type": "boolean"},
            }
        },
        400: {"description": "Bugungi davomat allaqachon to'liq belgilangan"}
    }
)
class FaceCheckInOutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if user.role != "worker":
            return Response({"detail": "Faqat xodimlar kirish-chiqish qilishi mumkin."}, status=status.HTTP_403_FORBIDDEN)

        from django.utils import timezone
        today = timezone.localtime().date()
        daily_att, created = DailyAttendance.objects.get_or_create(user=user, date=today)

        # Get work schedule or individual schedule
        start_time = None
        if user.work_start_time:
            start_time = user.work_start_time
        else:
            schedule = None
            if user.department:
                schedule = WorkSchedule.objects.filter(departments=user.department).first()
            if schedule:
                start_time = schedule.start_time

        now_dt = timezone.now()
        now_time = timezone.localtime(now_dt).time()

        # Get or create today's Attendance
        attendance, _ = Attendance.objects.get_or_create(
            worker=user,
            date=today,
        )

        if not daily_att.check_in_time:
            # Check-in
            is_late = False
            if start_time and now_time > start_time:
                is_late = True
            
            daily_att.check_in_time = now_dt
            daily_att.is_late = is_late
            daily_att.save()

            attendance.check_in_time = now_dt
            attendance.check_in_success = True
            attendance.is_late = is_late
            attendance.save()

            msg = "kechikdingiz" if is_late else "muvaffaqiyatli"
            return Response({
                "message": msg,
                "check_in_time": daily_att.check_in_time,
                "is_late": is_late
            }, status=status.HTTP_200_OK)

        elif not daily_att.check_out_time:
            # Check-out
            daily_att.check_out_time = now_dt
            daily_att.save()

            attendance.check_out_time = now_dt
            attendance.check_out_success = True
            attendance.save()

            return Response({
                "message": "muvaffaqiyatli",
                "check_out_time": daily_att.check_out_time
            }, status=status.HTTP_200_OK)

        return Response({"message": "Bugungi davomat allaqachon to'liq belgilangan"}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    tags=["Inspection - Attendance"],
    summary="Xodimning bugungi davomat ma'lumotlari (Jonli hisoblagich uchun)",
    responses={
        200: inline_serializer(
            name='MyAttendanceTodayResponse',
            fields={
                'department': serializers.CharField(allow_null=True),
                'check_in_time': serializers.DateTimeField(allow_null=True),
                'check_out_time': serializers.DateTimeField(allow_null=True),
                'worked_seconds': serializers.IntegerField(),
                'schedule': serializers.CharField(),
                'is_late': serializers.BooleanField(),
            }
        )
    }
)
class MyAttendanceTodayView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.role != "worker":
            return Response({"detail": "Faqat xodimlar uchun."}, status=status.HTTP_403_FORBIDDEN)

        from django.utils import timezone
        today = timezone.localtime().date()
        daily_att = DailyAttendance.objects.filter(user=user, date=today).first()
        
        # Get schedule
        schedule_str = "Ish vaqti belgilanmagan"
        if user.work_start_time and user.work_end_time:
            schedule_str = f"{user.work_start_time.strftime('%H:%M')} — {user.work_end_time.strftime('%H:%M')} (Shaxsiy)"
        else:
            schedule = None
            if user.department:
                schedule = WorkSchedule.objects.filter(departments=user.department).first()
            if schedule:
                schedule_str = f"{schedule.start_time.strftime('%H:%M')} — {schedule.end_time.strftime('%H:%M')}"

        return Response({
            "department": user.department.name if user.department else None,
            "check_in_time": daily_att.check_in_time if daily_att else None,
            "check_out_time": daily_att.check_out_time if daily_att else None,
            "worked_seconds": int(daily_att.worked_duration.total_seconds()) if daily_att and daily_att.worked_duration else 0,
            "schedule": schedule_str,
            "is_late": daily_att.is_late if daily_att else False,
        }, status=status.HTTP_200_OK)


@extend_schema(
    tags=["Inspection - Workers"],
    summary="Admin bosgan xodimning davomat tarixi va statistikasi (ID bo'yicha)",
    responses={
        200: inline_serializer(
            name='WorkerAttendanceDetailResponse',
            fields={
                'worker': inline_serializer(
                    name='WorkerDetailInfo',
                    fields={
                        'id': serializers.IntegerField(),
                        'full_name': serializers.CharField(),
                        'phone': serializers.CharField(),
                        'branch': serializers.CharField(),
                        'branch_display': serializers.CharField(),
                        'department': inline_serializer(
                            name='WorkerDepartmentInfo',
                            fields={
                                'id': serializers.IntegerField(),
                                'name': serializers.CharField(),
                                'code': serializers.CharField(),
                            }
                        ),
                        'balance': serializers.FloatField(),
                        'salary': serializers.FloatField(),
                        'is_active': serializers.BooleanField(),
                        'created_at': serializers.DateTimeField(allow_null=True),
                    }
                ),
                'stats': inline_serializer(
                    name='WorkerAttendanceStats',
                    fields={
                        'total_days_logged': serializers.IntegerField(),
                        'present_days': serializers.IntegerField(),
                        'absent_days': serializers.IntegerField(),
                        'late_days': serializers.IntegerField(),
                        'total_worked_seconds': serializers.IntegerField(),
                        'total_worked_time_display': serializers.CharField(),
                    }
                ),
                'history': inline_serializer(
                    name='WorkerAttendanceHistoryItem',
                    fields={
                        'id': serializers.IntegerField(),
                        'date': serializers.CharField(allow_null=True),
                        'check_in_time': serializers.DateTimeField(allow_null=True),
                        'check_out_time': serializers.DateTimeField(allow_null=True),
                        'is_late': serializers.BooleanField(),
                        'worked_seconds': serializers.IntegerField(),
                    },
                    many=True
                )
            }
        )
    }
)
class WorkerAttendanceDetailView(APIView):
    permission_classes = [IsAdminOrManager]

    def get(self, request, worker_id):
        from django.shortcuts import get_object_or_404
        
        worker = get_object_or_404(User, pk=worker_id, role="worker")
        
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        
        daily_qs = DailyAttendance.objects.filter(user=worker).order_by("-date")
        if start_date:
            daily_qs = daily_qs.filter(date__gte=start_date)
        if end_date:
            daily_qs = daily_qs.filter(date__lte=end_date)
            
        total_days = daily_qs.count()
        present_days = daily_qs.filter(check_in_time__isnull=False).count()
        late_days = daily_qs.filter(is_late=True).count()
        
        total_seconds = 0
        for da in daily_qs:
            duration = da.worked_duration
            if duration:
                total_seconds += int(duration.total_seconds())
                
        total_hours = total_seconds // 3600
        total_minutes = (total_seconds % 3600) // 60
        worked_time_str = f"{total_hours} soat {total_minutes} daqiqa"
        
        history_data = []
        for da in daily_qs:
            history_data.append({
                "id": da.id,
                "date": da.date.strftime("%Y-%m-%d") if da.date else None,
                "check_in_time": da.check_in_time.isoformat() if da.check_in_time else None,
                "check_out_time": da.check_out_time.isoformat() if da.check_out_time else None,
                "is_late": da.is_late,
                "worked_seconds": int(da.worked_duration.total_seconds()) if da.worked_duration else 0
            })
            
        return Response({
            "worker": {
                "id": worker.id,
                "full_name": worker.full_name,
                "phone": worker.phone,
                "branch": worker.branch,
                "branch_display": worker.get_branch_display(),
                "department": {
                    "id": worker.department.id,
                    "name": worker.department.name,
                    "code": worker.department.code
                } if worker.department else None,
                "balance": float(worker.balance),
                "salary": float(worker.salary),
                "is_active": worker.is_active,
                "created_at": worker.created_at.isoformat() if worker.created_at else None
            },
            "stats": {
                "total_days_logged": total_days,
                "present_days": present_days,
                "absent_days": max(0, total_days - present_days),
                "late_days": late_days,
                "total_worked_seconds": total_seconds,
                "total_worked_time_display": worked_time_str
            },
            "history": history_data
        }, status=status.HTTP_200_OK)


@extend_schema(
    tags=["Inspection - Attendance"],
    summary="Davomat Tarixi jadvali (bitta endpoint orqali)",
)
class AttendanceHistoryView(generics.ListAPIView):
    serializer_class = AttendanceSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        return Attendance.objects.select_related('worker').order_by('-date', '-check_in_time')


@extend_schema(
    tags=["Lavozimlar"],
    summary="Barcha lavozimlar ro'yxatini olish va yangi lavozim qo'shish (Faqat Admin qo'sha oladi)",
)
class LavozimListCreateView(generics.ListCreateAPIView):
    queryset = Lavozim.objects.all()

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return LavozimCreateSerializer
        return LavozimSerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdminUser()]
        return [permissions.IsAuthenticated()]


@extend_schema(
    tags=["Lavozimlar"],
    summary="Lavozimni o'chirish yoki tahrirlash (Faqat Admin, standart bo'limlar tahrirlanmaydi/o'chirilmaydi)",
)
class LavozimDeleteView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Lavozim.objects.all()
    serializer_class = LavozimSerializer
    permission_classes = [IsAdminUser]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_default:
            return Response(
                {"error": "Bu standart lavozimni o'chirish taqiqlangan."},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().destroy(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_default:
            return Response(
                {"error": "Bu standart lavozimni tahrirlash taqiqlangan."},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().update(request, *args, **kwargs)


@extend_schema(
    tags=["Inspection - Workers"],
    summary="Ishchilarni qidirish (Admin/Manager/Boss)",
    parameters=[
        OpenApiParameter(name="q", description="Qidiruv kalit so'zi (F.I.O. yoki Telefon)", required=False, type=str),
        OpenApiParameter(name="department", description="Bo'lim/Lavozim ID si yoki nomi", required=False, type=str),
    ]
)
class WorkerSearchView(generics.ListAPIView):
    serializer_class = WorkerDetailSerializer
    permission_classes = [IsAdminOrManager]

    def get_queryset(self):
        queryset = User.objects.filter(role="worker").select_related("face_profile", "department").order_by("-created_at")
        
        q = self.request.query_params.get("q") or self.request.query_params.get("search")
        if q:
            queryset = queryset.filter(
                Q(full_name__icontains=q) | Q(phone__icontains=q)
            )

        department = self.request.query_params.get("department")
        if department:
            if department.isdigit():
                queryset = queryset.filter(department_id=int(department))
            else:
                queryset = queryset.filter(
                    Q(department__slug=department) |
                    Q(department__slug=department.replace("u", "o")) |
                    Q(department__slug=department.replace("o", "u")) |
                    Q(department__name__icontains=department)
                )

        return queryset