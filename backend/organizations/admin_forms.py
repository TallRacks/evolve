from django import forms

from .models import Membership
from .ownership import validate_membership_owner_change
from .permissions import all_permissions


class MembershipAdminForm(forms.ModelForm):
    class Meta:
        model = Membership
        fields = ("user", "organization", "role", "permission_overrides", "is_active")

    def clean_permission_overrides(self):
        value = self.cleaned_data.get("permission_overrides") or {}
        if not isinstance(value, dict):
            raise forms.ValidationError("Permission overrides must be an object.")
        allowed = all_permissions()
        for key in ("grant", "deny"):
            values = value.get(key, [])
            if not isinstance(values, list) or any(item not in allowed for item in values):
                raise forms.ValidationError({key: "Use only known permission names."})
        return {"grant": sorted(set(value.get("grant", []))), "deny": sorted(set(value.get("deny", [])))}

    def clean(self):
        cleaned_data = super().clean()
        overrides = cleaned_data.get("permission_overrides", {})
        if cleaned_data.get("role") == Membership.Role.OWNER and overrides:
            self.add_error("permission_overrides", "Owner memberships inherit all permissions and cannot use overrides.")
        if self.instance.pk and not self.errors:
            validate_membership_owner_change(
                self.instance,
                role=cleaned_data.get("role", self.instance.role),
                is_active=cleaned_data.get("is_active", self.instance.is_active),
                user=cleaned_data.get("user", self.instance.user),
                organization=cleaned_data.get("organization", self.instance.organization),
            )
        return cleaned_data
