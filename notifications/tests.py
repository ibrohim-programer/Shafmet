from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from .models import FCMDevice

class NotificationAPITests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            phone="+998901234567",
            password="password123",
            full_name="Ali Valiyev",
            role="worker",
        )
        self.client.force_authenticate(user=self.user)

    def test_register_device_token(self):
        url = reverse("fcm-device-register")
        data = {
            "device_token": "test_fcm_token_123",
            "device_type": "android"
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(FCMDevice.objects.count(), 1)
        
        device = FCMDevice.objects.first()
        self.assertEqual(device.user, self.user)
        self.assertEqual(device.device_token, "test_fcm_token_123")
        self.assertEqual(device.device_type, "android")

    def test_register_same_token_reassigns_to_new_user(self):
        # Register token for user1
        url = reverse("fcm-device-register")
        self.client.post(url, {"device_token": "shared_token", "device_type": "ios"}, format="json")
        
        # Create and auth user2
        user2 = get_user_model().objects.create_user(
            phone="+998907654321",
            password="password123",
            full_name="Bobur Karimov",
            role="worker",
        )
        self.client.force_authenticate(user=user2)
        
        # Register same token for user2
        response = self.client.post(url, {"device_token": "shared_token", "device_type": "ios"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify the token is now assigned to user2 and removed from user1
        self.assertEqual(FCMDevice.objects.count(), 1)
        device = FCMDevice.objects.first()
        self.assertEqual(device.user, user2)
        self.assertEqual(device.device_token, "shared_token")

    def test_unregister_device_token(self):
        # Register first
        device = FCMDevice.objects.create(
            user=self.user,
            device_token="token_to_remove",
            device_type="web"
        )
        
        url = reverse("fcm-device-unregister")
        response = self.client.post(url, {"device_token": "token_to_remove"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(FCMDevice.objects.count(), 0)

