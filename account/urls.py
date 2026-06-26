from django.urls import path

from .views import (
    LoginView,
    LogoutView,
    ProfileView,
    RefreshTokenView,
    RegisterView,
    UserListView,
    UserRetrieveUpdateDestroyView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("token/refresh/", RefreshTokenView.as_view(), name="token_refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("users/", UserListView.as_view(), name="user-list"),
    path("users/<int:pk>/", UserRetrieveUpdateDestroyView.as_view(), name="user-detail"),
]
