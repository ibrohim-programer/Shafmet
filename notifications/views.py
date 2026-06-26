from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from .models import FCMDevice
from .serializers import FCMDeviceSerializer

@extend_schema(
    tags=["Notifications"],
    summary="FCM Qurilma tokenini ro'yxatdan o'tkazish (Push notification uchun)",
)
class FCMDeviceRegisterView(generics.CreateAPIView):
    serializer_class = FCMDeviceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save()


@extend_schema(
    tags=["Notifications"],
    summary="FCM Qurilma tokenini o'chirish (Push notificationni to'xtatish uchun)",
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "device_token": {"type": "string", "example": "fcm_token_123"}
            },
            "required": ["device_token"]
        }
    },
    responses={200: {"description": "Device token deleted successfully"}}
)
class FCMDeviceUnregisterView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        device_token = request.data.get("device_token")
        if not device_token:
            return Response(
                {"device_token": ["Token kiritilishi shart."]},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        deleted_count, _ = FCMDevice.objects.filter(user=request.user, device_token=device_token).delete()
        if deleted_count > 0:
            return Response({"detail": "Qurilma muvaffaqiyatli o'chirildi."}, status=status.HTTP_200_OK)
        return Response({"detail": "Qurilma topilmadi yoki sizga tegishli emas."}, status=status.HTTP_404_NOT_FOUND)

