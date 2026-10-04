from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from artists.models import Artist
from campaigns.models import (
    Campaign,
    CampaignAsset,
    CampaignChannel,
    CampaignResponsibility,
    Rollout,
    RolloutMilestone,
    RolloutTask,
    RolloutTaskDependency,
)
from campaigns.selectors import activity, campaigns_for_user, portal_campaigns, rollouts_for_user
from campaigns.services import (
    CAMPAIGN_TRANSITIONS,
    add_channel,
    add_dependency,
    assign_responsibility,
    complete_task,
    create_campaign,
    create_milestone,
    create_rollout,
    create_task,
    remove_channel,
    remove_dependency,
    remove_milestone,
    remove_responsibility,
    require,
    transition_campaign,
    transition_rollout,
    transition_task,
    update_campaign,
    update_milestone,
    update_rollout,
    update_task,
)
from music.models import Release
from organizations.api.permissions import PlatformSuperuser
from organizations.models import Membership, Organization
from organizations.selectors import organizations_for_user
from white_label.services import authenticate_api_key

from .serializers import (
    CampaignDetailSerializer,
    CampaignResponsibilitySerializer,
    CampaignResponsibilityWriteSerializer,
    CampaignAssetSerializer,
    CampaignSummarySerializer,
    CampaignWriteSerializer,
    ChannelSerializer,
    DeveloperCampaignSerializer,
    DeveloperRolloutSerializer,
    MilestoneSerializer,
    PortalCampaignSerializer,
    RolloutDetailSerializer,
    RolloutSummarySerializer,
    RolloutWriteSerializer,
    StatusSerializer,
    TaskSerializer,
)


def valid(call):
    try:
        return call()
    except DjangoValidationError as e:
        raise ValidationError(e.message_dict if hasattr(e, "message_dict") else e.messages) from e


def org_for(user, pk):
    return get_object_or_404(
        Organization.objects.filter(pk__in=organizations_for_user(user).values("pk")), pk=pk
    )


def campaign_qs():
    return Campaign.objects.select_related(
        "organization", "artist", "release", "owner_membership__user"
    ).prefetch_related("rollouts__tasks", "responsibilities__membership__user")


def rollout_qs():
    return Rollout.objects.select_related(
        "organization", "campaign", "campaign__artist", "owner_membership__user"
    ).prefetch_related("tasks", "milestones")


def scoped_campaign(user, pk):
    return get_object_or_404(
        campaign_qs().filter(pk__in=campaigns_for_user(user).values("pk")), pk=pk
    )


def scoped_rollout(user, pk):
    return get_object_or_404(
        rollout_qs().filter(pk__in=rollouts_for_user(user).values("pk")), pk=pk
    )


def event_data(obj):
    return [
        {
            "id": e.id,
            "action": e.action,
            "description": e.description,
            "actor": e.actor.email if e.actor else None,
            "created_at": e.created_at,
        }
        for e in activity(obj)
    ]


def filter_campaigns(queryset, request):
    search = request.query_params.get("search")
    if search:
        queryset = queryset.filter(
            Q(name__icontains=search) | Q(artist__stage_name__icontains=search)
        )
    for parameter, field in (
        ("organization", "organization_id"),
        ("artist", "artist_id"),
        ("release", "release_id"),
        ("status", "status"),
        ("objective", "objective"),
        ("priority", "priority"),
        ("owner", "owner_membership_id"),
    ):
        if request.query_params.get(parameter):
            queryset = queryset.filter(**{field: request.query_params[parameter]})
    if request.query_params.get("date_from"):
        queryset = queryset.filter(end_date__gte=request.query_params["date_from"])
    if request.query_params.get("date_to"):
        queryset = queryset.filter(start_date__lte=request.query_params["date_to"])
    return queryset


def filter_rollouts(queryset, request):
    for parameter, field in (
        ("organization", "organization_id"),
        ("campaign", "campaign_id"),
        ("status", "status"),
    ):
        if request.query_params.get(parameter):
            queryset = queryset.filter(**{field: request.query_params[parameter]})
    if request.query_params.get("date_from"):
        queryset = queryset.filter(end_date__gte=request.query_params["date_from"])
    if request.query_params.get("date_to"):
        queryset = queryset.filter(start_date__lte=request.query_params["date_to"])
    return queryset


def campaign_data(obj):
    obj.activity = event_data(obj)
    obj.allowed_transitions = sorted(CAMPAIGN_TRANSITIONS[obj.status])
    return CampaignDetailSerializer(obj).data


def rollout_data(obj):
    obj.activity = event_data(obj)
    return RolloutDetailSerializer(obj).data


def relation(data, org, key, model, required=False):
    pk = data.pop(key, None)
    if not pk and not required:
        return None
    return get_object_or_404(model, pk=pk, organization=org)


def membership(data, org, key):
    pk = data.pop(key, None)
    return (
        get_object_or_404(
            Membership.objects.active(), pk=pk, organization=org, user__is_active=True
        )
        if pk
        else None
    )


class CampaignListView(APIView):
    def get(self, r):
        org = org_for(r.user, r.query_params.get("organization_id"))
        require(r.user, org, "campaign.view")
        qs = campaign_qs().filter(organization=org)
        q = r.query_params.get("search")
        qs = qs.filter(Q(name__icontains=q) | Q(artist__stage_name__icontains=q)) if q else qs
        for p, f in (
            ("artist", "artist_id"),
            ("release", "release_id"),
            ("status", "status"),
            ("objective", "objective"),
            ("priority", "priority"),
            ("owner", "owner_membership_id"),
        ):
            if r.query_params.get(p):
                qs = qs.filter(**{f: r.query_params[p]})
        return Response(CampaignSummarySerializer(qs, many=True).data)

    def post(self, r):
        org = org_for(r.user, r.data.get("organization_id"))
        s = CampaignWriteSerializer(data=r.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        artist = relation(d, org, "artist_id", Artist, True)
        release = relation(d, org, "release_id", Release)
        owner = membership(d, org, "owner_membership_id")
        obj = valid(
            lambda: create_campaign(
                actor=r.user,
                organization=org,
                data={**d, "artist": artist, "release": release, "owner_membership": owner},
                request=r,
            )
        )
        return Response(campaign_data(obj), status=201)


class CampaignDetailView(APIView):
    def get(self, r, campaign_id):
        obj = scoped_campaign(r.user, campaign_id)
        require(r.user, obj.organization, "campaign.view")
        return Response(campaign_data(obj))

    def patch(self, r, campaign_id):
        obj = scoped_campaign(r.user, campaign_id)
        if "status" in r.data:
            raise ValidationError({"status": "Use the status endpoint."})
        s = CampaignWriteSerializer(obj, data=r.data, partial=True)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        if "artist_id" in d:
            d["artist"] = relation(d, obj.organization, "artist_id", Artist, True)
        if "release_id" in d:
            d["release"] = relation(d, obj.organization, "release_id", Release)
        if "owner_membership_id" in d:
            d["owner_membership"] = membership(d, obj.organization, "owner_membership_id")
        return Response(
            campaign_data(
                valid(lambda: update_campaign(actor=r.user, campaign=obj, data=d, request=r))
            )
        )


class CampaignStatusView(APIView):
    def post(self, r, campaign_id):
        obj = scoped_campaign(r.user, campaign_id)
        s = StatusSerializer(data=r.data)
        s.is_valid(raise_exception=True)
        return Response(
            campaign_data(
                valid(
                    lambda: transition_campaign(
                        actor=r.user, campaign=obj, request=r, **s.validated_data
                    )
                )
            )
        )


class ChannelView(APIView):
    def post(self, r, campaign_id):
        obj = scoped_campaign(r.user, campaign_id)
        s = ChannelSerializer(data=r.data)
        s.is_valid(raise_exception=True)
        return Response(
            ChannelSerializer(
                valid(
                    lambda: add_channel(
                        actor=r.user, campaign=obj, data=s.validated_data, request=r
                    )
                )
            ).data,
            status=201,
        )


class ChannelDetailView(APIView):
    def delete(self, r, campaign_id, channel_id):
        obj = scoped_campaign(r.user, campaign_id)
        ch = get_object_or_404(CampaignChannel, pk=channel_id, campaign=obj)
        valid(lambda: remove_channel(actor=r.user, channel=ch, request=r))
        return Response(status=204)


class CampaignAssetView(APIView):
    def get(self, r, campaign_id):
        campaign = scoped_campaign(r.user, campaign_id)
        require(r.user, campaign.organization, "campaign.view")
        return Response(CampaignAssetSerializer(campaign.assets.all(), many=True).data)

    def post(self, r, campaign_id):
        campaign = scoped_campaign(r.user, campaign_id)
        require(r.user, campaign.organization, "campaign.manage")
        serializer = CampaignAssetSerializer(data=r.data)
        serializer.is_valid(raise_exception=True)
        document = serializer.validated_data.get("document")
        if document and document.organization_id != campaign.organization_id:
            raise ValidationError({"document": "The asset document must belong to this organization."})
        asset = valid(lambda: serializer.save(campaign=campaign, created_by=r.user))
        record_event(actor=r.user, organization=campaign.organization, action="campaign.asset_created", resource=asset, description=f"Campaign asset created for {campaign.name}.", request=r)
        return Response(CampaignAssetSerializer(asset).data, status=201)


class CampaignResponsibilityView(APIView):
    def post(self, r, campaign_id):
        campaign = scoped_campaign(r.user, campaign_id)
        serializer = CampaignResponsibilityWriteSerializer(data=r.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        member = get_object_or_404(
            Membership.objects.active(),
            pk=data.pop("membership_id"),
            organization=campaign.organization,
            user__is_active=True,
        )
        responsibility = valid(
            lambda: assign_responsibility(
                actor=r.user, campaign=campaign, membership=member, request=r, **data
            )
        )
        return Response(CampaignResponsibilitySerializer(responsibility).data, status=201)


class CampaignResponsibilityDetailView(APIView):
    def delete(self, r, campaign_id, responsibility_id):
        campaign = scoped_campaign(r.user, campaign_id)
        responsibility = get_object_or_404(
            CampaignResponsibility, pk=responsibility_id, campaign=campaign
        )
        valid(lambda: remove_responsibility(actor=r.user, responsibility=responsibility, request=r))
        return Response(status=204)


class RolloutCreateView(APIView):
    def post(self, r, campaign_id):
        camp = scoped_campaign(r.user, campaign_id)
        s = RolloutWriteSerializer(data=r.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        owner = membership(d, camp.organization, "owner_membership_id")
        obj = valid(
            lambda: create_rollout(
                actor=r.user, campaign=camp, data={**d, "owner_membership": owner}, request=r
            )
        )
        return Response(rollout_data(obj), status=201)


class RolloutDetailView(APIView):
    def get(self, r, rollout_id):
        obj = scoped_rollout(r.user, rollout_id)
        require(r.user, obj.organization, "rollout.view")
        return Response(rollout_data(obj))

    def patch(self, r, rollout_id):
        obj = scoped_rollout(r.user, rollout_id)
        if "status" in r.data:
            raise ValidationError({"status": "Use the status endpoint."})
        s = RolloutWriteSerializer(obj, data=r.data, partial=True)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        if "owner_membership_id" in d:
            d["owner_membership"] = membership(d, obj.organization, "owner_membership_id")
        return Response(
            rollout_data(
                valid(lambda: update_rollout(actor=r.user, rollout=obj, data=d, request=r))
            )
        )


class RolloutStatusView(APIView):
    def post(self, r, rollout_id):
        obj = scoped_rollout(r.user, rollout_id)
        s = StatusSerializer(data=r.data)
        s.is_valid(raise_exception=True)
        return Response(
            rollout_data(
                valid(
                    lambda: transition_rollout(
                        actor=r.user, rollout=obj, request=r, **s.validated_data
                    )
                )
            )
        )


class MilestoneView(APIView):
    def post(self, r, rollout_id):
        obj = scoped_rollout(r.user, rollout_id)
        s = MilestoneSerializer(data=r.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        owner = membership(d, obj.organization, "owner_membership_id")
        m = valid(
            lambda: create_milestone(
                actor=r.user, rollout=obj, data={**d, "owner_membership": owner}, request=r
            )
        )
        return Response(MilestoneSerializer(m).data, status=201)


class MilestoneDetailView(APIView):
    def patch(self, r, milestone_id):
        m = get_object_or_404(
            RolloutMilestone, pk=milestone_id, rollout__in=rollouts_for_user(r.user)
        )
        s = MilestoneSerializer(m, data=r.data, partial=True)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        if "owner_membership_id" in d:
            d["owner_membership"] = membership(d, m.rollout.organization, "owner_membership_id")
        return Response(
            MilestoneSerializer(
                valid(lambda: update_milestone(actor=r.user, milestone=m, data=d, request=r))
            ).data
        )

    def delete(self, r, milestone_id):
        m = get_object_or_404(
            RolloutMilestone, pk=milestone_id, rollout__in=rollouts_for_user(r.user)
        )
        valid(lambda: remove_milestone(actor=r.user, milestone=m, request=r))
        return Response(status=204)


class TaskView(APIView):
    def post(self, r, rollout_id):
        obj = scoped_rollout(r.user, rollout_id)
        s = TaskSerializer(data=r.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        mid = d.pop("milestone_id", None)
        m = get_object_or_404(RolloutMilestone, pk=mid, rollout=obj) if mid else None
        assignee = membership(d, obj.organization, "assigned_membership_id")
        task = valid(
            lambda: create_task(
                actor=r.user,
                rollout=obj,
                data={**d, "milestone": m, "assigned_membership": assignee},
                request=r,
            )
        )
        return Response(TaskSerializer(task).data, status=201)


class TaskDetailView(APIView):
    def obj(self, u, pk):
        return get_object_or_404(RolloutTask, pk=pk, rollout__in=rollouts_for_user(u))

    def patch(self, r, task_id):
        t = self.obj(r.user, task_id)
        if "status" in r.data:
            raise ValidationError({"status": "Use the status endpoint."})
        s = TaskSerializer(t, data=r.data, partial=True)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        if "milestone_id" in d:
            mid = d.pop("milestone_id")
            d["milestone"] = (
                get_object_or_404(RolloutMilestone, pk=mid, rollout=t.rollout) if mid else None
            )
        if "assigned_membership_id" in d:
            d["assigned_membership"] = membership(
                d, t.rollout.organization, "assigned_membership_id"
            )
        return Response(
            TaskSerializer(valid(lambda: update_task(actor=r.user, task=t, data=d, request=r))).data
        )


class TaskStatusView(TaskDetailView):
    def post(self, r, task_id):
        t = self.obj(r.user, task_id)
        s = StatusSerializer(data=r.data)
        s.is_valid(raise_exception=True)
        return Response(
            TaskSerializer(
                valid(lambda: transition_task(actor=r.user, task=t, request=r, **s.validated_data))
            ).data
        )


class TaskCompleteView(TaskDetailView):
    def post(self, r, task_id):
        return Response(
            TaskSerializer(
                valid(
                    lambda: complete_task(actor=r.user, task=self.obj(r.user, task_id), request=r)
                )
            ).data
        )


class DependencyView(TaskDetailView):
    def post(self, r, task_id):
        t = self.obj(r.user, task_id)
        dep = self.obj(r.user, r.data.get("depends_on_id"))
        obj = valid(lambda: add_dependency(actor=r.user, task=t, depends_on=dep, request=r))
        return Response({"id": obj.id}, status=201)


class DependencyDetailView(TaskDetailView):
    def delete(self, r, task_id, dependency_id):
        t = self.obj(r.user, task_id)
        d = get_object_or_404(RolloutTaskDependency, pk=dependency_id, task=t)
        valid(lambda: remove_dependency(actor=r.user, dependency=d, request=r))
        return Response(status=204)


class ArtistPortalCampaignView(APIView):
    def get(self, r):
        qs = (
            portal_campaigns(r.user)
            .select_related("artist", "release", "owner_membership__user")
            .prefetch_related("rollouts")
        )
        return Response(PortalCampaignSerializer(qs, many=True).data)


class PlatformCampaignListView(APIView):
    permission_classes = (PlatformSuperuser,)

    def get(self, r):
        return Response(
            CampaignSummarySerializer(filter_campaigns(campaign_qs(), r), many=True).data
        )


class PlatformCampaignDetailView(APIView):
    permission_classes = (PlatformSuperuser,)

    def get(self, r, campaign_id):
        return Response(campaign_data(get_object_or_404(campaign_qs(), pk=campaign_id)))


class PlatformRolloutListView(APIView):
    permission_classes = (PlatformSuperuser,)

    def get(self, r):
        return Response(RolloutSummarySerializer(filter_rollouts(rollout_qs(), r), many=True).data)


class PlatformRolloutDetailView(APIView):
    permission_classes = (PlatformSuperuser,)

    def get(self, r, rollout_id):
        return Response(rollout_data(get_object_or_404(rollout_qs(), pk=rollout_id)))


class DeveloperView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)
    model = None

    def get(self, r):
        h = r.headers.get("Authorization", "")
        if not h.startswith("Bearer "):
            raise PermissionDenied("Invalid API credentials.")
        key = authenticate_api_key(h[7:], required_scope="campaign.read")
        if self.model is Campaign:
            return Response(
                DeveloperCampaignSerializer(
                    Campaign.objects.filter(organization=key.client.organization).select_related(
                        "artist", "release"
                    ),
                    many=True,
                ).data
            )
        return Response(
            DeveloperRolloutSerializer(
                Rollout.objects.filter(organization=key.client.organization).select_related(
                    "campaign"
                ),
                many=True,
            ).data
        )
