from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from account.serializers import RegisterSerializers
from inspection.serializers import CreateWorkerSerializer

User = get_user_model()


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
