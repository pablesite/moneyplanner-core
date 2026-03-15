from pathlib import Path
import os
from datetime import timedelta
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

DEFAULT_DEV_SECRET_KEY = "dev-only-not-for-production-change-me-please-32b"
INSECURE_SECRET_VALUES = {
    "",
    "changeme",
    "dev-insecure-secret",
    DEFAULT_DEV_SECRET_KEY,
}


def validate_secret(name: str, value: str, *, min_length: int = 32) -> None:
    if DEBUG:
        return
    if value in INSECURE_SECRET_VALUES:
        raise ImproperlyConfigured(f"{name} uses an insecure default value.")
    if len(value) < min_length:
        raise ImproperlyConfigured(f"{name} must be at least {min_length} characters long.")


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", DEFAULT_DEV_SECRET_KEY).strip()
DEBUG = os.getenv("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = [
    h.strip() for h in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost").split(",") if h.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "drf_spectacular",
    # apps
    "core",
    "accounting.apps.AccountingConfig",
    "budget.apps.BudgetConfig",
    "accounts.apps.AccountsConfig",
    "memberships.apps.MembershipsConfig",
    "net_worth",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "saas"),
        "USER": os.getenv("DB_USER", "saas"),
        "PASSWORD": os.getenv("DB_PASSWORD", "saas"),
        "HOST": os.getenv("DB_HOST", "db"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-es"
TIME_ZONE = "Europe/Madrid"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()
]
CORS_ALLOW_CREDENTIALS = True

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ("accounts.authentication.CoreSaasJWTAuthentication",),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_THROTTLE_CLASSES": ("rest_framework.throttling.ScopedRateThrottle",),
    "DEFAULT_THROTTLE_RATES": {
        "auth_login": os.getenv("THROTTLE_AUTH_LOGIN", "20/min"),
        "auth_refresh": os.getenv("THROTTLE_AUTH_REFRESH", "60/min"),
        "auth_mode": os.getenv("THROTTLE_AUTH_MODE", "120/min"),
        "auth_settings": os.getenv("THROTTLE_AUTH_SETTINGS", "120/min"),
        "auth_ops_metrics": os.getenv("THROTTLE_AUTH_OPS_METRICS", "60/min"),
        "auth_link_token": os.getenv("THROTTLE_AUTH_LINK_TOKEN", "30/min"),
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "config.exceptions.custom_exception_handler",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "MoneyPlanner Core API",
    "DESCRIPTION": "API del core de MoneyPlanner.",
    "VERSION": "0.19.0",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "SIGNING_KEY": "",
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ISSUER": os.getenv("JWT_ISSUER", "moneyplanner-core"),
    "AUDIENCE": os.getenv("JWT_AUDIENCE", "moneyplanner-core-api"),
}
JWT_SIGNING_KEY = os.getenv("JWT_SIGNING_KEY", SECRET_KEY).strip()
SIMPLE_JWT["SIGNING_KEY"] = JWT_SIGNING_KEY

# Roadmap 03 flag: keep core auth standalone.
AUTH_MODE_CORE_LOCAL = os.getenv("AUTH_MODE_CORE_LOCAL", "1") == "1"
CORE_LINKING_SHARED_SECRET = os.getenv("CORE_LINKING_SHARED_SECRET", "").strip()
CORE_LINKING_TOKEN_MAX_AGE_SECONDS = int(os.getenv("CORE_LINKING_TOKEN_MAX_AGE_SECONDS", "300"))
AUTH_TRANSITION_MODE = os.getenv("AUTH_TRANSITION_MODE", "stable").strip().lower()
AUTH_SESSION_COMPAT_ENABLED = os.getenv("AUTH_SESSION_COMPAT_ENABLED", "1") == "1"

# Hito 05B extension: allow SaaS JWT access in Core while keeping local Core identities.
AUTH_ACCEPT_SAAS_TOKENS = os.getenv("AUTH_ACCEPT_SAAS_TOKENS", "1") == "1"
SAAS_JWT_ISSUER = os.getenv("SAAS_JWT_ISSUER", "moneyplanner-saas")
SAAS_JWT_AUDIENCE = os.getenv("SAAS_JWT_AUDIENCE", "moneyplanner-saas-api")
SAAS_JWT_SIGNING_KEY = os.getenv("SAAS_JWT_SIGNING_KEY", SECRET_KEY).strip()

validate_secret("DJANGO_SECRET_KEY", SECRET_KEY)
validate_secret("JWT_SIGNING_KEY", JWT_SIGNING_KEY)
if AUTH_ACCEPT_SAAS_TOKENS:
    validate_secret("SAAS_JWT_SIGNING_KEY", SAAS_JWT_SIGNING_KEY)
if CORE_LINKING_SHARED_SECRET:
    validate_secret("CORE_LINKING_SHARED_SECRET", CORE_LINKING_SHARED_SECRET)
