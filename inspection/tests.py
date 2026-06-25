from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from unittest.mock import patch

from .models import FaceProfile, WorkZone

SMALL_GIF = (
    b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x00\x00\x00\x21\xf9\x04'
    b'\x01\x0a\x00\x01\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02'
    b'\x02\x4c\x01\x00\x3b'
)


class CheckInTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            phone="+998900000002",
            password="testpass123",
            full_name="Test User",
            role="worker",
        )
        self.face_profile = FaceProfile.objects.create(
            user=self.user,
            encoding=[1.0] * 128,
            photo=SimpleUploadedFile("face.png", SMALL_GIF, content_type="image/gif"),
        )
        # Create an active work zone for geofencing check
        self.zone = WorkZone.objects.create(
            name="Test Zone",
            latitude=41.311081,
            longitude=69.240562,
            radius_meters=100
        )

    @patch('inspection.views.compare_faces_direct')
    def test_anonymous_photo_check_in_success(self, mock_compare_direct):
        # Mock face matching to succeed
        mock_compare_direct.return_value = (True, 0.1)

        response = self.client.post(
            reverse("inspection-check-in"),
            {
                "user_id": self.user.id,
                "photo": SimpleUploadedFile("face.gif", SMALL_GIF, content_type="image/gif"),
                "latitude": 41.311081,
                "longitude": 69.240562,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()["success"])
        self.assertTrue(response.json()["face_verified"])
        self.assertTrue(response.json()["location_verified"])

    @patch('inspection.views.compare_faces_direct')
    @patch('inspection.views.compare_faces')
    def test_anonymous_photo_check_in_fail_face(self, mock_compare, mock_compare_direct):
        # Mock direct face matching to return None (triggering fallback)
        mock_compare_direct.return_value = None
        # Mock fallback to return False (mismatch)
        mock_compare.return_value = (False, 0.9)

        response = self.client.post(
            reverse("inspection-check-in"),
            {
                "user_id": self.user.id,
                "photo": SimpleUploadedFile("face.gif", SMALL_GIF, content_type="image/gif"),
                "latitude": 41.311081,
                "longitude": 69.240562,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(response.json()["success"])
        self.assertFalse(response.json()["face_verified"])

    def test_anonymous_check_in_no_user_id_fails(self):
        # Unauthenticated request without user_id must fail validation
        response = self.client.post(
            reverse("inspection-check-in"),
            {
                "photo": SimpleUploadedFile("face.gif", SMALL_GIF, content_type="image/gif"),
                "latitude": 41.311081,
                "longitude": 69.240562,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        res_data = response.json()
        error_msg = res_data.get("detail", res_data.get("non_field_errors", [""])[0])
        if isinstance(error_msg, list):
            error_msg = error_msg[0]
        self.assertIn("Foydalanuvchini aniqlash", error_msg)
