from __future__ import annotations

from django.db.models import F, QuerySet

from .models import ApprovalRequest, PlanVersion, PublishedPlanSnapshot


WORKING_CANDIDATE = "working_candidate"
APPROVAL_CANDIDATE = "approval_candidate"
PUBLISH_CANDIDATE = "publish_candidate"
PUBLISHED_SNAPSHOT = "published_snapshot"


def plan_version_queryset() -> QuerySet[PlanVersion]:
    return PlanVersion.objects.select_related("plan", "created_by", "source_version")


def select_active_plan_version(mode: str = WORKING_CANDIDATE) -> PlanVersion | None:
    queryset = plan_version_queryset()
    if mode == PUBLISH_CANDIDATE:
        return queryset.filter(status=PlanVersion.Status.APPROVED).order_by("-created_at", "-id").first()
    if mode == APPROVAL_CANDIDATE:
        request = (
            ApprovalRequest.objects.select_related("plan_version", "plan_version__plan")
            .order_by("-created_at", "-id")
            .first()
        )
        if request:
            return request.plan_version
        return select_active_plan_version(WORKING_CANDIDATE)
    if mode == PUBLISHED_SNAPSHOT:
        snapshot = (
            PublishedPlanSnapshot.objects.filter(status=PublishedPlanSnapshot.Status.ACTIVE)
            .select_related("plan_version", "plan_version__plan", "plan_version__source_version")
            .order_by("-published_at", "-id")
            .first()
        )
        return snapshot.plan_version if snapshot else None
    if mode != WORKING_CANDIDATE:
        raise ValueError(f"Unknown active plan selector mode: {mode}")
    candidate = (
        queryset.filter(
            status__in=[
                PlanVersion.Status.DRAFT,
                PlanVersion.Status.GENERATED,
                PlanVersion.Status.VALIDATED,
                PlanVersion.Status.PROPOSED,
                PlanVersion.Status.APPROVED,
            ],
        )
        .order_by("-created_at", "-id")
        .first()
    )
    if candidate:
        return candidate
    published = select_active_plan_version(PUBLISHED_SNAPSHOT)
    if published:
        return published
    return queryset.order_by(F("generated_at").desc(nulls_last=True), "-created_at", "-id").first()
