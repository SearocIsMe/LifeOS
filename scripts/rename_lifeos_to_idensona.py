"""Rename LifeOS -> Idensona in v0.9.2 docs + naming doc (and rename files).

Discipline:
- PROTECTED: historical v0.9.1 filenames (those files keep LifeOS in their names)
  and real code paths (src/lifeos, lifeos/) must stay untouched.
- Only the 5 target files are modified; historical docs are left as-is.
"""

from pathlib import Path

DOC = Path("doc")

TARGETS = [
    "LifeOS_架构设计_v0.9.2.md",
    "LifeOS_生态交付与商业合作_v0.9.2.md",
    "LifeOS_竞品与市场分析_v0.9.2.md",
    "LifeOS_阶段拆解与任务进度_v0.9.2.md",
    "LifeOS_命名方案建议_20261125.md",
]

# Substrings that must survive the rename (historical file names / real paths).
PROTECTED = [
    "LifeOS_架构设计_v0.9.1",
    "LifeOS_产品规格说明书_v0.9.1",
    "LifeOS_研发路线图_v0.9.1",
    "src/lifeos",
    "src\\lifeos",
    "LifeOS 历史代号",  # keep the explicit historical-code phrasing intact
]


def transform(text: str) -> str:
    slots = {}
    for i, token in enumerate(PROTECTED):
        key = f"\x00P{i}\x00"
        slots[key] = token
        text = text.replace(token, key)

    text = text.replace("LifeOS", "Idensona")

    for key, token in slots.items():
        text = text.replace(key, token)
    return text


def main() -> None:
    for name in TARGETS:
        src = DOC / name
        if not src.exists():
            print(f"SKIP (missing): {name}")
            continue

        original = src.read_text(encoding="utf-8")
        updated = transform(original)

        new_name = name.replace("LifeOS_", "Idensona_", 1)
        dst = DOC / new_name

        dst.write_text(updated, encoding="utf-8")
        if dst != src:
            src.unlink()

        before = original.count("LifeOS")
        after = updated.count("LifeOS")
        print(f"{name} -> {new_name}: LifeOS {before} -> {after} ({before - after} replaced)")


if __name__ == "__main__":
    main()
