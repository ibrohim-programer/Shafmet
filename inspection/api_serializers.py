from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Attendance

User = get_user_model()

class EmployeeSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    branch_display = serializers.CharField(source='get_branch_display', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 
            'phone', 
            'full_name', 
            'branch', 
            'branch_display', 
            'salary', 
            'balance', 
            'avatar', 
            'password', 
            'is_active', 
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def validate_phone(self, value):
        phone = str(value).strip()
        if not phone.startswith("+998"):
            raise serializers.ValidationError("Telefon raqam +998 bilan boshlanishi shart.")
        
        # Check uniqueness, excluding current instance if updating
        qs = User.objects.filter(phone=phone)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Bu telefon raqam allaqachon ro'yxatdan o'tgan.")
        return phone

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        if not password:
            password = "Shafmet2026!"
        
        user = User.objects.create_user(
            phone=validated_data['phone'],
            password=password,
            full_name=validated_data['full_name'],
            branch=validated_data.get('branch', 'ichki_dokon'),
            salary=validated_data.get('salary', 0.0),
            balance=validated_data.get('balance', 0.0),
            avatar=validated_data.get('avatar', None),
            role="worker"
        )
        return user


class UserSummarySerializer(serializers.ModelSerializer):
    branch_display = serializers.CharField(source='get_branch_display', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'phone', 'full_name', 'branch', 'branch_display']


class AttendanceDetailSerializer(serializers.ModelSerializer):
    user = UserSummarySerializer(read_only=True)

    class Meta:
        model = Attendance
        fields = [
            'id', 
            'user', 
            'attendance_type', 
            'latitude', 
            'longitude', 
            'distance_meters', 
            'face_verified', 
            'location_verified', 
            'is_success', 
            'ip_address', 
            'attempts', 
            'is_late', 
            'created_at'
        ]
