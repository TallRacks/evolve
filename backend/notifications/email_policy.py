from dataclasses import dataclass

from .models import Notification


@dataclass(frozen=True)
class CategoryPolicy:
    key: str
    label: str
    description: str
    default_in_app: bool = True
    default_email: bool = False
    in_app_disableable: bool = True
    email_disableable: bool = True


CATEGORY_POLICIES = {
    Notification.Category.TEAM: CategoryPolicy(
        Notification.Category.TEAM,
        "Tasks & team",
        "Assignments and team access changes.",
        default_email=True,
    ),
    Notification.Category.BOOKINGS: CategoryPolicy(
        Notification.Category.BOOKINGS, "Bookings", "Important booking workflow changes."
    ),
    Notification.Category.PRODUCTION: CategoryPolicy(
        Notification.Category.PRODUCTION, "Production", "Production readiness and operations."
    ),
    Notification.Category.CALL_SHEETS: CategoryPolicy(
        Notification.Category.CALL_SHEETS,
        "Call sheets",
        "Published operational call sheets.",
        default_email=True,
    ),
    Notification.Category.CONTRACTS: CategoryPolicy(
        Notification.Category.CONTRACTS,
        "Contracts",
        "Contract approvals requiring attention.",
        default_email=True,
    ),
    Notification.Category.FINANCE: CategoryPolicy(
        Notification.Category.FINANCE, "Finance", "Internal finance workflow updates.", default_email=True
    ),
    Notification.Category.SECURITY: CategoryPolicy(
        Notification.Category.SECURITY,
        "Security",
        "Critical account security events.",
        default_email=True,
        in_app_disableable=False,
        email_disableable=False,
    ),
    Notification.Category.MUSIC: CategoryPolicy(
        Notification.Category.MUSIC, "Music", "Release and catalog updates."
    ),
    Notification.Category.MARKETING: CategoryPolicy(
        Notification.Category.MARKETING, "Campaigns", "Campaign and rollout workflow updates."
    ),
    Notification.Category.DOCUMENTS: CategoryPolicy(
        Notification.Category.DOCUMENTS, "Documents", "Document workflow updates."
    ),
    Notification.Category.RIGHTS: CategoryPolicy(
        Notification.Category.RIGHTS, "Rights & royalties", "Rights and royalty workflow updates."
    ),
    Notification.Category.SYSTEM: CategoryPolicy(
        Notification.Category.SYSTEM, "System", "Important Evolve system messages."
    ),
}

EMAIL_NOTIFICATION_TYPES = {
    "task.assigned": "task_assigned",
    "task.reassigned": "task_reassigned",
    "contract.approval_requested": "contract_approval_requested",
    "callsheet.published": "call_sheet_published",
    "invoice.issued": "invoice_issued",
    "invoice.paid": "invoice_paid",
}


def preference_defaults(category):
    policy = CATEGORY_POLICIES[category]
    return policy.default_in_app, policy.default_email
