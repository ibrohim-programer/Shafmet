from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from unittest.mock import patch

from account.serializers import RegisterSerializers
from inspection.serializers import CreateWorkerSerializer

User = get_user_model()

SMALL_GIF = (
    b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x00\x00\x00\x21\xf9\x04'
    b'\x01\x0a\x00\x01\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02'
    b'\x02\x4c\x01\x00\x3b'
)


class PhoneValidationTests(TestCase):
    def test_register_serializer_requires_998_format(self):
        data = {
            "phone": "900000001",
            "password": "password123",
            "full_name": "Test User",
            "role": "admin",
        }

        serializer = RegisterSerializers(data=data)

        self.assertFalse(serializer.is_valid())
        self.assertIn("phone", serializer.errors)
        self.assertIn("+998", serializer.errors["phone"][0])


class RegisterViewTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            phone="+998901111111",
            password="adminpassword123",
            full_name="Admin User",
            role="admin",
        )

    @patch("inspection.services.get_face_encoding")
    def test_admin_can_register_worker_with_face_photo_url(self, mock_get_face_encoding):
        mock_get_face_encoding.return_value = [0.1] * 128
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.post(
            reverse("register"),
            {
                "phone": "+998902222222",
                "password": "workerpass123",
                "full_name": "Worker User",
                "role": "worker",
                "photo": SimpleUploadedFile("face.gif", SMALL_GIF, content_type="image/gif"),
                "work_start_time": "09:00:00",
                "work_end_time": "18:00:00",
                "is_active": "false",
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["role"], "worker")
        self.assertIsNone(response.data["work_start_time"])
        self.assertIsNone(response.data["work_end_time"])
        self.assertFalse(response.data["is_active"])
        self.assertTrue(response.data["photo_url"].startswith("http://testserver/media/faces/"))

        user = User.objects.get(phone="+998902222222")
        self.assertTrue(hasattr(user, "face_profile"))

    def test_worker_role_requires_photo(self):
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.post(
            reverse("register"),
            {
                "phone": "+998903333333",
                "password": "workerpass123",
                "full_name": "Worker Without Face",
                "role": "worker",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("photo", response.data)

    def test_worker_serializer_requires_998_format(self):
        photo = SimpleUploadedFile("avatar.jpg", b"fake-content", content_type="image/jpeg")
        data = {
            "phone": "900000001",
            "full_name": "Test Worker",
            "password": "password123",
            "photo": photo,
        }

        serializer = CreateWorkerSerializer(data=data)

        self.assertFalse(serializer.is_valid())
        self.assertIn("phone", serializer.errors)
        self.assertIn("+998", serializer.errors["phone"][0])
