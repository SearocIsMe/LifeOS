"""P1-PRE-2a: RequestContext contract tests.

The context is the only sanctioned carrier of (tenant, instance, subject).
Its invariants are load-bearing for tenant isolation (TL-1/TL-2), so they are
asserted here rather than left to handler discipline.
"""

from __future__ import annotations

import dataclasses

import pytest

from lifeos.context import (
    DEFAULT_TENANT,
    ContextError,
    RequestContext,
    context_for,
)


# --------------------------------------------------------------------------- #
# Defaults
# --------------------------------------------------------------------------- #
def test_default_tenant_is_default() -> None:
    ctx = RequestContext()
    assert ctx.tenant_id == DEFAULT_TENANT == "default"
    assert ctx.life_id is None
    assert ctx.subject_id is None


def test_keyword_constructor_matches_positional() -> None:
    assert context_for(tenant_id="t1", life_id="l1") == RequestContext("t1", "l1")


# --------------------------------------------------------------------------- #
# Immutability
# --------------------------------------------------------------------------- #
def test_context_is_frozen() -> None:
    ctx = RequestContext(tenant_id="t1")
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.tenant_id = "t2"  # type: ignore[misc]


def test_derivation_returns_new_object_and_leaves_original_untouched() -> None:
    base = RequestContext(tenant_id="t1")
    scoped = base.for_instance("l1")
    assert scoped is not base
    assert scoped.life_id == "l1"
    assert base.life_id is None


# --------------------------------------------------------------------------- #
# Validation (fail closed)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("bad", ["", "   ", None])
def test_empty_tenant_rejected(bad: object) -> None:
    with pytest.raises(ContextError):
        RequestContext(tenant_id=bad)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", ["", "  "])
def test_empty_life_rejected(bad: str) -> None:
    with pytest.raises(ContextError):
        RequestContext(life_id=bad)


def test_subject_without_instance_rejected() -> None:
    # A subject predicate without an instance predicate would silently widen
    # the query across every instance in the tenant.
    with pytest.raises(ContextError):
        RequestContext(subject_id="s1")
    with pytest.raises(ContextError):
        RequestContext(tenant_id="t1", subject_id="s1")


def test_for_subject_requires_instance() -> None:
    with pytest.raises(ContextError):
        RequestContext(tenant_id="t1").for_subject("s1")


def test_require_life_fails_closed_when_absent() -> None:
    with pytest.raises(ContextError):
        RequestContext(tenant_id="t1").require_life()
    assert RequestContext(tenant_id="t1", life_id="l1").require_life() == "l1"


# --------------------------------------------------------------------------- #
# Derivation semantics
# --------------------------------------------------------------------------- #
def test_for_instance_drops_subject() -> None:
    ctx = RequestContext(tenant_id="t1", life_id="l1", subject_id="s1")
    moved = ctx.for_instance("l2")
    assert moved.life_id == "l2"
    assert moved.subject_id is None
    assert moved.tenant_id == "t1"  # tenant never changes through derivation


def test_for_subject_preserves_instance_and_tenant() -> None:
    ctx = RequestContext(tenant_id="t1", life_id="l1")
    assert ctx.for_subject("s1") == RequestContext("t1", "l1", "s1")


def test_tenant_cannot_be_narrowed_by_helpers() -> None:
    # Guard against a future helper accidentally letting handlers switch tenant.
    ctx = RequestContext(tenant_id="t1", life_id="l1")
    assert ctx.for_instance("l2").tenant_id == "t1"
    assert ctx.for_subject("s1").tenant_id == "t1"


# --------------------------------------------------------------------------- #
# Predicate fragment
# --------------------------------------------------------------------------- #
def test_as_predicates_always_includes_tenant() -> None:
    assert RequestContext(tenant_id="t1").as_predicates() == {"tenant_id": "t1"}


def test_as_predicates_adds_instance_and_subject() -> None:
    ctx = RequestContext(tenant_id="t1", life_id="l1", subject_id="s1")
    assert ctx.as_predicates() == {
        "tenant_id": "t1",
        "life_id": "l1",
        "subject_id": "s1",
    }


def test_as_predicates_omits_subject_when_unset() -> None:
    preds = RequestContext(tenant_id="t1", life_id="l1").as_predicates()
    assert "subject_id" not in preds
