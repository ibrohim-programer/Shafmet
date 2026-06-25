from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from .models import FaceProfile


class CheckInEmbeddingTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            phone="+998900000001",
            password="testpass123",
            full_name="Test User",
            role="worker",
        )
        self.embedding = [1.0 if i == 0 else 0.0 for i in range(128)]
        self.mismatch_embedding = [0.0 if i == 0 else 1.0 for i in range(128)]
        self.face_profile = FaceProfile.objects.create(
            user=self.user,
            encoding=self.embedding,
            photo=SimpleUploadedFile("face.png", b"fake-image", content_type="image/png"),
        )
        self.client.force_authenticate(user=self.user)

    def test_embedding_match_returns_success(self):
        response = self.client.post(
            reverse("inspection-check-in"),
            {"user_id": self.user.id, "embedding": self.embedding},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()["success"])
        self.assertGreaterEqual(response.json()["similarity"], 0.85)

    def test_embedding_mismatch_returns_unauthorized(self):
        response = self.client.post(
            reverse("inspection-check-in"),
            {"user_id": self.user.id, "embedding": self.mismatch_embedding},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(response.json()["success"])
