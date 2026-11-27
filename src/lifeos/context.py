"""Request-scoped context: the single carrier of (tenant, instance, subject).

Why this module exists (Idensona v0.9.2 distribution decision, 2026-11-26):
CH-A is a multi-tenant cloud, so ``tenant_id`` must be a first-class isolation
dimension alongside ``life_id`` / ``subject_id``. Passing three loose string
arguments through every seam function does not survive contact with reality:
the signature churns on every new endpoint and it is trivial to forget one
predicate. This module makes the triple explicit, immutable and defaulted.

Isolation hierarchy (architecture v0.9.2 §6.4):

    Tenant(tenant_id) -> Project(project_id, optional) -> Instance(life_id)
        -> Subject(subject_id)

Phase P1-PRE-2b/c wires ``tenant_id`` into the authoritative tables; this
module is the *carrier* only. It deliberately holds no behaviour: no I/O, no
policy, no defaults beyond ``DEFAULT_TENANT``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

#: Tenant used for single-tenant deployments and for all pre-cloud data.
#: Every row migrated in P1-PRE-2b gets this value, so existing behaviour is
#: preserved bit-for-bit (the "P0 stays green" requirement).
DEFAULT_TENANT = "default"


class ContextError(ValueError):
    """Raised when a context is constructed with an empty identifier."""


def _require(name: str, value: str | None) -> str:
    if value is None or not str(value).strip():
        raise ContextError(f"{name} must be a non-empty string")
    return str(value)


@dataclass(frozen=True, slots=True)
class RequestContext:
    """Immutable (tenant_id, life_id, subject_id) triple.

    ``life_id`` is optional because some operations are tenant-scoped but not
    instance-scoped (tenant onboarding, usage rollups). ``subject_id`` is
    optional because most operations are instance-scoped only; it becomes
    mandatory for recall paths that touch person-specific memory.

    The object is frozen: a handler cannot quietly rewrite the tenant mid-call,
    which is the cheapest defence against cross-tenant leakage (TL-2).
    """

    tenant_id: str = DEFAULT_TENANT
    life_id: str | None = None
    subject_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "tenant_id", _require("tenant_id", self.tenant_id))
        if self.life_id is not None:
            object.__setattr__(self, "life_id", _require("life_id", self.life_id))
        if self.subject_id is not None:
            object.__setattr__(self, "subject_id", _require("subject_id", self.subject_id))
        if self.subject_id is not None and self.life_id is None:
            # A subject only exists inside an instance; allowing this would let
            # callers build predicates that filter on subject but not instance.
            raise ContextError("subject_id requires life_id")

    # ------------------------------------------------------------------ #
    # Derivation helpers - the only sanctioned way to narrow a context.
    # ------------------------------------------------------------------ #
    def for_instance(self, life_id: str) -> RequestContext:
        """Scope this context to one instance (drops any subject)."""
        return replace(self, life_id=life_id, subject_id=None)

    def for_subject(self, subject_id: str) -> RequestContext:
        """Scope to one subject; requires an instance to already be set."""
        if self.life_id is None:
            raise ContextError("cannot scope to a subject without life_id")
        return replace(self, subject_id=subject_id)

    def require_life(self) -> str:
        """Return ``life_id`` or fail closed.

        Seam handlers call this instead of poking at the field, so a missing
        instance becomes a loud error rather than a predicate that silently
        widens to "all instances in the tenant".
        """
        if self.life_id is None:
            raise ContextError("life_id required for this operation")
        return self.life_id

    # ------------------------------------------------------------------ #
    def as_predicates(self) -> dict[str, str]:
        """Predicate fragment for store/DB filters (tenant always included)."""
        preds: dict[str, str] = {"tenant_id": self.tenant_id}
        if self.life_id is not None:
            preds["life_id"] = self.life_id
        if self.subject_id is not None:
            preds["subject_id"] = self.subject_id
        return preds


def context_for(
    *,
    tenant_id: str = DEFAULT_TENANT,
    life_id: str | None = None,
    subject_id: str | None = None,
) -> RequestContext:
    """Keyword-only constructor shorthand (reads better at call sites)."""
    return RequestContext(tenant_id=tenant_id, life_id=life_id, subject_id=subject_id)
