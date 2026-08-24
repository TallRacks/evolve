from django.contrib.auth.forms import UserChangeForm

from organizations.ownership import validate_user_deactivation

from .models import User


class OwnerSafeUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        if self.instance.pk and not self.errors:
            validate_user_deactivation(
                self.instance,
                is_active=cleaned_data.get("is_active", self.instance.is_active),
            )
        return cleaned_data
