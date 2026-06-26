from rest_framework import serializers
from .models import FCMDevice

class FCMDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = FCMDevice
        fields = ["id", "device_token", "device_type", "created_at"]
        read_only_fields = ["id", "created_at"]
        extra_kwargs = {
            "device_token": {
                "validators": []  # Disable default unique validation to handle token reallocation in create()
            }
        }

    def create(self, validated_data):
        user = self.context["request"].user
        device_token = validated_data["device_token"]
        
        # Agar token boshqa userda bo'lsa, o'chiramiz va joriy userga biriktiramiz
        FCMDevice.objects.filter(device_token=device_token).delete()
        
        device, created = FCMDevice.objects.get_or_create(
            user=user,
            device_token=device_token,
            defaults={"device_type": validated_data.get("device_type")}
        )
        if not created and "device_type" in validated_data:
            device.device_type = validated_data["device_type"]
            device.save()
            
        return device
