from django import forms

from .models import Membership
from .ownership import validate_membership_owner_change


class MembershipAdminForm(forms.ModelForm):
    class Meta:
        model = Membership
        fields = ("user", "organization", "role", "is_active")

    def clean(self):
        cleaned_data = super().clean()
        if self.instance.pk and not self.errors:
            validate_membership_owner_change(
                self.instance,
                role=cleaned_data.get("role", self.instance.role),
                is_active=cleaned_data.get("is_active", self.instance.is_active),
                user=cleaned_data.get("user", self.instance.user),
                organization=cleaned_data.get("organization", self.instance.organization),
            )
        return cleaned_data
