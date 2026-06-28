import datetime
from django.db.models import Q, OuterRef, Subquery
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from openpyxl import Workbook

from rest_framework import status, permissions, generics, parsers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, OpenApiParameter

from .models import Attendance, FaceProfile
from .services import get_face_encoding
from .api_serializers import EmployeeSerializer, AttendanceDetailSerializer

User = get_user_model()

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 15
    page_size_query_param = 'page_size'
    max_page_size = 100

class IsBossOrAdminOrManager(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ["boss", "admin", "manager"]

def get_date_range(request):
    start_date_str = request.query_params.get('start_date')
    end_date_str = request.query_params.get('end_date')
    today = timezone.localtime().date()
    
    if start_date_str:
        try:
            start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d").date()
        except ValueError:
            start_date = today
    else:
        start_date = today
        
    if end_date_str:
        try:
            end_date = datetime.datetime.strptime(end_date_str, "%Y-%m-%d").date()
        except ValueError:
            end_date = today
    else:
        end_date = today
        
    return start_date, end_date


# ──────────────────────────────────────────────────────────────────────
# 1. Dashboard & Statistics
# ──────────────────────────────────────────────────────────────────────
class DashboardSummaryAPIView(APIView):
    permission_classes = [IsBossOrAdminOrManager]
    
    @extend_schema(
        tags=["Dashboard"],
        summary="Umumiy statistika kartalari ma'lumotlari (Kelgan, Kechikkan, Kelmagan)",
        parameters=[
            OpenApiParameter("start_date", str, description="Boshlanish sanasi (YYYY-MM-DD)", required=False),
            OpenApiParameter("end_date", str, description="Tugash sanasi (YYYY-MM-DD)", required=False),
            OpenApiParameter("branch", str, description="Bo'lim filtri (ichki_dokon, tashqi_dokon, personal)", required=False),
        ]
    )
    def get(self, request):
        start_date, end_date = get_date_range(request)
        branch = request.query_params.get('branch')
        
        # Hozirgi davr statistikasi
        present_count, late_count, absent_count = self.calculate_stats(start_date, end_date, branch)
        
        # O'tgan oyning mos davridagi statistika (o'sish/pasayish foizini hisoblash uchun)
        prev_start_date = start_date - datetime.timedelta(days=30)
        prev_end_date = end_date - datetime.timedelta(days=30)
        prev_present, prev_late, prev_absent = self.calculate_stats(prev_start_date, prev_end_date, branch)
        
        # O'sish foizlari
        present_trend = self.calculate_trend(present_count, prev_present)
        late_trend = self.calculate_trend(late_count, prev_late)
        absent_trend = self.calculate_trend(absent_count, prev_absent)
        
        return Response({
            "present": {
                "count": present_count,
                "trend_percentage": present_trend
            },
            "late": {
                "count": late_count,
                "trend_percentage": late_trend
            },
            "absent": {
                "count": absent_count,
                "trend_percentage": absent_trend
            }
        }, status=status.HTTP_200_OK)
        
    def calculate_stats(self, start_date, end_date, branch):
        workers_qs = User.objects.filter(role="worker", is_active=True)
        if branch:
            workers_qs = workers_qs.filter(branch=branch)
        total_workers_count = workers_qs.count()
        
        successful_att = Attendance.objects.filter(
            check_in_success=True,
            date__range=[start_date, end_date]
        )
        if branch:
            successful_att = successful_att.filter(worker__branch=branch)
            
        # Har bir xodim uchun uning statusini aniqlash
        user_status = {}
        for att in successful_att:
            uid = att.worker_id
            if uid not in user_status:
                user_status[uid] = "late" if att.is_late else "present"
            elif not att.is_late:
                user_status[uid] = "present" # Agar kun davomida bir marta bo'lsa ham vaqtida kelgan bo'lsa
                
        present = sum(1 for status in user_status.values() if status == "present")
        late = sum(1 for status in user_status.values() if status == "late")
        absent = max(0, total_workers_count - len(user_status))
        
        return present, late, absent

    def calculate_trend(self, current, previous):
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return round(((current - previous) / previous) * 100, 1)


class DashboardChartsAPIView(APIView):
    permission_classes = [IsBossOrAdminOrManager]
    
    @extend_schema(
        tags=["Dashboard"],
        summary="Aylanma (Donut) chart uchun bo'limlar kesimida davomat foizlari",
        parameters=[
            OpenApiParameter("start_date", str, description="Boshlanish sanasi (YYYY-MM-DD)", required=False),
            OpenApiParameter("end_date", str, description="Tugash sanasi (YYYY-MM-DD)", required=False),
        ]
    )
    def get(self, request):
        start_date, end_date = get_date_range(request)
        
        branches = [
            ("ichki_dokon", "Ichki Do'kon"),
            ("tashqi_dokon", "Tashqi Do'kon"),
            ("personal", "Personallar")
        ]
        
        results = []
        for branch_code, branch_name in branches:
            total_workers = User.objects.filter(role="worker", is_active=True, branch=branch_code).count()
            
            present_workers = Attendance.objects.filter(
                check_in_success=True,
                worker__branch=branch_code,
                date__range=[start_date, end_date]
            ).values('worker').distinct().count()
            
            percentage = 0.0
            if total_workers > 0:
                percentage = round((present_workers / total_workers) * 100, 1)
                
            results.append({
                "branch": branch_code,
                "name": branch_name,
                "percentage": percentage,
                "present": present_workers,
                "total": total_workers
            })
            
        return Response(results, status=status.HTTP_200_OK)


# ──────────────────────────────────────────────────────────────────────
# 2. Davomat va Face ID loglari
# ──────────────────────────────────────────────────────────────────────
class AttendanceAllAPIView(generics.ListAPIView):
    permission_classes = [IsBossOrAdminOrManager]
    serializer_class = EmployeeSerializer
    pagination_class = StandardResultsSetPagination
    
    @extend_schema(
        tags=["Attendance V1"],
        summary="Asosiy sahifadagi 'Barcha Xodimlar' jadvali",
        parameters=[
            OpenApiParameter("start_date", str, description="Boshlanish sanasi", required=False),
            OpenApiParameter("end_date", str, description="Tugash sanasi", required=False),
            OpenApiParameter("branch", str, description="Bo'lim filtri", required=False),
            OpenApiParameter("search", str, description="Ism yoki telefon raqam bo'yicha qidiruv", required=False),
        ]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        start_date, end_date = get_date_range(self.request)
        branch = self.request.query_params.get('branch')
        search = self.request.query_params.get('search')
        
        latest_checkin = Attendance.objects.filter(
            worker=OuterRef('pk'),
            check_in_success=True,
            date__range=[start_date, end_date]
        ).order_by('-date', '-check_in_time')
        
        queryset = User.objects.filter(role="worker").annotate(
            latest_check_in=Subquery(latest_checkin.values('check_in_time')[:1])
        ).order_by('-created_at')
        
        if branch:
            queryset = queryset.filter(branch=branch)
        if search:
            queryset = queryset.filter(
                Q(full_name__icontains=search) | Q(phone__icontains=search)
            )
            
        return queryset
        
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            data = self.format_response_data(page)
            return self.get_paginated_response(data)
            
        data = self.format_response_data(queryset)
        return Response(data)

    def format_response_data(self, queryset):
        return [
            {
                "id": user.id,
                "full_name": user.full_name,
                "branch": user.branch,
                "branch_display": user.get_branch_display(),
                "phone": user.phone,
                "check_in_time": user.latest_check_in,
                "balance": user.balance,
                "is_active": user.is_active
            } for user in queryset
        ]


class AttendancePresentAPIView(generics.ListAPIView):
    permission_classes = [IsBossOrAdminOrManager]
    serializer_class = AttendanceDetailSerializer
    pagination_class = StandardResultsSetPagination
    
    @extend_schema(
        tags=["Attendance V1"],
        summary="Ishga kelganlar (Vaqtida kelganlar) modal jadvali",
        parameters=[
            OpenApiParameter("start_date", str, description="Sana oralig'i boshlanishi", required=False),
            OpenApiParameter("end_date", str, description="Sana oralig'i tugashi", required=False),
            OpenApiParameter("branch", str, description="Bo'lim filtri", required=False),
            OpenApiParameter("search", str, description="Ism yoki telefon bo'yicha qidiruv", required=False),
        ]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        start_date, end_date = get_date_range(self.request)
        branch = self.request.query_params.get('branch')
        search = self.request.query_params.get('search')
        
        queryset = Attendance.objects.filter(
            check_in_success=True,
            is_late=False,
            date__range=[start_date, end_date]
        ).select_related('worker').order_by('-date', '-check_in_time')
        
        if branch:
            queryset = queryset.filter(worker__branch=branch)
        if search:
            queryset = queryset.filter(
                Q(worker__full_name__icontains=search) | Q(worker__phone__icontains=search)
            )
            
        return queryset


class AttendanceLateAPIView(generics.ListAPIView):
    permission_classes = [IsBossOrAdminOrManager]
    serializer_class = AttendanceDetailSerializer
    pagination_class = StandardResultsSetPagination
    
    @extend_schema(
        tags=["Attendance V1"],
        summary="Ishga kechikib kelganlar modal jadvali",
        parameters=[
            OpenApiParameter("start_date", str, description="Sana oralig'i boshlanishi", required=False),
            OpenApiParameter("end_date", str, description="Sana oralig'i tugashi", required=False),
            OpenApiParameter("branch", str, description="Bo'lim filtri", required=False),
            OpenApiParameter("search", str, description="Ism yoki telefon bo'yicha qidiruv", required=False),
        ]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        start_date, end_date = get_date_range(self.request)
        branch = self.request.query_params.get('branch')
        search = self.request.query_params.get('search')
        
        queryset = Attendance.objects.filter(
            check_in_success=True,
            is_late=True,
            date__range=[start_date, end_date]
        ).select_related('worker').order_by('-date', '-check_in_time')
        
        if branch:
            queryset = queryset.filter(worker__branch=branch)
        if search:
            queryset = queryset.filter(
                Q(worker__full_name__icontains=search) | Q(worker__phone__icontains=search)
            )
            
        return queryset


class AttendanceAbsentAPIView(generics.ListAPIView):
    permission_classes = [IsBossOrAdminOrManager]
    serializer_class = EmployeeSerializer
    pagination_class = StandardResultsSetPagination
    
    @extend_schema(
        tags=["Attendance V1"],
        summary="Ishga kelmagan xodimlar modal jadvali",
        parameters=[
            OpenApiParameter("start_date", str, description="Sana oralig'i boshlanishi", required=False),
            OpenApiParameter("end_date", str, description="Sana oralig'i tugashi", required=False),
            OpenApiParameter("branch", str, description="Bo'lim filtri", required=False),
            OpenApiParameter("search", str, description="Ism yoki telefon bo'yicha qidiruv", required=False),
        ]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        start_date, end_date = get_date_range(self.request)
        branch = self.request.query_params.get('branch')
        search = self.request.query_params.get('search')
        
        present_user_ids = Attendance.objects.filter(
            check_in_success=True,
            date__range=[start_date, end_date]
        ).values_list('worker_id', flat=True).distinct()
        
        queryset = User.objects.filter(role="worker", is_active=True).exclude(
            id__in=present_user_ids
        ).order_by('-created_at')
        
        if branch:
            queryset = queryset.filter(branch=branch)
        if search:
            queryset = queryset.filter(
                Q(full_name__icontains=search) | Q(phone__icontains=search)
            )
            
        return queryset
        
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            data = self.format_response_data(page)
            return self.get_paginated_response(data)
            
        data = self.format_response_data(queryset)
        return Response(data)

    def format_response_data(self, queryset):
        return [
            {
                "id": user.id,
                "full_name": user.full_name,
                "branch": user.branch,
                "branch_display": user.get_branch_display(),
                "phone": user.phone,
                "balance": user.balance,
                "is_active": user.is_active
            } for user in queryset
        ]


# ──────────────────────────────────────────────────────────────────────
# 3. Eksport API (Excel yuklab olish)
# ──────────────────────────────────────────────────────────────────────
class AttendanceExportAPIView(APIView):
    permission_classes = [IsBossOrAdminOrManager]
    
    @extend_schema(
        tags=["Attendance V1"],
        summary="Filtrlangan davomat ro'yxatini Excel (.xlsx) fayli sifatida yuklab olish",
        parameters=[
            OpenApiParameter("status", str, description="Filtlash statusi (all, present, late, absent)", required=False, default="all"),
            OpenApiParameter("branch", str, description="Bo'lim filtri", required=False),
            OpenApiParameter("start_date", str, description="Boshlanish sanasi", required=False),
            OpenApiParameter("end_date", str, description="Tugash sanasi", required=False),
            OpenApiParameter("search", str, description="Ism yoki telefon bo'yicha qidiruv", required=False),
        ]
    )
    def get(self, request):
        start_date, end_date = get_date_range(request)
        status_param = request.query_params.get('status', 'all')
        branch = request.query_params.get('branch')
        search = request.query_params.get('search')
        
        wb = Workbook()
        ws = wb.active
        ws.title = "Davomat Hisoboti"
        
        # Sarlavha yozish
        headers = ["Ism Familiya", "Telefon raqami", "Bo'limi", "Kelgan vaqti", "IP Manzil", "Urinishlar soni", "Kechikkanmi", "Statusi"]
        ws.append(headers)
        
        if status_param == 'present':
            queryset = Attendance.objects.filter(check_in_success=True, is_late=False, date__range=[start_date, end_date])
            if branch: queryset = queryset.filter(worker__branch=branch)
            if search: queryset = queryset.filter(Q(worker__full_name__icontains=search) | Q(worker__phone__icontains=search))
            for att in queryset.select_related('worker'):
                ws.append([att.worker.full_name, att.worker.phone, att.worker.get_branch_display(), att.created_at.strftime('%Y-%m-%d %H:%M'), att.ip_address or "-", att.attempts, "Yo'q", "Vaqtida kelgan"])
        
        elif status_param == 'late':
            queryset = Attendance.objects.filter(check_in_success=True, is_late=True, date__range=[start_date, end_date])
            if branch: queryset = queryset.filter(worker__branch=branch)
            if search: queryset = queryset.filter(Q(worker__full_name__icontains=search) | Q(worker__phone__icontains=search))
            for att in queryset.select_related('worker'):
                ws.append([att.worker.full_name, att.worker.phone, att.worker.get_branch_display(), att.created_at.strftime('%Y-%m-%d %H:%M'), att.ip_address or "-", att.attempts, "Ha", "Kechikkan"])
                
        elif status_param == 'absent':
            present_ids = Attendance.objects.filter(check_in_success=True, date__range=[start_date, end_date]).values_list('worker_id', flat=True).distinct()
            queryset = User.objects.filter(role="worker", is_active=True).exclude(id__in=present_ids)
            if branch: queryset = queryset.filter(branch=branch)
            if search: queryset = queryset.filter(Q(full_name__icontains=search) | Q(phone__icontains=search))
            for user in queryset:
                ws.append([user.full_name, user.phone, user.get_branch_display(), "-", "-", "-", "-", "Kelmagan"])
                
        else: # 'all'
            latest_checkin = Attendance.objects.filter(worker=OuterRef('pk'), check_in_success=True, date__range=[start_date, end_date]).order_by('-date', '-check_in_time')
            queryset = User.objects.filter(role="worker").annotate(
                latest_check_in=Subquery(latest_checkin.values('check_in_time')[:1]),
                latest_is_late=Subquery(latest_checkin.values('is_late')[:1]),
            )
            if branch: queryset = queryset.filter(branch=branch)
            if search: queryset = queryset.filter(Q(full_name__icontains=search) | Q(phone__icontains=search))
            for user in queryset:
                time_str = user.latest_check_in.strftime('%Y-%m-%d %H:%M') if user.latest_check_in else "-"
                is_late_str = "Ha" if user.latest_is_late else ("Yo'q" if user.latest_check_in else "-")
                status_str = "Kechikkan" if user.latest_is_late else ("Vaqtida kelgan" if user.latest_check_in else "Kelmagan")
                ws.append([user.full_name, user.phone, user.get_branch_display(), time_str, "-", 1, is_late_str, status_str])

        # Ustunlar kengligini kontentga qarab moslash
        for col in ws.columns:
            max_len = 0
            for cell in col:
                val_str = str(cell.value or '')
                if len(val_str) > max_len:
                    max_len = len(val_str)
            ws.column_dimensions[col[0].column_letter].width = max(max_len + 3, 10)

        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="shafmet_report_{timezone.localtime().date()}.xlsx"'
        wb.save(response)
        return response


# ──────────────────────────────────────────────────────────────────────
# 4. Xodimlarni boshqarish (Face ID integratsiyasi)
# ──────────────────────────────────────────────────────────────────────
class EmployeeListCreateAPIView(generics.ListAPIView):
    permission_classes = [IsBossOrAdminOrManager]
    serializer_class = EmployeeSerializer
    pagination_class = StandardResultsSetPagination
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]
    
    @extend_schema(
        tags=["Employees V1"],
        summary="Barcha xodimlar ro'yxatini olish (Admin/Manager/Boss)",
        parameters=[
            OpenApiParameter("branch", str, description="Bo'lim filtri (ichki_dokon, tashqi_dokon, personal)", required=False),
            OpenApiParameter("search", str, description="Ism yoki telefon bo'yicha qidiruv", required=False),
        ]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        branch = self.request.query_params.get('branch')
        search = self.request.query_params.get('search')
        queryset = User.objects.filter(role="worker").order_by('-created_at')
        if branch:
            queryset = queryset.filter(branch=branch)
        if search:
            queryset = queryset.filter(
                Q(full_name__icontains=search) | Q(phone__icontains=search)
            )
        return queryset


class EmployeeUploadFaceAPIView(APIView):
    permission_classes = [IsBossOrAdminOrManager]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]
    
    @extend_schema(
        tags=["Employees V1"],
        summary="Xodimning yuz rasmini yuklash va encoding yaratish (Face ID integratsiyasi uchun)",
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "photo": {"type": "string", "format": "binary", "description": "Xodimning yuz rasmi"}
                },
                "required": ["photo"]
            }
        },
        responses={200: {"type": "object", "properties": {"detail": {"type": "string"}, "user_id": {"type": "integer"}, "has_face_profile": {"type": "boolean"}}}}
    )
    def post(self, request, id):
        employee = get_object_or_404(User, pk=id, role="worker")
        photo = request.FILES.get('photo')
        if not photo:
            return Response({"detail": "Yuz rasmi (photo) yuborilishi shart."}, status=status.HTTP_400_BAD_REQUEST)
            
        encoding = get_face_encoding(photo)
        if encoding is None:
            return Response({"detail": "Rasmda yuz aniqlanmadi. Iltimos, aniq yuz rasmi yuklang."}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            face_profile = FaceProfile.objects.get(user=employee)
            face_profile.encoding = encoding
            face_profile.photo = photo
            face_profile.save()
        except FaceProfile.DoesNotExist:
            face_profile = FaceProfile.objects.create(
                user=employee,
                encoding=encoding,
                photo=photo
            )
        
        return Response({
            "detail": "Yuz muvaffaqiyatli saqlandi va encoding yaratildi.",
            "user_id": employee.id,
            "has_face_profile": True
        }, status=status.HTTP_200_OK)
