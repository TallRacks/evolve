import os

os.environ["DJANGO_SECRET_KEY"] = "test-only-secret-key-not-for-production"
os.environ["ALLOWED_HOSTS"] = "testserver,localhost"
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "sqlite:///:memory:")

from .base import *  # noqa: E402,F403

DEBUG = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
ALLOW_TEST_FORCE_LOGIN_WITHOUT_PASSWORD_FRESHNESS = True
