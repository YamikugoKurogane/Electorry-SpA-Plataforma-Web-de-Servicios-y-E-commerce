"""
Configuración de Electorry SpA.

Toda la configuración dependiente del entorno se lee desde variables de
entorno (RNF-SEG-08, RNF-POR-02, D7). Nunca se guardan secretos en el repo.
"""
import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path):
    """Carga un archivo .env simple (solo en desarrollo; no pisa variables ya definidas)."""
    if not path.exists():
        return
    for linea in path.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


_load_dotenv(BASE_DIR / ".env")


def env(nombre, default=None):
    return os.environ.get(nombre, default)


def env_bool(nombre, default=False):
    valor = os.environ.get(nombre)
    if valor is None:
        return default
    return valor.strip().lower() in {"1", "true", "yes", "si", "sí", "on"}


def env_list(nombre, default=""):
    return [x.strip() for x in env(nombre, default).split(",") if x.strip()]


# ---------------------------------------------------------------- Núcleo
DEBUG = env_bool("DJANGO_DEBUG", False)
TESTING = env_bool("DJANGO_TESTING", False)

SECRET_KEY = env("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if DEBUG or TESTING:
        SECRET_KEY = "insecure-solo-para-desarrollo-no-usar-en-produccion"
    else:
        raise ImproperlyConfigured(
            "Falta DJANGO_SECRET_KEY. Defínela como variable de entorno (RNF-SEG-08)."
        )

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1" if DEBUG else "")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    # Módulos de Electorry (monolito modular, D1)
    "apps.core",
    "apps.usuarios",
    "apps.auditoria",
    "apps.notificaciones",
    "apps.catalogo",
    "apps.solicitudes",
    "apps.cotizaciones",
    "apps.tienda",
    "apps.pagos",
    "apps.reportes",
    "apps.panel",
    "apps.api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.sitio",
            ],
        },
    },
]

# ------------------------------------------------------- Base de datos (D3)
# PostgreSQL en staging/producción (DATABASE_URL). SQLite solo como respaldo
# para desarrollo rápido y pruebas.
DATABASES = {
    "default": dj_database_url.config(
        env="DATABASE_URL",
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=60,
    )
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ------------------------------------------------ Autenticación (D4, RNF-SEG)
AUTH_USER_MODEL = "usuarios.Usuario"
LOGIN_URL = "usuarios:login"
LOGIN_REDIRECT_URL = "core:inicio"
LOGOUT_REDIRECT_URL = "core:inicio"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Límite de intentos de inicio de sesión (RNF-SEG-01)
LOGIN_MAX_INTENTOS = int(env("LOGIN_MAX_INTENTOS", "5"))
LOGIN_MAX_INTENTOS_IP = int(env("LOGIN_MAX_INTENTOS_IP", "30"))
LOGIN_VENTANA_MINUTOS = int(env("LOGIN_VENTANA_MINUTOS", "15"))
# Activar solo si hay un proxy de confianza (Nginx) delante de Gunicorn.
USE_X_FORWARDED_FOR = env_bool("USE_X_FORWARDED_FOR", False)

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 24  # 1 día
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"

# ------------------------------------------------ Seguridad en producción (RNF-SEG-05)
if not DEBUG and not TESTING:
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(env("DJANGO_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = False
    SILENCED_SYSTEM_CHECKS = ["security.W021"]  # preload es opcional
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_REDIRECT_EXEMPT = [r"^salud/$"]  # healthcheck interno por HTTP
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# ---------------------------------------------------- Internacionalización
LANGUAGE_CODE = "es-cl"
TIME_ZONE = "America/Santiago"
USE_I18N = True
USE_TZ = True
USE_THOUSAND_SEPARATOR = True

# ------------------------------------------------- Estáticos y archivos (D6)
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "media/"
MEDIA_ROOT = Path(env("MEDIA_ROOT", str(BASE_DIR / "media")))
# Los adjuntos de solicitudes viven en MEDIA_ROOT/adjuntos y NUNCA se sirven
# directamente: se entregan mediante una vista que verifica propietario/rol.
# Para migrar a almacenamiento externo basta con sobrescribir STORAGES["default"].

# Adjuntos (RNF-SEG-04, EC-10)
ADJUNTO_MAX_BYTES = int(env("ADJUNTO_MAX_BYTES", str(5 * 1024 * 1024)))
ADJUNTOS_MAX_CANTIDAD = int(env("ADJUNTOS_MAX_CANTIDAD", "5"))
ADJUNTO_EXTENSIONES = ("jpg", "jpeg", "png", "pdf")
DATA_UPLOAD_MAX_NUMBER_FILES = 10
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

# ---------------------------------------------------------- Correo (D8)
EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend"
    if (DEBUG or TESTING)
    else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = env("EMAIL_HOST", "localhost")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_TIMEOUT = int(env("EMAIL_TIMEOUT", "10"))  # timeout: una caída del SMTP no bloquea
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "Electorry SpA <no-reply@electorry.cl>")
NOTIFICACION_MAX_INTENTOS = int(env("NOTIFICACION_MAX_INTENTOS", "5"))
# Correo interno que recibe avisos de nuevas solicitudes/ventas
CORREO_AVISOS_INTERNOS = env("CORREO_AVISOS_INTERNOS", "")

# ---------------------------------------------------- Negocio / integraciones
IVA_PORCENTAJE = int(env("IVA_PORCENTAJE", "19"))
EMPRESA = {
    "nombre": "Electorry SpA",
    "eslogan": "Servicios y productos eléctricos para hogares y empresas",
    "email": env("EMPRESA_EMAIL", "contacto@electorry.cl"),
    "telefono": env("EMPRESA_TELEFONO", "+56 9 0000 0000"),
    "whatsapp": env("EMPRESA_WHATSAPP", ""),  # solo dígitos, ej: 56900000000
    "direccion": env("EMPRESA_DIRECCION", "Chile"),
}

# Pasarela de pago (D5). Valores: "sandbox" | "webpay"
PAYMENT_GATEWAY = env("PAYMENT_GATEWAY", "sandbox")
# El sandbox simula pagos: no debe quedar activo en producción por accidente.
PAYMENT_SANDBOX_PERMITIDO = DEBUG or TESTING or env_bool("PAYMENT_SANDBOX_PERMITIDO", False)
PAYMENT_TIMEOUT = int(env("PAYMENT_TIMEOUT", "10"))
WEBPAY_BASE_URL = env("WEBPAY_BASE_URL", "https://webpay3gint.transbank.cl")
WEBPAY_COMMERCE_CODE = env("WEBPAY_COMMERCE_CODE", "597055555532")  # código público de integración
WEBPAY_API_SECRET = env(
    "WEBPAY_API_SECRET",
    "579B532A7440BB0C9079DED94D31EA1615BACEB56610332264630D42D0A36B1C",  # secreto público de integración
)

# ---------------------------------------------------------------- API (DRF)
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.AnonRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"anon": "120/min"},
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}

# ------------------------------------------------------------- Logging (RNF-FIA-01)
LOG_DIR = env("LOG_DIR", "")
_handlers = {"console": {"class": "logging.StreamHandler", "formatter": "simple"}}
_root_handlers = ["console"]
if LOG_DIR:
    Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
    _handlers["archivo"] = {
        "class": "logging.handlers.RotatingFileHandler",
        "filename": str(Path(LOG_DIR) / "electorry.log"),
        "maxBytes": 5 * 1024 * 1024,
        "backupCount": 5,
        "formatter": "simple",
        "encoding": "utf-8",
    }
    _root_handlers.append("archivo")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "{asctime} {levelname} {name} {message}", "style": "{"}},
    "handlers": _handlers,
    "loggers": {
        "django": {"handlers": _root_handlers, "level": "INFO"},
        "django.request": {"handlers": _root_handlers, "level": "WARNING", "propagate": False},
        "electorry": {"handlers": _root_handlers, "level": "INFO", "propagate": False},
    },
}

if TESTING:
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
