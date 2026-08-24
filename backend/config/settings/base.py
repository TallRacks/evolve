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
    "bookings",
    "callsheets",
    "music",
    "campaigns",
    "calendar_app",
    "documents",
    "notifications",
    "contacts",
    "promoters",
    "venues",
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
                        "title": "Calendar events",
                        "icon": "calendar_month",
                        "link": reverse_lazy("admin:calendar_app_calendarevent_changelist"),
                    },
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
                    {
                        "title": "Bookings",
                        "icon": "event_note",
                        "link": reverse_lazy("admin:bookings_booking_changelist"),
                    },
                    {
                        "title": "Booking team assignments",
                        "icon": "groups",
                        "link": reverse_lazy("admin:bookings_bookingteamassignment_changelist"),
                    },
                    {
                        "title": "Booking contact assignments",
                        "icon": "contact_page",
                        "link": reverse_lazy("admin:bookings_bookingcontactassignment_changelist"),
                    },
                    {
                        "title": "Booking status history",
                        "icon": "history",
                        "link": reverse_lazy("admin:bookings_bookingstatushistory_changelist"),
                    },
                    {
                        "title": "Call Sheets",
                        "icon": "description",
                        "link": reverse_lazy("admin:callsheets_callsheet_changelist"),
                    },
                    {
                        "title": "Call Sheet versions",
                        "icon": "history_edu",
                        "link": reverse_lazy("admin:callsheets_callsheetversion_changelist"),
                    },
                    {
                        "title": "Music releases",
                        "icon": "album",
                        "link": reverse_lazy("admin:music_release_changelist"),
                    },
                    {
                        "title": "Music tracks",
                        "icon": "music_note",
                        "link": reverse_lazy("admin:music_track_changelist"),
                    },
                    {
                        "title": "Music credits",
                        "icon": "group",
                        "link": reverse_lazy("admin:music_musiccredit_changelist"),
                    },
                    {
                        "title": "Promoters",
                        "icon": "campaign",
                        "link": reverse_lazy("admin:promoters_promoter_changelist"),
                    },
                    {
                        "title": "Promoter contacts",
                        "icon": "contact_page",
                        "link": reverse_lazy("admin:promoters_promotercontact_changelist"),
                    },
                    {
                        "title": "Venues",
                        "icon": "location_on",
                        "link": reverse_lazy("admin:venues_venue_changelist"),
                    },
                    {
                        "title": "Venue contacts",
                        "icon": "contact_page",
                        "link": reverse_lazy("admin:venues_venuecontact_changelist"),
                    },
                    {
                        "title": "Contacts",
                        "icon": "contacts",
                        "link": reverse_lazy("admin:contacts_contact_changelist"),
                    },
                ],
            },
            {
                "title": "Marketing",
                "collapsible": True,
                "items": [
                    {
                        "title": "Campaigns",
                        "icon": "campaign",
                        "link": reverse_lazy("admin:campaigns_campaign_changelist"),
                    },
                    {
                        "title": "Rollouts",
                        "icon": "view_timeline",
                        "link": reverse_lazy("admin:campaigns_rollout_changelist"),
                    },
                    {
                        "title": "Milestones",
                        "icon": "flag",
                        "link": reverse_lazy("admin:campaigns_rolloutmilestone_changelist"),
                    },
                    {
                        "title": "Tasks",
                        "icon": "task_alt",
                        "link": reverse_lazy("admin:campaigns_rollouttask_changelist"),
                    },
                    {
                        "title": "Channels",
                        "icon": "share",
                        "link": reverse_lazy("admin:campaigns_campaignchannel_changelist"),
                    },
                ],
            },
            {
                "title": "Content & Documents",
                "collapsible": True,
                "items": [
                    {
                        "title": "Documents",
                        "icon": "folder",
                        "link": reverse_lazy("admin:documents_document_changelist"),
                    },
                    {
                        "title": "Document links",
                        "icon": "link",
                        "link": reverse_lazy("admin:documents_documentlink_changelist"),
                    },
                ],
            },
            {
                "title": "Communication",
                "collapsible": True,
                "items": [
                    {
                        "title": "Notifications",
                        "icon": "notifications",
                        "link": reverse_lazy(
                            "admin:notifications_notification_changelist"
                        ),
                    },
                    {
                        "title": "Preferences",
                        "icon": "tune",
                        "link": reverse_lazy(
                            "admin:notifications_notificationpreference_changelist"
                        ),
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
