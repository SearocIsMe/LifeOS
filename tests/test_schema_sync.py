"""Design doc 01 D2-1: Pydantic contract and SQLAlchemy DDL must not drift."""

from __future__ import annotations

from lifeos.entities import ENTITY_MODELS
from lifeos.store.tables import TABLE_FOR_ENTITY, tables


def test_fifteen_entities_present():
    assert len(ENTITY_MODELS) == 15


def test_every_entity_maps_to_a_table():
    assert set(TABLE_FOR_ENTITY) == set(ENTITY_MODELS)


def test_column_names_match_field_names():
    for entity_name, table_name in TABLE_FOR_ENTITY.items():
        model_fields = set(ENTITY_MODELS[entity_name].model_fields)
        table_cols = {c.key for c in tables[table_name].columns}
        assert model_fields == table_cols, (
            f"{entity_name} fields {sorted(model_fields ^ table_cols)} drift "
            f"from {table_name} columns"
        )


def test_every_table_has_life_id_except_global_ones():
    global_tables = {"life_instances", "gold_set_registry"}
    for name, table in tables.items():
        if name in global_tables:
            continue
        assert "life_id" in table.c, f"{name} missing life_id (isolation predicate)"
