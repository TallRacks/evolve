from django.apps import apps
from django.contrib import admin


def _can_view(request, app_label, model_name):
    model = apps.get_model(app_label, model_name)
    model_admin = admin.site._registry.get(model)
    return bool(model_admin and model_admin.has_view_permission(request))


def finance_overview(request):
    return any(
        _can_view(request, "finance", model)
        for model in ("Invoice", "Payment", "PaymentAllocation")
    )


def finance_invoices(request):
    return _can_view(request, "finance", "Invoice")


def finance_payments(request):
    return _can_view(request, "finance", "Payment")


def finance_allocations(request):
    return _can_view(request, "finance", "PaymentAllocation")


def rights_works(request):
    return _can_view(request, "rights", "Work")


def rights_parties(request):
    return _can_view(request, "rights", "RightsParty")


def master_rights(request):
    return _can_view(request, "rights", "MasterRight")


def publishing_rights(request):
    return _can_view(request, "rights", "PublishingRight")


def royalty_statements(request):
    return _can_view(request, "rights", "RoyaltyStatement")


def royalty_allocations(request):
    return _can_view(request, "rights", "RoyaltyAllocation")


def workflow_tasks(request):
    return _can_view(request, "tasks", "Task")


def workflow_checklists(request):
    return _can_view(request, "tasks", "TaskChecklistItem")


def document_templates(request):
    return _can_view(request, "documents", "DocumentTemplate")


def document_template_sections(request):
    return _can_view(request, "documents", "DocumentTemplateSection")


def security_events(request):
    return _can_view(request, "users", "SecurityEvent")
