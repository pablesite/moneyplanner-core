from pathlib import Path
import os
from datetime import timedelta
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


DEFAULT_DEV_SECRET_KEY = "dev-only-not-for-production-change-me-please-32b"
INSECURE_SECRET_VALUES = {
    "",
    "changeme",
    "dev-insecure-secret",
    DEFAULT_DEV_SECRET_KEY,
}


def validate_secret(name: str, value: str, *, min_length: int = 50) -> None:
    if DEBUG:
        return
    if value in INSECURE_SECRET_VALUES:
        raise ImproperlyConfigured(f"{name} uses an insecure default value.")
    if len(value) < min_length:
        raise ImproperlyConfigured(f"{name} must be at least {min_length} characters long.")


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", DEFAULT_DEV_SECRET_KEY).strip()
DEBUG = env_bool("DJANGO_DEBUG", "0")
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "")
USE_X_FORWARDED_HOST = env_bool("USE_X_FORWARDED_HOST", "0" if DEBUG else "1")

SECURE_PROXY_SSL_HEADER = None
if env_bool("SECURE_PROXY_SSL_HEADER_ENABLED", "0" if DEBUG else "1"):
    SECURE_PROXY_SSL_HEADER = (
        os.getenv("SECURE_PROXY_SSL_HEADER_NAME", "HTTP_X_FORWARDED_PROTO").strip(),
        os.getenv("SECURE_PROXY_SSL_HEADER_VALUE", "https").strip(),
    )

SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", "0" if DEBUG else "1")
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", "0" if DEBUG else "1")
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", "0" if DEBUG else "1")
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "0" if DEBUG else "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", "0" if DEBUG else "1")
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", "0" if DEBUG else "1")
SECURE_CONTENT_TYPE_NOSNIFF = env_bool("SECURE_CONTENT_TYPE_NOSNIFF", "1")
SECURE_REFERRER_POLICY = os.getenv(
    "SECURE_REFERRER_POLICY",
    "same-origin" if DEBUG else "strict-origin-when-cross-origin",
).strip()

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
    "whitenoise.middleware.WhiteNoiseMiddleware",
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
        "NAME": os.getenv("DB_NAME", "core"),
        "USER": os.getenv("DB_USER", "core"),
        "PASSWORD": os.getenv("DB_PASSWORD", "core"),
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
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "")
CORS_ALLOW_CREDENTIALS = True

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ("accounts.authentication.CoreJWTAuthentication",),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_THROTTLE_CLASSES": ("rest_framework.throttling.ScopedRateThrottle",),
    "DEFAULT_THROTTLE_RATES": {
        "auth_login": os.getenv("THROTTLE_AUTH_LOGIN", "20/min"),
        "auth_refresh": os.getenv("THROTTLE_AUTH_REFRESH", "60/min"),
        "auth_mode": os.getenv("THROTTLE_AUTH_MODE", "120/min"),
        "auth_settings": os.getenv("THROTTLE_AUTH_SETTINGS", "120/min"),
        "auth_ops_metrics": os.getenv("THROTTLE_AUTH_OPS_METRICS", "60/min"),
        "auth_link_token": os.getenv("THROTTLE_AUTH_LINK_TOKEN", "30/min"),
        "auth_register": os.getenv("THROTTLE_AUTH_REGISTER", "5/min"),
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "config.exceptions.custom_exception_handler",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "The Arkenstone Core API",
    "DESCRIPTION": "API del core abierto de The Arkenstone.",
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
AUTH_MODE_CORE_LOCAL = env_bool("AUTH_MODE_CORE_LOCAL", "1")
CORE_LINKING_SHARED_SECRET = os.getenv("CORE_LINKING_SHARED_SECRET", "").strip()
CORE_LINKING_TOKEN_MAX_AGE_SECONDS = int(os.getenv("CORE_LINKING_TOKEN_MAX_AGE_SECONDS", "300"))
AUTH_TRANSITION_MODE = os.getenv("AUTH_TRANSITION_MODE", "stable").strip().lower()
AUTH_SESSION_COMPAT_ENABLED = env_bool("AUTH_SESSION_COMPAT_ENABLED", "1")

AUTH_ACCEPT_EXTERNAL_TOKENS = env_bool("AUTH_ACCEPT_EXTERNAL_TOKENS", "0")
EXTERNAL_JWT_ISSUER = os.getenv("EXTERNAL_JWT_ISSUER", "moneyplanner-external")
EXTERNAL_JWT_AUDIENCE = os.getenv("EXTERNAL_JWT_AUDIENCE", "moneyplanner-external-api")
EXTERNAL_JWT_SIGNING_KEY = os.getenv("EXTERNAL_JWT_SIGNING_KEY", SECRET_KEY).strip()

validate_secret("DJANGO_SECRET_KEY", SECRET_KEY)
validate_secret("JWT_SIGNING_KEY", JWT_SIGNING_KEY)
if AUTH_ACCEPT_EXTERNAL_TOKENS:
    validate_secret("EXTERNAL_JWT_SIGNING_KEY", EXTERNAL_JWT_SIGNING_KEY)
if CORE_LINKING_SHARED_SECRET:
    validate_secret("CORE_LINKING_SHARED_SECRET", CORE_LINKING_SHARED_SECRET)
