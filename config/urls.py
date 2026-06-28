from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from django.contrib import admin
from django.urls import path , include
from django.conf import settings
from django.conf.urls.static import static
from inspection.views import AttendanceByDateView, WorkerAttendanceDetailView, LavozimListCreateView, LavozimDeleteView

urlpatterns = [
    # Amdin
    path('admin/', admin.site.urls),
    
    # Swaggwer
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    # App
    path('account/', include('account.urls')),
    path('notifications/' , include('notifications.urls')),
    path('task/' , include('task_and_assessment.urls')),
    path('api/inspection/' , include('inspection.urls')),
    path('api/attendance/', AttendanceByDateView.as_view(), name='attendance-by-date'),
    path('api/attendance/worker/<int:worker_id>/', WorkerAttendanceDetailView.as_view(), name='worker-attendance-detail'),
    path('api/lavozim/', LavozimListCreateView.as_view(), name='lavozim-list-create'),
    path('api/lavozim/<int:pk>/', LavozimDeleteView.as_view(), name='lavozim-delete'),
    path('api/v1/', include('inspection.api_urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
