"""Transaction atomicity: a failed commit leaves ZERO half-applied state
(design doc 01 §10; AC-04 assertion 5, in-memory variant)."""

from __future__ import annotations

from lifeos.cli import DEMO_EVENTS, _new_store_and_pipeline


def test_failed_commit_leaves_no_partial_state():
    store, pipeline = _new_store_and_pipeline()
    before = store.snapshot()

    # Ingest the first two events normally, then inject a failure at apply time.
    pipeline.ingest(dict(DEMO_EVENTS[0]))
    pipeline.ingest(dict(DEMO_EVENTS[1]))
    mid = store.snapshot()

    try:
        # Event 3 carries an ambiguous-conflict memory update; fail the commit
        # right before the single application phase.
        store.commit_effects(
            pipeline.build_effects_for_test(dict(DEMO_EVENTS[2]))
            if hasattr(pipeline, "build_effects_for_test")
            else _effects(pipeline, DEMO_EVENTS[2]),
            fail_before_apply=True,
        )
        raise AssertionError("injected failure did not fire")
    except RuntimeError as exc:
        assert "injected failure" in str(exc)

    after = store.snapshot()
    assert after == mid, "half-applied state detected after failed commit"
    assert before != mid  # sanity: earlier events did apply


def _effects(pipeline, event):
    from lifeos.entities import EventSource
    from lifeos.events.pipeline import build_effects

    # Re-run the commit path up to (not including) effects application.
    raw = pipeline.store.ingest_raw(
        life_id=event["life_id"],
        source=EventSource(event["source"]),
        payload=event["payload"],
        occurred_at=event["occurred_at"],
    )
    assert raw is not None
    from lifeos.events.interpret import rule_interpret

    l1 = rule_interpret(raw, extractor_version=pipeline.extractor_version)
    pipeline.store.archive_l1(l1)
    from lifeos.events.commit import deterministic_commit

    l2 = deterministic_commit(
        l1.output_json,
        life_id=raw.life_id,
        l1_event_id=l1.event_id,
        raw_event_id=raw.event_id,
        occurred_at=raw.occurred_at,
        schema_version=pipeline.schema_version,
        policy_version=pipeline.policy_version,
        rules_version=pipeline.rules_version,
    )
    pipeline.store.archive_l2(l2)
    return build_effects(pipeline.store, l2)
