from datetime import timedelta

import pytest
from django.utils import timezone

from apps.organizations.models import Organization
from apps.scheduling.active_plan_selectors import (
    APPROVAL_CANDIDATE,
    PUBLISHED_SNAPSHOT,
    PUBLISH_CANDIDATE,
    WORKING_CANDIDATE,
    select_active_plan_version,
)
from apps.scheduling.models import ApprovalRequest, Plan, PlanVersion, PublishedPlanSnapshot


@pytest.mark.django_db
def test_active_plan_selector_modes_are_explicit_and_deterministic():
    plan = _plan("selector-plan")
    generated = _version(plan, 1, PlanVersion.Status.GENERATED)
    proposed = _version(plan, 2, PlanVersion.Status.PROPOSED)
    approved = _version(plan, 3, PlanVersion.Status.APPROVED)
    published = _version(plan, 4, PlanVersion.Status.PUBLISHED)
    approval = ApprovalRequest.objects.create(
        request_id="APR-SELECTOR-01",
        plan_version=proposed,
        status=ApprovalRequest.Status.PENDING,
        reason="Selector test.",
    )
    PublishedPlanSnapshot.objects.create(
        snapshot_id="LIVE-SELECTOR-01",
        plan=plan,
        plan_version=published,
        approval_request=approval,
        status=PublishedPlanSnapshot.Status.ACTIVE,
        payload={"test": "selector"},
    )

    assert select_active_plan_version(WORKING_CANDIDATE) == approved
    assert select_active_plan_version(APPROVAL_CANDIDATE) == proposed
    assert select_active_plan_version(PUBLISH_CANDIDATE) == approved
    assert select_active_plan_version(PUBLISHED_SNAPSHOT) == published
    assert generated != select_active_plan_version(PUBLISH_CANDIDATE)


@pytest.mark.django_db
def test_publish_candidate_never_selects_generated_or_proposed_plan():
    plan = _plan("selector-unapproved")
    _version(plan, 1, PlanVersion.Status.GENERATED)
    _version(plan, 2, PlanVersion.Status.PROPOSED)

    assert select_active_plan_version(WORKING_CANDIDATE).status == PlanVersion.Status.PROPOSED
    assert select_active_plan_version(PUBLISH_CANDIDATE) is None


def _plan(slug: str) -> Plan:
    now = timezone.now()
    org = Organization.objects.create(name=slug, slug=slug, kind=Organization.Kind.BERAU)
    return Plan.objects.create(
        code=f"PLAN-{slug}",
        name=slug,
        organization=org,
        horizon_start=now,
        horizon_end=now + timedelta(days=3),
        status=Plan.Status.ACTIVE,
    )


def _version(plan: Plan, version_no: int, status: str) -> PlanVersion:
    return PlanVersion.objects.create(
        plan=plan,
        version_no=version_no,
        status=status,
        generated_at=timezone.now() + timedelta(minutes=version_no),
    )
