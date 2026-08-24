# Campaigns

Campaign is the organization-owned strategic marketing initiative: what is promoted, why, when, to whom, and through which planned channels. It requires an Artist and may reference one compatible same-organization Release.

## Strategy and lifecycle

Objectives are constrained descriptive values: awareness, pre-save, release launch, audience growth, engagement, streaming, press, live, or other. CampaignChannel records planned channels only and do not integrate external services.

Campaign status is service controlled: draft to planned/cancelled; planned to active/draft/cancelled; active to paused/completed/cancelled; paused to active/cancelled; completed or cancelled to archived. Generic updates and admin forms cannot bypass this graph. Campaign deletion is disabled.

Dates must be ordered. An optional owner is an active Membership whose User and Organization remain active. Release, Artist, owner, and Campaign organization must align.

## Access and surfaces

Workspace routes are `/workspace/campaigns`, `/workspace/campaigns/new`, and `/workspace/campaigns/[id]`. Linked artist users receive a read-only, portal-safe view for their authorized Artists only. Platform routes require a Django superuser. `is_staff` alone grants no access.

`campaign.view`, `campaign.manage`, and `campaign.status.manage` are centralized organization permissions. Important create, update, lifecycle, and channel changes are audited without copying strategic descriptions into audit records.

Integration credentials with `campaign.read` may call `/api/developer/campaigns/`. Responses are organization scoped and omit strategy notes, ownership contact details, tasks, and audit data.

Budgets, ad spend, analytics, social/DSP/email integrations, asset approval, and finances are deferred.
