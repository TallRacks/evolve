import pytest
from django.contrib import admin
from django.contrib.auth.models import Permission
from django.test import RequestFactory
from django.urls import resolve

from config import admin_navigation
from config.settings.base import UNFOLD
from users.models import User

pytestmark = pytest.mark.django_db


def request_for(user):
    request = RequestFactory().get("/admin/")
    request.user = user
    return request


def test_rights_navigation_is_nested_under_finance():
    groups = UNFOLD["SIDEBAR"]["navigation"]
    assert "Rights & Royalties" not in [group["title"] for group in groups]
    finance = next(group for group in groups if group["title"] == "Finance")
    assert finance["collapsible"] is True
    titles = [item["title"] for item in finance["items"]]
    assert titles == [
        "Finance overview",
        "Invoices",
        "Payments",
        "Payment allocations",
        "Rights & Royalties / Works",
        "Rights Parties",
        "Master Rights",
        "Publishing Rights",
        "Royalty Statements",
        "Royalty Allocations",
    ]
    assert all(item.get("permission") for item in finance["items"])
    assert all(resolve(str(item["link"])) for item in finance["items"])


def test_navigation_uses_existing_admin_permissions_without_staff_bypass():
    staff = User.objects.create_user(email="nav-staff@example.invalid", is_staff=True)
    request = request_for(staff)
    assert not admin_navigation.finance_overview(request)
    assert not admin_navigation.rights_works(request)
    assert not admin_navigation.royalty_statements(request)

    finance = User.objects.create_user(email="nav-finance@example.invalid", is_staff=True)
    finance.user_permissions.add(
        Permission.objects.get(content_type__app_label="finance", codename="view_invoice")
    )
    finance_request = request_for(User.objects.get(pk=finance.pk))
    # Finance admin retains its existing platform-superuser-only policy.
    assert not admin_navigation.finance_overview(finance_request)
    assert not admin_navigation.rights_works(finance_request)
    assert not admin_navigation.royalty_statements(finance_request)

    rights = User.objects.create_user(email="nav-rights@example.invalid", is_staff=True)
    rights.user_permissions.add(
        Permission.objects.get(content_type__app_label="rights", codename="view_work")
    )
    rights_request = request_for(User.objects.get(pk=rights.pk))
    assert admin_navigation.rights_works(rights_request)
    assert not admin_navigation.finance_overview(rights_request)
    assert not admin_navigation.royalty_statements(rights_request)
    finance_group = next(
        group
        for group in admin.site.get_sidebar_list(rights_request)
        if group["title"] == "Finance"
    )
    visible = [item["title"] for item in finance_group["items"] if item["has_permission"]]
    assert visible == ["Rights & Royalties / Works"]

    royalties = User.objects.create_user(email="nav-royalties@example.invalid", is_staff=True)
    royalties.user_permissions.add(
        Permission.objects.get(
            content_type__app_label="rights", codename="view_royaltystatement"
        )
    )
    royalties_request = request_for(User.objects.get(pk=royalties.pk))
    assert admin_navigation.royalty_statements(royalties_request)
    assert not admin_navigation.finance_overview(royalties_request)
    assert not admin_navigation.rights_works(royalties_request)


def test_platform_superuser_retains_all_navigation():
    superuser = User.objects.create_superuser(
        email="nav-superuser@example.invalid", password=None
    )
    request = request_for(superuser)
    callbacks = (
        admin_navigation.finance_overview,
        admin_navigation.finance_invoices,
        admin_navigation.finance_payments,
        admin_navigation.finance_allocations,
        admin_navigation.rights_works,
        admin_navigation.rights_parties,
        admin_navigation.master_rights,
        admin_navigation.publishing_rights,
        admin_navigation.royalty_statements,
        admin_navigation.royalty_allocations,
    )
    assert all(callback(request) for callback in callbacks)
