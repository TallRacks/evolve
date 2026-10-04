from types import SimpleNamespace
from uuid import uuid4

import pytest
from rest_framework import serializers

from signing.api.serializers import SigningRequestSerializer


def test_signing_sources_must_match_request_organization():
    organization_id = uuid4()
    serializer = SigningRequestSerializer(
        context={"organization": SimpleNamespace(id=organization_id)}
    )

    with pytest.raises(serializers.ValidationError, match="belong to this organization"):
        serializer.validate(
            {
                "source_document": SimpleNamespace(organization_id=uuid4()),
                "signers": [{"email": "signer@example.com"}],
            }
        )


def test_signing_request_needs_a_source_or_template():
    serializer = SigningRequestSerializer()

    with pytest.raises(serializers.ValidationError, match="source document"):
        serializer.validate({"signers": [{"email": "signer@example.com"}]})
