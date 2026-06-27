from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from unittest.mock import patch

from .models import FaceProfile, WorkZone, Attendance, WorkSchedule, DailyAttendance
from account.models import Department

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


class FaceProfileTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            phone="+998900000003",
            password="testpass123",
            full_name="Face Profile User",
            role="worker",
        )

    @patch('inspection.services.get_face_encoding')
    def test_face_profile_auto_encoding_on_clean(self, mock_get_encoding):
        mock_get_encoding.return_value = [0.5] * 128
        
        # Create FaceProfile without encoding, should automatically populate
        profile = FaceProfile(
            user=self.user,
            photo=SimpleUploadedFile("face.png", SMALL_GIF, content_type="image/gif")
        )
        profile.clean()
        profile.save()
        
        self.assertEqual(profile.encoding, [0.5] * 128)
        mock_get_encoding.assert_called_once()

    @patch('inspection.services.get_face_encoding')
    def test_face_profile_validation_error_when_no_face_detected(self, mock_get_encoding):
        mock_get_encoding.return_value = None
        
        profile = FaceProfile(
            user=self.user,
            photo=SimpleUploadedFile("face.png", SMALL_GIF, content_type="image/gif")
        )
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            profile.clean()


class DashboardAndAttendanceAPIV1Tests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = get_user_model().objects.create_superuser(
            phone="+998901234567",
            password="adminpassword123",
            full_name="Admin Adminov",
        )
        self.client.force_authenticate(user=self.admin_user)
        
        self.worker = get_user_model().objects.create_user(
            phone="+998909876543",
            password="workerpassword123",
            full_name="Worker Ali",
            branch="ichki_dokon",
            salary=5000000.0,
            balance=100000.0,
        )
        # Create an attendance log
        self.attendance = Attendance.objects.create(
            user=self.worker,
            attendance_type="in",
            latitude=41.311081,
            longitude=69.240562,
            distance_meters=10.0,
            face_verified=True,
            location_verified=True,
            is_success=True,
            is_late=False,
            attempts=1,
            ip_address="192.168.1.10"
        )
        
    def test_dashboard_summary(self):
        response = self.client.get(reverse("v1-dashboard-summary"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("present", response.data)
        self.assertIn("late", response.data)
        self.assertIn("absent", response.data)

    def test_dashboard_charts(self):
        response = self.client.get(reverse("v1-dashboard-charts"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3) # ichki_dokon, tashqi_dokon, personal

    def test_attendance_all(self):
        response = self.client.get(reverse("v1-attendance-all"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data) # paginated

    def test_attendance_present(self):
        response = self.client.get(reverse("v1-attendance-present"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)

    def test_attendance_late(self):
        response = self.client.get(reverse("v1-attendance-late"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)

    def test_attendance_absent(self):
        response = self.client.get(reverse("v1-attendance-absent"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)

    def test_attendance_export(self):
        response = self.client.get(reverse("v1-attendance-export"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    def test_employee_list_create(self):
        # List
        response = self.client.get(reverse("v1-employees-list-create"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        
        # Create
        new_employee_data = {
            "phone": "+998901239876",
            "full_name": "New Employee",
            "branch": "tashqi_dokon",
            "salary": 6000000.0,
            "balance": 0.0
        }
        response = self.client.post(reverse("v1-employees-list-create"), new_employee_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["full_name"], "New Employee")

    @patch('inspection.api_views.get_face_encoding')
    def test_employee_upload_face(self, mock_get_encoding):
        mock_get_encoding.return_value = [0.2] * 128
        
        photo = SimpleUploadedFile("face.png", SMALL_GIF, content_type="image/gif")
        response = self.client.post(
            reverse("v1-employees-upload-face", kwargs={"id": self.worker.id}),
            {"photo": photo},
            format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["has_face_profile"])


class WorkerDepartmentTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.dept_ichki, _ = Department.objects.get_or_create(code="ichki_dokon", defaults={"name": "Ichki do'kon ishchisi"})
        self.dept_tashqi, _ = Department.objects.get_or_create(code="tashqi_dokon", defaults={"name": "Tashqi do'kon ishchisi"})
        
        self.admin_user = get_user_model().objects.create_user(
            phone="+998901234568",
            password="adminpassword123",
            full_name="Admin Adminov",
            role="admin",
        )
        self.boss_user = get_user_model().objects.create_user(
            phone="+998901234569",
            password="bosspassword123",
            full_name="Boss Bossov",
            role="boss",
        )

    @patch('inspection.serializers.get_face_encoding')
    def test_admin_can_create_worker_with_department(self, mock_encoding):
        mock_encoding.return_value = [0.1] * 128
        self.client.force_authenticate(user=self.admin_user)
        
        photo = SimpleUploadedFile("face.png", SMALL_GIF, content_type="image/gif")
        data = {
            "phone": "+998991112233",
            "full_name": "Asror Aliyev",
            "password": "workerpass123",
            "photo": photo,
            "department": self.dept_ichki.id
        }
        
        response = self.client.post(reverse("inspection-create-worker"), data, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["phone"], "+998991112233")
        self.assertEqual(response.data["department"]["code"], "ichki_dokon")
        self.assertIsNotNone(response.data.get("photo"))
        self.assertTrue(response.data["photo"].startswith("http://"))
        self.assertEqual(response.data["photo"], response.data["photo_url"])

    @patch('inspection.serializers.get_face_encoding')
    def test_boss_cannot_create_worker(self, mock_encoding):
        mock_encoding.return_value = [0.1] * 128
        self.client.force_authenticate(user=self.boss_user)
        
        photo = SimpleUploadedFile("face.png", SMALL_GIF, content_type="image/gif")
        data = {
            "phone": "+998991112244",
            "full_name": "Asror Aliyev",
            "password": "workerpass123",
            "photo": photo,
            "department": self.dept_ichki.id
        }
        
        response = self.client.post(reverse("inspection-create-worker"), data, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_workers_filtered_by_department(self):
        w1 = get_user_model().objects.create_user(
            phone="+998992223344",
            password="workerpass123",
            full_name="Worker One",
            role="worker",
            department=self.dept_ichki
        )
        w2 = get_user_model().objects.create_user(
            phone="+998992223355",
            password="workerpass123",
            full_name="Worker Two",
            role="worker",
            department=self.dept_tashqi
        )
        
        self.client.force_authenticate(user=self.admin_user)
        
        response = self.client.get(reverse("inspection-worker-list"), {"department": "ichki_dokon"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        phones = [worker["phone"] for worker in response.data]
        self.assertIn("+998992223344", phones)
        self.assertNotIn("+998992223355", phones)

        response = self.client.get(reverse("inspection-worker-list"), {"department": str(self.dept_tashqi.id)})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        phones = [worker["phone"] for worker in response.data]
        self.assertNotIn("+998992223344", phones)
        self.assertIn("+998992223355", phones)


class AttendanceByDateTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.dept_ichki, _ = Department.objects.get_or_create(code="ichki_dokon", defaults={"name": "Ichki do'kon ishchisi"})
        self.dept_tashqi, _ = Department.objects.get_or_create(code="tashqi_dokon", defaults={"name": "Tashqi do'kon ishchisi"})
        
        self.admin_user = get_user_model().objects.create_user(
            phone="+998901234568",
            password="adminpassword123",
            full_name="Admin Adminov",
            role="admin",
        )
        self.worker1 = get_user_model().objects.create_user(
            phone="+998992223344",
            password="workerpass123",
            full_name="Worker One",
            role="worker",
            department=self.dept_ichki,
            balance=1000.0,
        )
        self.worker2 = get_user_model().objects.create_user(
            phone="+998992223355",
            password="workerpass123",
            full_name="Worker Two",
            role="worker",
            department=self.dept_tashqi,
            balance=2000.0,
        )
        self.client.force_authenticate(user=self.admin_user)

    def test_attendance_by_date_empty_if_no_logs(self):
        response = self.client.get(reverse("attendance-by-date"), {"date": "2025-04-22"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_attendance_by_date_returns_workers_if_logs_exist(self):
        import datetime
        from django.utils import timezone
        
        target_date = datetime.date(2025, 4, 22)
        att = Attendance.objects.create(
            user=self.worker1,
            attendance_type="in",
            latitude=41.311081,
            longitude=69.240562,
            distance_meters=10.0,
            face_verified=True,
            location_verified=True,
            is_success=True,
            is_late=False,
        )
        naive_dt = datetime.datetime.combine(target_date, datetime.time(9, 30, 0))
        target_dt = timezone.make_aware(naive_dt)
        Attendance.objects.filter(id=att.id).update(created_at=target_dt)

        response = self.client.get(reverse("attendance-by-date"), {"date": "2025-04-22"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(len(response.data) > 0)
        
        response_filtered = self.client.get(reverse("attendance-by-date"), {"date": "2025-04-22", "department": "ichki_dokon"})
        self.assertEqual(response_filtered.status_code, status.HTTP_200_OK)
        phones = [w["phone"] for w in response_filtered.data]
        self.assertIn("+998992223344", phones)
        self.assertNotIn("+998992223355", phones)


class WorkScheduleAndDailyAttendanceTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.dept_ichki, _ = Department.objects.get_or_create(code="ichki_dokon", defaults={"name": "Ichki do'kon ishchisi"})
        
        self.admin_user = get_user_model().objects.create_user(
            phone="+998901234568",
            password="adminpassword123",
            full_name="Admin Adminov",
            role="admin",
        )
        self.worker = get_user_model().objects.create_user(
            phone="+998992223344",
            password="workerpass123",
            full_name="Worker One",
            role="worker",
            department=self.dept_ichki,
        )

    def test_admin_can_create_schedule(self):
        self.client.force_authenticate(user=self.admin_user)
        data = {
            "departments": [self.dept_ichki.id],
            "start_time": "08:00:00",
            "end_time": "18:00:00"
        }
        response = self.client.post(reverse("inspection-schedules"), data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(WorkSchedule.objects.count(), 1)

    def test_worker_cannot_create_schedule(self):
        self.client.force_authenticate(user=self.worker)
        data = {
            "departments": [self.dept_ichki.id],
            "start_time": "08:00:00",
            "end_time": "18:00:00"
        }
        response = self.client.post(reverse("inspection-schedules"), data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_face_check_in_out_and_live_stats(self):
        # 1. Create a work schedule starting at 09:00:00
        schedule = WorkSchedule.objects.create(
            start_time="09:00:00",
            end_time="18:00:00"
        )
        schedule.departments.add(self.dept_ichki)

        # 2. Worker check-in
        self.client.force_authenticate(user=self.worker)
        response = self.client.post(reverse("inspection-face-check-in-out"), {"latitude": 41.3, "longitude": 69.2})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("check_in_time", response.data)

        # Check today's stats (live dashboard)
        response_stats = self.client.get(reverse("inspection-my-attendance-today"))
        self.assertEqual(response_stats.status_code, status.HTTP_200_OK)
        self.assertEqual(response_stats.data["department"], "Ichki do'kon ishchisi")
        self.assertIsNotNone(response_stats.data["check_in_time"])
        self.assertIsNone(response_stats.data["check_out_time"])

        # 3. Worker check-out
        response_out = self.client.post(reverse("inspection-face-check-in-out"), {"latitude": 41.3, "longitude": 69.2})
        self.assertEqual(response_out.status_code, status.HTTP_200_OK)
        self.assertIn("check_out_time", response_out.data)

        # Check today's stats again
        response_stats_out = self.client.get(reverse("inspection-my-attendance-today"))
        self.assertEqual(response_stats_out.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response_stats_out.data["check_out_time"])

    def test_worker_attendance_detail_by_id(self):
        # Create schedule and checks
        schedule = WorkSchedule.objects.create(
            start_time="09:00:00",
            end_time="18:00:00"
        )
        schedule.departments.add(self.dept_ichki)

        # Worker check-in/out
        self.client.force_authenticate(user=self.worker)
        self.client.post(reverse("inspection-face-check-in-out"), {"latitude": 41.3, "longitude": 69.2})
        self.client.post(reverse("inspection-face-check-in-out"), {"latitude": 41.3, "longitude": 69.2})

        # Admin gets worker details & stats by ID
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(reverse("worker-attendance-detail", kwargs={"worker_id": self.worker.id}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["worker"]["id"], self.worker.id)
        self.assertEqual(response.data["stats"]["total_days_logged"], 1)
        self.assertEqual(len(response.data["history"]), 1)

