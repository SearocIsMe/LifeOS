"""LifeOS Life Kernel (Phase 1, S1): lazy decay + relationship engine.

Public surface is deliberately small (import-discipline anchor):
- decay: pure lazy-decay functions (architecture §5.1);
- relationship: verbatim r_{t+1} update rule (architecture §5.3).
"""

from lifeos.kernel.decay import (
    DECAY_PARAMS,
    DECAY_TRIGGERS,
    KERNEL_STATES,
    DecayError,
    KernelSnapshot,
    decay_state_map,
    decay_value,
    snapshot,
)
from lifeos.kernel.relationship import (
    PERSONALITY_MODULATION_DEFAULT,
    RELATIONSHIP_DECAY_LAMBDA,
    RelationshipError,
    RelationshipUpdate,
    apply_relationship_event,
    personality_modulation,
)

__all__ = [
    "DECAY_PARAMS",
    "DECAY_TRIGGERS",
    "KERNEL_STATES",
    "DecayError",
    "KernelSnapshot",
    "decay_state_map",
    "decay_value",
    "snapshot",
    "PERSONALITY_MODULATION_DEFAULT",
    "RELATIONSHIP_DECAY_LAMBDA",
    "RelationshipError",
    "RelationshipUpdate",
    "apply_relationship_event",
    "personality_modulation",
]
