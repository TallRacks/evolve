import pytest

from audit.services import record_event
from contracts.models import Contract
from organizations.models import Membership, Organization
from tasks.services import create_task
from users.models import User

pytestmark = pytest.mark.django_db


def test_activity_hides_task_linked_to_protected_contract(client):
    organization = Organization.objects.create(name="Activity Org", slug="activity-org")
    owner = User.objects.create_user(email="owner@activity.invalid", password=None)
    member = User.objects.create_user(email="member@activity.invalid", password=None)
    Membership.objects.create(user=owner, organization=organization, role=Membership.Role.OWNER)
    Membership.objects.create(user=member, organization=organization, role=Membership.Role.MEMBER)
    contract = Contract.objects.create(
        organization=organization,
        title="Private agreement",
        contract_type=Contract.Type.MANAGEMENT,
        created_by=owner,
    )
    protected = create_task(
        actor=owner,
        organization=organization,
        data={"title": "Private legal follow-up", "contract": contract},
    )
    visible = create_task(
        actor=owner, organization=organization, data={"title": "General follow-up"}
    )
    record_event(
        actor=owner,
        organization=organization,
        action="task.updated",
        resource=protected,
        description="Private legal follow-up updated.",
    )
    client.force_login(member)
    response = client.get("/api/activity/", {"organization_id": organization.id})
    assert response.status_code == 200
    resource_ids = {item["resource_id"] for item in response.json()}
    assert str(visible.id) in resource_ids
    assert str(protected.id) not in resource_ids
    assert "Private legal" not in str(response.json())
