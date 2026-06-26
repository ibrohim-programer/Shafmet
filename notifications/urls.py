from django.urls import path
from .views import FCMDeviceRegisterView, FCMDeviceUnregisterView

urlpatterns = [
    path("devices/register/", FCMDeviceRegisterView.as_view(), name="fcm-device-register"),
    path("devices/unregister/", FCMDeviceUnregisterView.as_view(), name="fcm-device-unregister"),
]