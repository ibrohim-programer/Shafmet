from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin

class RoleChoices(models.TextChoices):
    BOSS = "boss", "Boss"
    ADMIN = "admin", "Admin"
    MANAGER = "manager", "Manager"
    WORKER = "worker", "Worker"
    
class CustomUserManager(BaseUserManager):
    def create_user(self, phone, password=None , **extra_fields):
        if not phone:
            raise ValueError("Telefon raqam kiritilishi shart")
        phone = str(phone).strip()
        if not phone.startswith("+998"):
            raise ValueError("Telefon raqam +998 bilan boshlanishi shart")
        extra_fields.setdefault("role", RoleChoices.WORKER)
        user = self.model(phone=phone ,**extra_fields)
        user.set_password(password)
        user.save(using = self._db)
        return user
    
    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault("is_staff",True)
        extra_fields.setdefault("is_superuser",True)
        extra_fields.setdefault("role", RoleChoices.ADMIN)
        return self.create_user(phone ,password , **extra_fields)
        

class UserModel(AbstractBaseUser , PermissionsMixin):        
    phone = models.CharField("Telefon raqam", max_length=20, unique=True)
    full_name = models.CharField("To'liq ism", max_length=150)
    role = models.CharField("Rol",max_length=20,choices=RoleChoices.choices,default=RoleChoices.WORKER)
    avatar = models.ImageField("Rasm", upload_to="avatars/", blank=True, null=True)
    branch = models.CharField(
        "Bo'lim",
        max_length=50,
        choices=[
            ("ichki_dokon", "Ichki Do'kon"),
            ("tashqi_dokon", "Tashqi Do'kon"),
            ("personal", "Personal"),
        ],
        default="ichki_dokon",
    )
    salary = models.DecimalField("Oylik ish haqi", max_digits=12, decimal_places=2, default=0.00)
    balance = models.DecimalField("Balans", max_digits=12, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)   
    created_at = models.DateTimeField(auto_now_add=True)

    objects = CustomUserManager()

    USERNAME_FIELD = "phone"        
    REQUIRED_FIELDS = ["full_name"]  
    
    def __str__(self):
        return f"{self.full_name} ({self.get_role_display()})"
    
    @property
    def is_admin(self):
        return self.role == RoleChoices.ADMIN
    
    @property
    def is_boss(self):
        return self.role == RoleChoices.BOSS
    
    @property
    def is_manager(self):
        return self.role == RoleChoices.MANAGER
    
    @property
    def is_worker(self):
        return self.role == RoleChoices.WORKER
    
    class Meta:
        verbose_name        = ("Foydalanuvchi")
        verbose_name_plural = ("Foydalanuvchilar")
        
        

    
