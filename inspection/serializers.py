from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db import transaction

from .models import Attendance, FaceProfile, WorkZone, WorkSchedule, DailyAttendance
from .services import get_face_encoding
from account.models import Lavozim

User = get_user_model()


class LavozimSerializer(serializers.ModelSerializer):
    code = serializers.CharField(source='slug', read_only=True)

    class Meta:
        model = Lavozim
        fields = ["id", "name", "slug", "code", "description", "show_in_diagram", "is_default", "created_at"]

# Compatibility alias
DepartmentSerializer = LavozimSerializer


class CreateWorkerSerializer(serializers.Serializer):
    """Yangi ishchi yaratish — yuz rasmi bilan birga."""
    phone = serializers.CharField(max_length=20)
    full_name = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True)
    photo = serializers.ImageField(write_only=True)
    department = serializers.ChoiceField(choices=[], required=True)
    work_start_time = serializers.TimeField(required=True)
    work_end_time = serializers.TimeField(required=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self.fields['department'].choices = [(dept.id, dept.name) for dept in Lavozim.objects.all()]
        except Exception:
            pass

    def validate_phone(self, value):
        phone = str(value).strip()
        if not phone.startswith("+998"):
            raise serializers.ValidationError("Telefon raqam +998 bilan boshlanishi shart.")
        if User.objects.filter(phone=phone).exists():
            raise serializers.ValidationError(
                "Bu telefon raqam allaqachon ro'yxatdan o'tgan."
            )
        return phone

    def validate_full_name(self, value):
        full_name = str(value).strip()
        if User.objects.filter(full_name=full_name).exists():
            raise serializers.ValidationError(
                "Bu to'liq ism (full_name) allaqachon ro'yxatdan o'tgan."
            )
        return full_name

    def validate_department(self, value):
        try:
            return Lavozim.objects.get(id=int(value))
        except (ValueError, TypeError, Lavozim.DoesNotExist):
            raise serializers.ValidationError("Bunday bo'lim mavjud emas.")

    def create(self, validated_data):
        photo = validated_data["photo"]
        department = validated_data["department"]

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
                department=department,
                work_start_time=validated_data.get("work_start_time"),
                work_end_time=validated_data.get("work_end_time"),
            )
            FaceProfile.objects.create(
                user=user,
                encoding=encoding,
                photo=photo,
            )

        return user

    def to_representation(self, instance):
        request = self.context.get('request')
        photo_url = None
        if hasattr(instance, 'face_profile') and instance.face_profile.photo:
            if request:
                photo_url = request.build_absolute_uri(instance.face_profile.photo.url)
            else:
                photo_url = instance.face_profile.photo.url
        return {
            "id": instance.id,
            "phone": instance.phone,
            "full_name": instance.full_name,
            "role": instance.role,
            "photo": photo_url,
            "photo_url": photo_url,
            "department": DepartmentSerializer(instance.department).data if instance.department else None,
            "work_start_time": instance.work_start_time.strftime("%H:%M:%S") if instance.work_start_time else None,
            "work_end_time": instance.work_end_time.strftime("%H:%M:%S") if instance.work_end_time else None,
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
    attendance_type = serializers.ChoiceField(
        choices=[("in", "In"), ("out", "Out")],
        default="in",
        required=False,
        help_text="Davomat turi (in/out)",
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
    rasm = serializers.SerializerMethodField()
    ism = serializers.CharField(source='worker.full_name')
    sana = serializers.DateField(source='date', format='%Y-%m-%d')

    kelgan_vaqt = serializers.DateTimeField(source='check_in_time', format='%H:%M', allow_null=True)
    turi_kirish = serializers.SerializerMethodField()
    status_kirish = serializers.BooleanField(source='check_in_success')

    ketgan_vaqt = serializers.DateTimeField(source='check_out_time', format='%H:%M', allow_null=True)
    turi_chiqish = serializers.SerializerMethodField()
    status_chiqish = serializers.BooleanField(source='check_out_success', allow_null=True)

    umumiy_soat = serializers.SerializerMethodField()

    class Meta:
        model = Attendance
        fields = ['rasm', 'ism', 'sana', 'kelgan_vaqt', 'turi_kirish', 'status_kirish',
                  'ketgan_vaqt', 'turi_chiqish', 'status_chiqish', 'umumiy_soat']

    def get_rasm(self, obj) -> str:
        request = self.context.get('request')
        if obj.worker.avatar and request:
            return request.build_absolute_uri(obj.worker.avatar.url)
        if hasattr(obj.worker, 'face_profile') and obj.worker.face_profile and obj.worker.face_profile.photo and request:
            return request.build_absolute_uri(obj.worker.face_profile.photo.url)
        return None

    def get_turi_kirish(self, obj) -> str:
        return "Ishda" if obj.check_in_time else None

    def get_turi_chiqish(self, obj) -> str:
        return "Ketgan" if obj.check_out_time else None

    def get_umumiy_soat(self, obj) -> str:
        return obj.total_hours


class WorkerDetailSerializer(serializers.ModelSerializer):
    photo = serializers.ImageField(source='face_profile.photo', read_only=True)
    photo_url = serializers.SerializerMethodField()
    new_photo = serializers.ImageField(write_only=True, required=False, help_text="Yangi yuz rasmi yuklash (ixtiyoriy)")
    password = serializers.CharField(write_only=True, required=False)
    has_face_profile = serializers.SerializerMethodField()
    department = serializers.PrimaryKeyRelatedField(
        queryset=Lavozim.objects.all(),
        required=True,
        help_text="Bo'lim ID si"
    )

    class Meta:
        model = User
        fields = [
            "id",
            "phone",
            "full_name",
            "avatar",
            "role",
            "is_active",
            "photo",
            "photo_url",
            "new_photo",
            "password",
            "has_face_profile",
            "department",
            "work_start_time",
            "work_end_time",
            "created_at",
        ]
        read_only_fields = ["id", "role", "photo", "photo_url", "created_at"]

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.department:
            representation["department"] = DepartmentSerializer(instance.department).data
        else:
            representation["department"] = None
        return representation

    def get_photo_url(self, obj) -> str:
        request = self.context.get('request')
        if hasattr(obj, 'face_profile') and obj.face_profile.photo:
            if request:
                return request.build_absolute_uri(obj.face_profile.photo.url)
            return obj.face_profile.photo.url
        return None

    def get_has_face_profile(self, obj) -> bool:
        return hasattr(obj, 'face_profile')

    def validate_phone(self, value):
        phone = str(value).strip()
        if not phone.startswith("+998"):
            raise serializers.ValidationError("Telefon raqam +998 bilan boshlanishi shart.")
        user_id = self.instance.id if self.instance else None
        if User.objects.exclude(pk=user_id).filter(phone=phone).exists():
            raise serializers.ValidationError("Bu telefon raqam allaqachon ro'yxatdan o'tgan.")
        return phone

    def update(self, instance, validated_data):
        new_photo = validated_data.pop("new_photo", None)
        password = validated_data.pop("password", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.set_password(password)
        instance.save()

        if new_photo:
            encoding = get_face_encoding(new_photo)
            if encoding is None:
                raise serializers.ValidationError(
                    {"new_photo": "Rasmda yuz topilmadi. Iltimos, aniq yuz rasmi yuklang."}
                )
            
            face_profile, created = FaceProfile.objects.get_or_create(user=instance)
            face_profile.encoding = encoding
            face_profile.photo = new_photo
            face_profile.save()

        return instance


class AttendanceByDateSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    full_name = serializers.CharField()
    phone = serializers.CharField()
    branch = serializers.CharField()
    branch_display = serializers.CharField(source='get_branch_display')
    department = DepartmentSerializer()
    check_in_time = serializers.SerializerMethodField()
    balance = serializers.DecimalField(max_digits=12, decimal_places=2)
    activity_percent = serializers.SerializerMethodField()
    is_excused = serializers.SerializerMethodField()
    excuse_reason = serializers.SerializerMethodField()

    def get_check_in_time(self, obj) -> str:
        date = self.context.get('date')
        if not date:
            return None
        att = Attendance.objects.filter(
            worker=obj,
            date=date,
            check_in_success=True
        ).first()
        
        if att and att.check_in_time:
            from django.utils import timezone
            local_time = timezone.localtime(att.check_in_time)
            return local_time.strftime("%H:%M:%S")
        return None

    def get_activity_percent(self, obj) -> str:
        date = self.context.get('date')
        if not date:
            return 0
            
        att = Attendance.objects.filter(
            worker=obj,
            date=date,
            check_in_success=True
        ).first()
        if not att:
            return 0
            
        from task_and_assessment.models import Task
        tasks = Task.objects.filter(assigned_to=obj)
        total_tasks = tasks.count()
        
        has_late = att.is_late
        
        if total_tasks > 0:
            completed_tasks = tasks.filter(status="completed").count()
            task_completion_rate = (completed_tasks / total_tasks) * 100
            
            punctuality_score = 70 if has_late else 100
            
            activity = int(0.6 * task_completion_rate + 0.4 * punctuality_score)
            return min(100, max(0, activity))
        else:
            return 70 if has_late else 100

    def get_is_excused(self, obj) -> bool:
        date = self.context.get('date')
        if not date:
            return False
        att = Attendance.objects.filter(
            worker=obj,
            date=date
        ).first()
        return att.is_excused if att else False

    def get_excuse_reason(self, obj) -> str:
        date = self.context.get('date')
        if not date:
            return None
        att = Attendance.objects.filter(
            worker=obj,
            date=date
        ).first()
        return att.excuse_reason if att else None


class WorkScheduleSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    departments_details = DepartmentSerializer(source='departments', many=True, read_only=True)

    class Meta:
        model = WorkSchedule
        fields = [
            'id',
            'departments',
            'departments_details',
            'start_time',
            'end_time',
            'created_by',
            'created_by_name',
            'created_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_at']


class DailyAttendanceSerializer(serializers.ModelSerializer):
    user_full_name = serializers.CharField(source='user.full_name', read_only=True)
    user_phone = serializers.CharField(source='user.phone', read_only=True)
    department_name = serializers.CharField(source='user.department.name', read_only=True)
    worked_duration_seconds = serializers.SerializerMethodField()

    class Meta:
        model = DailyAttendance
        fields = [
            'id',
            'user',
            'user_full_name',
            'user_phone',
            'department_name',
            'date',
            'check_in_time',
            'check_out_time',
            'is_late',
            'worked_duration_seconds'
        ]
        read_only_fields = fields

    def get_worked_duration_seconds(self, obj):
        duration = obj.worked_duration
        if duration:
            return int(duration.total_seconds())
        return 0


class LavozimCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lavozim
        fields = ['name', 'description', 'show_in_diagram']