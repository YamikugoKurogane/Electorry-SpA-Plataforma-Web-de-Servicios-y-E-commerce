from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone


class Rol(models.TextChoices):
    CLIENTE = "CLIENTE", "Cliente"
    INTERNO = "INTERNO", "Usuario interno"
    ADMIN = "ADMIN", "Administrador"


class UsuarioManager(BaseUserManager):
    use_in_migrations = True

    def _crear(self, email, password, **extra):
        if not email:
            raise ValueError("El correo es obligatorio.")
        usuario = self.model(email=self.normalize_email(email).lower(), **extra)
        if password:
            usuario.set_password(password)
        else:
            usuario.set_unusable_password()
        usuario.save(using=self._db)
        return usuario

    def create_user(self, email, password=None, **extra):
        extra.setdefault("rol", Rol.CLIENTE)
        return self._crear(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("rol", Rol.ADMIN)
        extra["is_superuser"] = True
        extra["is_staff"] = True
        return self._crear(email, password, **extra)


class Usuario(AbstractUser):
    """Usuario único del sistema; el rol determina qué puede hacer (RF-01, RF-10)."""

    username = None
    email = models.EmailField("correo electrónico", unique=True)
    telefono = models.CharField("teléfono", max_length=20, blank=True)
    rol = models.CharField(max_length=10, choices=Rol.choices, default=Rol.CLIENTE, db_index=True)
    acepta_privacidad = models.BooleanField("acepta aviso de privacidad", default=False)
    fecha_privacidad = models.DateTimeField(null=True, blank=True)
    anonimizado = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UsuarioManager()

    class Meta:
        ordering = ["last_name", "first_name"]
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"

    def __str__(self):
        return self.nombre_completo or self.email

    @property
    def nombre_completo(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def es_cliente(self):
        return self.rol == Rol.CLIENTE

    @property
    def es_admin(self):
        return self.rol == Rol.ADMIN

    @property
    def es_personal(self):
        return self.rol in (Rol.ADMIN, Rol.INTERNO)

    def save(self, *args, **kwargs):
        self.email = (self.email or "").lower()
        # Solo los administradores acceden al sitio de administración de Django.
        self.is_staff = self.is_superuser or self.rol == Rol.ADMIN
        if self.acepta_privacidad and not self.fecha_privacidad:
            self.fecha_privacidad = timezone.now()
        super().save(*args, **kwargs)


class IntentoLogin(models.Model):
    """Intentos de inicio de sesión para limitar fuerza bruta (RNF-SEG-01)."""

    email = models.CharField(max_length=254, db_index=True)
    ip = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    fecha = models.DateTimeField(auto_now_add=True, db_index=True)
    exitoso = models.BooleanField(default=False)

    class Meta:
        ordering = ["-fecha"]
