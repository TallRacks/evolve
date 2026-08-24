from pathlib import Path

import environ
from django.urls import reverse_lazy

BASE_DIR = Path(__file__).resolve().parents[2]

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
)

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

INSTALLED_APPS = [
    "unfold",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "users",
    "organizations",
    "artists",
    "white_label",
    "audit",
    "core",
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
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {"default": env.db("DATABASE_URL")}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Johannesburg"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
AUTH_USER_MODEL = "users.User"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 8 * 60 * 60
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "users.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}

UNFOLD = {
    "SITE_TITLE": "Evolve administration",
    "SITE_HEADER": "Evolve",
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": [
            {
                "title": "Overview",
                "collapsible": True,
                "items": [
                    {
                        "title": "Dashboard",
                        "icon": "dashboard",
                        "link": reverse_lazy("admin:index"),
                    },
                ],
            },
            {
                "title": "Identity & Access",
                "collapsible": True,
                "items": [
                    {
                        "title": "Users",
                        "icon": "person",
                        "link": reverse_lazy("admin:users_user_changelist"),
                    },
                    {
                        "title": "Organizations",
                        "icon": "business",
                        "link": reverse_lazy("admin:organizations_organization_changelist"),
                    },
                    {
                        "title": "Memberships",
                        "icon": "group",
                        "link": reverse_lazy("admin:organizations_membership_changelist"),
                    },
                    {
                        "title": "Invitations",
                        "icon": "mail",
                        "link": reverse_lazy("admin:organizations_invitation_changelist"),
                    },
                ],
            },
            {
                "title": "Platform",
                "collapsible": True,
                "items": [
                    {
                        "title": "White-label configuration",
                        "icon": "palette",
                        "link": reverse_lazy("admin:white_label_organizationbranding_changelist"),
                    },
                    {
                        "title": "Domains",
                        "icon": "language",
                        "link": reverse_lazy("admin:white_label_organizationdomain_changelist"),
                    },
                    {
                        "title": "API clients",
                        "icon": "key",
                        "link": reverse_lazy("admin:white_label_apiclient_changelist"),
                    },
                    {
                        "title": "API keys",
                        "icon": "vpn_key",
                        "link": reverse_lazy("admin:white_label_apikey_changelist"),
                    },
                ],
            },
            {
                "title": "Operations",
                "collapsible": True,
                "items": [
                    {
                        "title": "Artists",
                        "icon": "person",
                        "link": reverse_lazy("admin:artists_artist_changelist"),
                    },
                    {
                        "title": "Artist team assignments",
                        "icon": "groups",
                        "link": reverse_lazy("admin:artists_artistteamassignment_changelist"),
                    },
                    {
                        "title": "Artist portal links",
                        "icon": "link",
                        "link": reverse_lazy("admin:artists_artistportallink_changelist"),
                    },
                ],
            },
            {
                "title": "Governance",
                "collapsible": True,
                "items": [
                    {
                        "title": "Audit events",
                        "icon": "policy",
                        "link": reverse_lazy("admin:audit_auditevent_changelist"),
                    },
                ],
            },
        ],
    },
}
