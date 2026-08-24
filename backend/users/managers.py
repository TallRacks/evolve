from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    use_in_migrations = True

    @staticmethod
    def normalize_login_email(email: str) -> str:
        return BaseUserManager.normalize_email(email).strip().lower()

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")
        user = self.model(email=self.normalize_login_email(email), **extra_fields)
        user.set_password(password)
        user.full_clean(exclude={"password"})
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superusers must have is_staff=True")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superusers must have is_superuser=True")
        if extra_fields.get("is_active") is not True:
            raise ValueError("Superusers must have is_active=True")
        return self.create_user(email, password, **extra_fields)
