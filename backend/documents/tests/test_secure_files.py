from io import BytesIO
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APIClient

from documents.file_validation import sanitize_filename, validate_upload
from documents.models import Document
from integrations.models import StorageProvider
from organizations.models import Membership, Organization
from users.models import User

pytestmark = pytest.mark.django_db


class FakeStorage:
    objects = {}

    def put(self, key, stream, content_type, metadata):
        self.objects[key] = (stream.read(), content_type)
        stream.seek(0)

    def open_stream(self, key):
        from documents.storage import StoredObject

        content, content_type = self.objects[key]
        return StoredObject(BytesIO(content), len(content), content_type)

    def delete(self, key):
        self.objects.pop(key, None)


def setup_access(role=Membership.Role.OWNER, suffix="one"):
    organization = Organization.objects.create(name=f"Org {suffix}", slug=f"org-{suffix}")
    user = User.objects.create_user(
        email=f"owner-{suffix}@example.invalid", password="Secure-test-password-123"
    )
    Membership.objects.create(user=user, organization=organization, role=role)
    provider = StorageProvider.objects.create(
        name=f"Private {suffix}",
        provider_type="s3_compatible",
        is_active=True,
        is_default=True,
        endpoint="https://storage.example.invalid",
        region="test-1",
        bucket=f"evolve-{suffix}",
        path_prefix="private",
        access_key_reference="EVOLVE_STORAGE_TEST_ACCESS_KEY",
        secret_key_reference="EVOLVE_STORAGE_TEST_SECRET_KEY",
        created_by=user,
    )
    return user, organization, provider


def pdf(name="brief.pdf"):
    return SimpleUploadedFile(name, b"%PDF-1.7\nprivate\n", content_type="application/pdf")


def upload(client, organization, file=None):
    return client.post(
        "/api/documents/upload/",
        {
            "organization": str(organization.pk),
            "title": "Private brief",
            "document_type": "other",
            "visibility": "organization",
            "file": file or pdf(),
        },
        format="multipart",
    )


def test_filename_and_content_validation_rejects_traversal_spoofing_and_active_content():
    assert sanitize_filename("../../Q3 brief.pdf") == "Q3 brief.pdf"
    with pytest.raises(ValidationError):
        validate_upload(SimpleUploadedFile("fake.pdf", b"not a pdf"))
    with pytest.raises(ValidationError):
        validate_upload(SimpleUploadedFile("payload.txt", b"<script>alert(1)</script>"))
    with pytest.raises(ValidationError):
        validate_upload(SimpleUploadedFile("vector.svg", b"<svg></svg>"))


@override_settings(EVOLVE_MAX_UPLOAD_BYTES=4)
def test_upload_limit_accepts_exact_boundary_and_rejects_larger_file():
    metadata = validate_upload(SimpleUploadedFile("note.txt", b"1234"))
    assert metadata["file_size"] == 4
    with pytest.raises(ValidationError):
        validate_upload(SimpleUploadedFile("note.txt", b"12345"))


def test_travel_identity_document_names_are_rejected():
    with pytest.raises(ValidationError):
        validate_upload(pdf("artist-passport.pdf"), document_type="travel")


def test_upload_requires_manage_permission_and_configured_storage():
    member, organization, _ = setup_access(Membership.Role.MEMBER)
    client = APIClient()
    client.force_authenticate(member)
    assert upload(client, organization).status_code == 403

    owner = User.objects.create_user(email="other@example.invalid", password="test-password-123")
    Membership.objects.create(user=owner, organization=organization, role=Membership.Role.OWNER)
    client.force_authenticate(owner)
    assert upload(client, organization).status_code == 503


def test_upload_stream_and_version_metadata_are_private_and_audited():
    user, organization, provider = setup_access()
    client = APIClient()
    client.force_authenticate(user)
    backend = FakeStorage()
    with (
        patch("documents.services.default_storage_provider", return_value=provider),
        patch("documents.services.get_storage_backend", return_value=backend),
    ):
        response = upload(client, organization)
    assert response.status_code == 201, response.json()
    payload = response.json()
    assert payload["source_type"] == "stored"
    assert payload["storage_status"] == "available"
    assert payload["checksum"].endswith("...")
    assert "storage_key" not in payload
    assert "checksum_sha256" not in payload
    document = Document.objects.get(pk=payload["id"])
    assert document.storage_key.startswith("private/organizations/")
    assert "brief.pdf" not in document.storage_key

    with patch("documents.api.views.get_storage_backend", return_value=backend):
        download = client.get(
            f"/api/documents/{document.pk}/download/?organization={organization.pk}"
        )
    assert download.status_code == 200
    assert b"".join(download.streaming_content).startswith(b"%PDF-")
    assert download["Cache-Control"] == "private, no-store, max-age=0"
    assert download["X-Content-Type-Options"] == "nosniff"
    assert "attachment" in download["Content-Disposition"]

    with (
        patch("documents.services.default_storage_provider", return_value=provider),
        patch("documents.services.get_storage_backend", return_value=backend),
    ):
        version = client.post(
            f"/api/documents/{document.pk}/versions/upload/",
            {"organization": str(organization.pk), "file": pdf("revision.pdf")},
            format="multipart",
        )
    assert version.status_code == 201, version.json()
    assert version.json()["version_number"] == 2
    assert version.json()["parent_document"] == str(document.pk)


def test_cross_organization_and_ordinary_staff_receive_no_bypass():
    owner, organization, provider = setup_access(suffix="isolation")
    backend = FakeStorage()
    client = APIClient()
    client.force_authenticate(owner)
    with (
        patch("documents.services.default_storage_provider", return_value=provider),
        patch("documents.services.get_storage_backend", return_value=backend),
    ):
        document_id = upload(client, organization).json()["id"]

    other = Organization.objects.create(name="Other", slug="other-secure")
    staff = User.objects.create_user(
        email="staff@example.invalid", password="test-password-123", is_staff=True
    )
    Membership.objects.create(user=staff, organization=other, role=Membership.Role.MEMBER)
    client.force_authenticate(staff)
    response = client.get(f"/api/documents/{document_id}/download/?organization={organization.pk}")
    assert response.status_code == 404


@pytest.mark.django_db(transaction=True)
def test_postgresql_concurrent_version_numbers_are_serialized():
    from threading import Barrier, Thread

    from django.db import close_old_connections, connection

    from documents.services import upload_new_version

    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-lock regression test")
    user, organization, provider = setup_access(suffix="version-race")
    root = Document.objects.create(
        organization=organization,
        uploaded_by=user,
        title="Versioned",
        document_type="other",
        external_url="https://example.invalid/versioned.pdf",
    )
    barrier = Barrier(2)
    versions = []
    failures = []
    backend = FakeStorage()

    def create_revision(index):
        close_old_connections()
        try:
            barrier.wait()
            revision = upload_new_version(
                document=Document.objects.get(pk=root.pk),
                actor=User.objects.get(pk=user.pk),
                file=pdf(f"revision-{index}.pdf"),
            )
            versions.append(revision.version_number)
        except Exception as exc:
            failures.append(type(exc).__name__)
        finally:
            close_old_connections()

    with (
        patch("documents.services.default_storage_provider", return_value=provider),
        patch("documents.services.get_storage_backend", return_value=backend),
    ):
        threads = [Thread(target=create_revision, args=(index,)) for index in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
    assert failures == []
    assert sorted(versions) == [2, 3]
