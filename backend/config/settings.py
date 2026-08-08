"""
Settings do Sistema de Monitoramento de CTOs Lotadas.
Banco: Neon (Postgres serverless) via DATABASE_URL, sslmode=require obrigatório.

Configuração via variáveis de ambiente (.env — ver .env.example):
  DATABASE_URL      string de conexão do Neon
  SECRET_KEY        chave secreta do Django (OBRIGATÓRIA em produção)
  DEBUG             True só em desenvolvimento
  ALLOWED_HOSTS     lista separada por vírgula
  CSRF_TRUSTED_ORIGINS  origens (https://...) para admin/app do técnico
  USE_HTTPS         True se o Django for servido atrás de TLS (ex.: Nginx)
  NOMINATIM_USER_AGENT  usado pelo script de geocodificação
"""
import os
from pathlib import Path
from urllib.parse import urlparse

from decouple import config
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = config("DEBUG", default=False, cast=bool)

SECRET_KEY = config("SECRET_KEY", default="dev-only-troque-em-producao")
if not DEBUG and SECRET_KEY == "dev-only-troque-em-producao":
    raise ImproperlyConfigured("Defina SECRET_KEY no .env para produção!")

ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1").split(",")

# Origens permitidas para POSTs via formulário/browser quando o site está num
# domínio real (ex.: https://sistema.proxxima.com.br). Separe por vírgula.
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in config("CSRF_TRUSTED_ORIGINS", default="").split(",") if o.strip()
]

# True quando o Django está atrás de um proxy/TLS (ex.: Nginx com Let's Encrypt).
USE_HTTPS = config("USE_HTTPS", default=False, cast=bool)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework.authtoken",
    "ctos",
    "api",
]

MIDDLEWARE = [
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
        "DIRS": [BASE_DIR / "templates"],
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

# ---- Banco de dados: SQLite local (dev) ou Postgres/Neon (produção) ----
_db_url = config("DATABASE_URL", default="sqlite:///db.sqlite3")
if _db_url.startswith("sqlite"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    _parsed = urlparse(_db_url)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": _parsed.path.lstrip("/"),
            "USER": _parsed.username,
            "PASSWORD": _parsed.password,
            "HOST": _parsed.hostname,
            "PORT": _parsed.port or 5432,
            "OPTIONS": {"sslmode": "require"},  # Neon exige SSL
            # Reutiliza a conexão entre requisições (handshake SSL + Neon
            # custa ~1-2s; sem isso cada request abre uma conexão nova).
            # CONN_HEALTH_CHECKS detecta conexão morta (compute idle da Neon)
            # e reconecta automaticamente.
            "CONN_MAX_AGE": 300,
            "CONN_HEALTH_CHECKS": True,
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Recife"
USE_I18N = True
USE_TZ = True

# ---- Arquivos estáticos (admin, painel Django) ----
# Em produção o whitenoise serve os estáticos coletados (STATIC_ROOT).
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
WHITENOISE_MAX_AGE = 31536000 if not DEBUG else 0

# Fotos das ocorrências -- armazenamento local (decisão de projeto)
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

# Regra de negócio: threshold de "quase lotada" -- baseado em portas livres
# restantes, não em percentual, para funcionar igual em qualquer capacidade
# de splitter (1x8, 1x16, 1x32...).
LIMITE_PORTAS_LIVRES_QUASE_LOTADA = 2  # <= 2 portas livres = quase_lotada
LIMITE_PORTAS_LIVRES_LOTADA = 0        # 0 portas livres = lotada

NOMINATIM_USER_AGENT = config(
    "NOMINATIM_USER_AGENT",
    default="sistema-ctos-campina-grande/1.0",
)

# ---- Segurança ----
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

if USE_HTTPS:
    # O redirect HTTP→HTTPS fica por conta do Nginx (certbot). Deixamos o
    # SECURE_SSL_REDIRECT do Django desligado para não redirecionar chamadas
    # internas (ex.: dashboard → API via http://127.0.0.1:8000), que virariam
    # um 301 para https://127.0.0.1:8000 e travariam (TLS contra gunicorn HTTP).
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# ---- Logging ----
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": BASE_DIR / "logs" / "app.log",
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 3,
            "formatter": "verbose",
            "encoding": "utf-8",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": config("DJANGO_LOG_LEVEL", default="INFO"),
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": config("DJANGO_LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
    },
}
