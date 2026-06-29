import os
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv
load_dotenv()


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRET_KEY = "n4&=_re9tg9h+r)^*ct(q@scv_&sn5fe&3!y&mo!_a!iltc4%f"
DEBUG = bool(int(os.environ.get("DEBUG", 1)))
DOMAIN = os.environ.get("DOMAIN", "http://localhost:8000")

ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "*").split(",")
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST = os.environ.get("EMAIL_HOST")
EMAIL_HOST_USER = os.environ.get("EMAIL_USER")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_PASS")
DATETIME_FORMAT = "%d/%m/%Y %H:%M:%S"
SEND_EMAIL = bool(int(os.environ.get("SEND_EMAIL", 0)))
REPORT_TRIGGER_TOKEN = os.environ.get("REPORT_TRIGGER_TOKEN", "")

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "storages",
    "assessment.apps.assessmentConfig",
    "rest_framework",
    "simple_history",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
]

ROOT_URLCONF = "assessmentPrishni.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "assessmentPrishni/templates")],
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

WSGI_APPLICATION = "assessmentPrishni.wsgi.application"

# Database
# https://docs.djangoproject.com/en/3.0/ref/settings/#databases
if DEBUG:
    LOG_FILE = "logFile.log"
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql_psycopg2",
            "NAME": os.environ.get("DB_NAME"),
            "USER": os.environ.get("DB_USER"),
            "PASSWORD": os.environ.get("DB_PASS"),
            "HOST": os.environ.get("DB_HOST"),
            "PORT": os.environ.get("DB_PORT"),
        }
    }
    STATIC_URL = "/static/"
    STATIC_ROOT = os.path.join(BASE_DIR, "static")
    MEDIA_URL = "/media/"
else:
    LOG_FILE = os.path.join(os.environ.get("AZURE_LOG_PATH", "/var/log/app-logs/logfile.log"), "logfile.log")   # Default to '/home/LogFiles' if AZURE_LOG_PATH is not set
    STATIC_URL = os.environ.get("AZURESTATICURL", "") + "/"
    MEDIA_URL = os.environ.get("AZUREMEDIAURL", "") + "/"
    STATIC_ROOT = os.path.join(BASE_DIR, "static")
    MEDIA_ROOT = os.path.join(BASE_DIR, "media")
    DEFAULT_FILE_STORAGE = "assessmentPrishni.custom_azure.AzureMediaStorage"
    STATICFILES_STORAGE = "assessmentPrishni.custom_azure.AzureStaticStorage"
    CSRF_TRUSTED_ORIGINS = os.environ.get("DOMAIN", "http://localhost:8000").split(",")
    CSRF_ALLOWED_ORIGINS = CSRF_TRUSTED_ORIGINS
    CORS_ORIGINS_WHITELIST = CSRF_TRUSTED_ORIGINS
    CORS_ALLOWED_ORIGINS = CSRF_TRUSTED_ORIGINS
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql_psycopg2",
            "NAME": os.environ.get("DB_NAME"),
            "USER": os.environ.get("DB_USER"),
            "PASSWORD": os.environ.get("DB_PASSWORD"),
            "HOST": os.environ.get("DB_HOST"),
            "PORT": os.environ.get("DB_PORT"),
        }
    }

# Password validation
# https://docs.djangoproject.com/en/3.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/3.0/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE =  'Asia/Kolkata'

USE_I18N = True

USE_L10N = True

USE_TZ = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler", # Using RotatingFileHandler to manage log file size
            "filename": LOG_FILE,
            "maxBytes": 1024 * 1024 * 15,
            "backupCount": 5,
            "formatter": "app",
        },
    },
    "loggers": {
        "django": {"handlers": ["file"], "level": "INFO", "propagate": True},
    },
    "formatters": {
        "app": {
            "format": (
                u"%(asctime)s [%(levelname)-8s] "
                "(%(module)s.%(funcName)s) %(message)s"
            ),
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
}


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.0/howto/static-files/

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "assessment.User"
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

REPORT_EMAIL_CC = ["anima@prishni.in"]
REPORT_EMAIL_BCC = ["kamal@prishni.in"]
AZURE_QUEUE_CONNECTION = os.environ.get("AZURE_QUEUE_CONNECTION", "")
QUEUE_NAME = os.environ.get("QUEUE_NAME", "testqueue")