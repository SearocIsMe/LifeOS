"""Memory OS v1: EmbeddingOutbox worker + vector recall (Phase 3 technical track).

Spec anchor (arch §5.2): async embedding via Outbox + Worker retry; embedding
failure never blocks authoritative facts - recall degrades to SQL filtering.
"""
