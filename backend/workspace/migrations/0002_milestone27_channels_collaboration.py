import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


LEGACY_TABLES = {
    "workspace_actionrequest": "workspace_actionrequest_legacy_m26",
    "workspace_automationexecution": "workspace_automationexecution_legacy_m26",
    "workspace_automationrule": "workspace_automationrule_legacy_m26",
    "workspace_inboundmessage": "workspace_inboundmessage_legacy_m26",
    "workspace_messagingconnector": "workspace_messagingconnector_legacy_m26",
    "workspace_messagingidentity": "workspace_messagingidentity_legacy_m26",
}

LEGACY_COLUMNS = {
    "workspace_automationrule": {
        "created_at", "updated_at", "id", "name", "trigger_key", "trigger_config",
        "action_key", "action_config", "is_active", "created_by_id", "organization_id",
    },
    "workspace_actionrequest": {
        "created_at", "updated_at", "id", "channel", "action_key", "risk_level",
        "validated_payload", "status", "confirmation_code_hash", "expires_at",
        "executed_at", "result_summary", "idempotency_key", "actor_id",
        "organization_id", "conversation_id",
    },
    "workspace_automationexecution": {
        "id", "trigger_key", "entity_type", "entity_id", "status", "safe_result",
        "started_at", "completed_at", "rule_id",
    },
    "workspace_inboundmessage": {
        "id", "provider_event_id", "sender_identifier_hash", "provider_thread_id_hash",
        "status", "message_kind", "safe_response", "received_at", "processed_at",
        "connector_id",
    },
    "workspace_messagingconnector": {
        "created_at", "updated_at", "id", "channel", "provider", "name",
        "display_identifier", "token_secret_reference", "webhook_secret_reference",
        "is_active", "status", "last_tested_at", "created_by_id",
    },
    "workspace_messagingidentity": {
        "created_at", "updated_at", "id", "channel", "provider_identifier_hash",
        "status", "verification_code_hash", "verification_expires_at", "verified_at",
        "last_used_at", "active_organization_id", "user_id",
    },
}

CANONICAL_COLUMNS = {
    "workspace_actionrequest": {
        "created_at", "updated_at", "id", "channel", "action_key", "risk",
        "validated_payload", "status", "confirmation_hash", "expires_at", "executed_at",
        "result_summary", "idempotency_key", "actor_id", "organization_id",
    },
    "workspace_automationexecution": {
        "created_at", "updated_at", "id", "event_key", "correlation_id", "depth",
        "status", "result_summary", "idempotency_key", "automation_id", "organization_id",
    },
    "workspace_inboundmessage": {
        "created_at", "updated_at", "id", "provider_message_id", "channel", "sender_address",
        "subject", "body_text", "has_attachments", "event_type", "organization_id",
        "connector_id", "identity_id",
    },
    "workspace_messagingconnector": {
        "created_at", "updated_at", "id", "provider_type", "name", "is_active", "is_default",
        "display_name", "display_phone", "webhook_status", "access_token_reference",
        "signing_secret_reference", "verification_token_reference", "created_by_id", "organization_id",
    },
    "workspace_messagingidentity": {
        "created_at", "updated_at", "id", "provider_subject", "display_address", "is_verified",
        "revoked_at", "active_context_id", "connector_id", "organization_id", "user_id",
    },
}


def _rename_legacy_indexes(cursor, connection, table_name):
    cursor.execute(
        "SELECT idx.relname FROM pg_class AS tbl "
        "JOIN pg_index AS ind ON ind.indrelid = tbl.oid "
        "JOIN pg_class AS idx ON idx.oid = ind.indexrelid "
        "JOIN pg_namespace AS ns ON ns.oid = tbl.relnamespace "
        "WHERE ns.nspname = 'public' AND tbl.relname = %s",
        [table_name],
    )
    for (index_name,) in cursor.fetchall():
        archive_index_name = f"{index_name[:47]}_legacy_m26"
        cursor.execute("SELECT to_regclass(%s)", [f"public.{archive_index_name}"])
        if cursor.fetchone()[0] is not None:
            raise RuntimeError(
                f"Workspace reconciliation is non-colliding failure: "
                f"index {archive_index_name} already exists."
            )
        cursor.execute(
            f"ALTER INDEX {connection.ops.quote_name(index_name)} "
            f"RENAME TO {connection.ops.quote_name(archive_index_name)}"
        )


def reconcile_milestone26_workspace_tables(apps, schema_editor):
    """Verify and archive documented legacy relations before canonical creation."""
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return
    existing = set(connection.introspection.table_names())
    quote = connection.ops.quote_name
    with connection.cursor() as cursor:
        for table_name, archive_name in LEGACY_TABLES.items():
            if table_name not in existing:
                continue
            if archive_name in existing:
                raise RuntimeError(
                    f"Workspace reconciliation aborted: both {table_name} and {archive_name} exist."
                )
            columns = {column.name for column in connection.introspection.get_table_description(cursor, table_name)}
            if columns == CANONICAL_COLUMNS.get(table_name):
                continue
            if columns != LEGACY_COLUMNS[table_name]:
                raise RuntimeError(
                    f"Workspace reconciliation aborted: {table_name} has unexpected columns; "
                    f"expected the documented Milestone 26 schema, found {sorted(columns)}."
                )
            _rename_legacy_indexes(cursor, connection, table_name)
            cursor.execute(f"ALTER TABLE {quote(table_name)} RENAME TO {quote(archive_name)}")


def ensure_missing_0001_workspace_models(apps, schema_editor):
    """Restore relations omitted physically when workspace.0001 was recorded."""
    for model_name in ("AIProviderConfig", "Automation", "ActionRequest"):
        model = apps.get_model("workspace", model_name)
        if model._meta.db_table not in schema_editor.connection.introspection.table_names():
            schema_editor.create_model(model)


class EnsureCreateModel(migrations.CreateModel):
    """Create a canonical table only when it is absent from the drifted database."""
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        model = to_state.apps.get_model(app_label, self.name)
        if model._meta.db_table not in schema_editor.connection.introspection.table_names():
            schema_editor.create_model(model)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        model = from_state.apps.get_model(app_label, self.name)
        if model._meta.db_table in schema_editor.connection.introspection.table_names():
            schema_editor.delete_model(model)


class EnsureAddConstraint(migrations.AddConstraint):
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        model = to_state.apps.get_model(app_label, self.model_name)
        with schema_editor.connection.cursor() as cursor:
            constraints = schema_editor.connection.introspection.get_constraints(cursor, model._meta.db_table)
        if self.constraint.name not in constraints:
            schema_editor.add_constraint(model, self.constraint)


def reverse_reconcile_milestone26_workspace_tables(apps, schema_editor):
    # The archive tables are intentionally retained for data preservation.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("workspace", "0001_initial"),
        ("organizations", "0002_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(
            reconcile_milestone26_workspace_tables,
            reverse_code=reverse_reconcile_milestone26_workspace_tables,
        ),
        migrations.RunPython(ensure_missing_0001_workspace_models),
        EnsureCreateModel(
            name="AutomationExecution",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("event_key", models.CharField(max_length=80)),
                ("correlation_id", models.UUIDField()),
                ("depth", models.PositiveSmallIntegerField(default=0)),
                ("status", models.CharField(choices=[("executed", "Executed"), ("failed", "Failed"), ("skipped", "Skipped")], max_length=16)),
                ("result_summary", models.CharField(blank=True, max_length=500)),
                ("idempotency_key", models.CharField(max_length=180, unique=True)),
                ("automation", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="executions", to="workspace.automation")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="organizations.organization")),
            ],
        ),
        EnsureCreateModel(
            name="Comment",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("context_type", models.CharField(choices=[("task", "Task"), ("booking", "Booking"), ("campaign", "Campaign"), ("production", "Production")], max_length=20)),
                ("context_id", models.UUIDField()),
                ("body", models.TextField(max_length=5000)),
                ("edited_at", models.DateTimeField(blank=True, null=True)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                ("author", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="comments", to=settings.AUTH_USER_MODEL)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="comments", to="organizations.organization")),
            ],
        ),
        EnsureCreateModel(
            name="MessagingConnector",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("provider_type", models.CharField(choices=[("whatsapp", "WhatsApp Business"), ("email", "Inbound email")], max_length=20)),
                ("name", models.CharField(max_length=120)),
                ("is_active", models.BooleanField(default=False)),
                ("is_default", models.BooleanField(default=False)),
                ("display_name", models.CharField(blank=True, max_length=120)),
                ("display_phone", models.CharField(blank=True, max_length=40)),
                ("webhook_status", models.CharField(choices=[("not_configured", "Not configured"), ("healthy", "Healthy"), ("failed", "Failed")], default="not_configured", max_length=24)),
                ("access_token_reference", models.CharField(blank=True, max_length=110)),
                ("signing_secret_reference", models.CharField(blank=True, max_length=110)),
                ("verification_token_reference", models.CharField(blank=True, max_length=110)),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("organization", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="messaging_connectors", to="organizations.organization")),
            ],
        ),
        EnsureCreateModel(
            name="ChannelVerification",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("channel", models.CharField(max_length=20)), ("code_hash", models.CharField(max_length=64)),
                ("expires_at", models.DateTimeField()), ("used_at", models.DateTimeField(blank=True, null=True)),
                ("provider_subject", models.CharField(blank=True, max_length=180)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="organizations.organization")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="channel_verifications", to=settings.AUTH_USER_MODEL)),
                ("connector", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="verifications", to="workspace.messagingconnector")),
            ],
        ),
        EnsureCreateModel(
            name="MessagingIdentity",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("provider_subject", models.CharField(max_length=180)), ("display_address", models.CharField(blank=True, max_length=180)),
                ("is_verified", models.BooleanField(default=False)), ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("active_context", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="active_messaging_contexts", to="organizations.organization")),
                ("connector", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="identities", to="workspace.messagingconnector")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="messaging_identities", to="organizations.organization")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="messaging_identities", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        EnsureCreateModel(
            name="InboundMessage",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("provider_message_id", models.CharField(max_length=220)), ("channel", models.CharField(choices=[("whatsapp", "WhatsApp"), ("email", "Email")], max_length=20)),
                ("sender_address", models.CharField(max_length=180)), ("subject", models.CharField(blank=True, max_length=220)),
                ("body_text", models.TextField(blank=True, max_length=10000)), ("has_attachments", models.BooleanField(default=False)), ("event_type", models.CharField(max_length=80)),
                ("organization", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="organizations.organization")),
                ("connector", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="inbound_messages", to="workspace.messagingconnector")),
                ("identity", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="messages", to="workspace.messagingidentity")),
            ],
        ),
        EnsureCreateModel(
            name="CommentMention",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("comment", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="mentions", to="workspace.comment")),
                ("membership", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="comment_mentions", to="organizations.membership")),
            ],
            options={"constraints": [models.UniqueConstraint(fields=("comment", "membership"), name="unique_comment_mention")]},
        ),
        EnsureAddConstraint(
            model_name="messagingconnector",
            constraint=models.UniqueConstraint(condition=models.Q(is_default=True), fields=("organization", "provider_type", "is_default"), name="one_default_messaging_connector"),
        ),
        EnsureAddConstraint(
            model_name="messagingidentity",
            constraint=models.UniqueConstraint(fields=("connector", "provider_subject"), name="unique_provider_identity"),
        ),
        EnsureAddConstraint(
            model_name="inboundmessage",
            constraint=models.UniqueConstraint(fields=("connector", "provider_message_id"), name="unique_inbound_provider_message"),
        ),
    ]
