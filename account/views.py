from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import generics, parsers, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from rest_framework_simplejwt.views import TokenRefreshView

from core.permissions import IsAdmin, IsAdminOrManager, IsBoss

from .serializers import LoginSerializers, ProfileSerializer, RegisterSerializers, UserAdminSerializer


class RegisterView(APIView):
    permission_classes = [IsAdmin]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    @extend_schema(
        tags=["Accounts"],
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "phone": {"type": "string", "example": "+998901234567"},
                    "password": {"type": "string", "example": "password123"},
                    "full_name": {"type": "string", "example": "Ali Valiyev"},
                    "role": {
                        "type": "string",
                        "enum": ["boss", "admin", "manager"],
                        "example": "manager",
                    },
                    "avatar": {"type": "string", "format": "binary"},
                    "is_active": {"type": "boolean", "example": True},
                },
                "required": ["phone", "password", "full_name", "role"],
            }
        },
        responses={201: RegisterSerializers},
        description="Register a new user account (worker excluded — use inspection endpoint)",
        summary="Create User Account",
    )
    def post(self, request, *args, **kwargs):
        serializer = RegisterSerializers(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(RegisterSerializers(user).data, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=["Accounts"],
        request=LoginSerializers,
        responses={200: RegisterSerializers},
        description="Login to an existing user account",
        summary="Login User Account",
        examples=[
            OpenApiExample(
                "Valid login payload",
                value={"phone": "+998901234567", "password": "password123"},
                request_only=True,
            )
        ],
    )
    def post(self, request, *args, **kwargs):
        serializer = LoginSerializers(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": RegisterSerializers(user, context={"request": request}).data,
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            },
            status=status.HTTP_200_OK,
        )


@extend_schema(
    tags=["Accounts"],
    description=""" View existing user account information 
                    ----------------------------------------------------
                    Mavjud foydalanuvchi hisobigani malumotlarini kuradi""",
    summary="Profile Crud")

class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def get_object(self):
        return self.request.user

@extend_schema(
    tags=["Refresh Token"],
    summary = "Tokenni Yanigilash"
)
class RefreshTokenView(TokenRefreshView):
    serializer_class = TokenRefreshSerializer


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Accounts"],
        request={
            "application/json": {
                "type": "object",
                "properties": {"refresh": {"type": "string"}},
                "required": ["refresh"],
            }
        },
        responses={205: {"description": "Refresh token blacklisted"}},
        description="Logout user by blacklisting refresh token",
        summary="Logout User Account",
    )
    def post(self, request, *args, **kwargs):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"refresh": ["Refresh token kiritilishi shart."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except AttributeError:
            return Response(
                {"detail": "Token blacklist app sozlanmagan."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except TokenError:
            return Response(
                {"refresh": ["Refresh token noto'g'ri yoki eskirgan."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(status=status.HTTP_205_RESET_CONTENT)


@extend_schema(
    tags=["Accounts"],
    summary="Barcha foydalanuvchilar ro'yxati (Admin/Manager/Boss)",
)
class UserListView(generics.ListAPIView):
    queryset = get_user_model().objects.all().order_by("-created_at")
    serializer_class = UserAdminSerializer
    permission_classes = [IsAdminOrManager | IsBoss]

    def get_queryset(self):
        queryset = super().get_queryset()
        role = self.request.query_params.get("role")
        search = self.request.query_params.get("search")
        
        if role:
            queryset = queryset.filter(role=role)
        if search:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(full_name__icontains=search) | Q(phone__icontains=search)
            )
        return queryset


@extend_schema(
    tags=["Accounts"],
    summary="Foydalanuvchini ko'rish, tahrirlash va o'chirish (Admin/Boss)",
)
class UserRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = get_user_model().objects.all()
    serializer_class = UserAdminSerializer
    permission_classes = [IsAdmin | IsBoss]
