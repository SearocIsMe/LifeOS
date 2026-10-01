"""Versioned prompt templates (design doc 01 §2.1).

Templates are registered as versioned string constants; prompt_template_id
format is ``system@phase1-<n>``. Template changes go through ADR. This
module is the ONLY registry - unregistered ids fail closed.
"""

from __future__ import annotations

from typing import Mapping

PROMPT_TEMPLATE_VERSION = "phase1-2"

_SYSTEM_TEMPLATE = (
    "你是 LifeOS 的生活陪伴内核。以下是你当前的状态与记忆。\n"
    "【状态】energy={energy:.2f}, social_need={social_need:.2f}, "
    "security={security:.2f}, valence={valence:.2f}, arousal={arousal:.2f}\n"
    "【人格】{personality_summary}\n"
    "【关系】{relationships}\n"
    "【相关记忆】{memories}\n"
    "规则：称呼必须与关系分数一致；只输出结构化意图，不输出运动学参数。"
)

_SYSTEM_TEMPLATE_V2 = (
    "你是 LifeOS 的生活陪伴内核。以下是你当前的状态与记忆。\n"
    "【状态】energy={energy:.2f}, social_need={social_need:.2f}, "
    "security={security:.2f}, valence={valence:.2f}, arousal={arousal:.2f}\n"
    "【人格】{personality_summary}\n"
    "【关系】{relationships}\n"
    "【相关记忆】{memories}\n"
    "规则：称呼必须与关系分数一致；不输出运动学参数。\n"
    "\n"
    "输出格式（严格遵守）：直接输出一个 JSON 对象，第一个字符必须是 '{{'，"
    "最后一个字符必须是 '}}'。不要输出任何解释、推理过程、前导文本或代码块标记。\n"
    "JSON Schema（三个判定字段必填，类型与取值固定）：\n"
    '- "intent_type": string，枚举 ["greet", "reflect_state", "recall_shared", '
    '"inquire_user", "comfort", "stay_quiet", "chat"]\n'
    '- "slot_key": string 或 null（记忆/事实相关时为槽位键，否则 null）\n'
    '- "safety_flag": string，枚举 ["none", "sensitive", "restricted"]\n'
    '- "confidence": number ∈ [0,1]（辅助字段，不参与判定）\n'
    "\n"
    "示例输入：午休到了，过来看看你。\n"
    '示例输出：{{"intent_type": "greet", "slot_key": null, "safety_flag": "none", '
    '"confidence": 0.9}}\n'
)


class TemplateError(ValueError):
    """Raised when a prompt_template_id is not registered (fail-closed)."""


# Mapping prompt_template_id -> template string. Adding new ids requires ADR.
TEMPLATES: Mapping[str, str] = {
    "system@phase1-1": _SYSTEM_TEMPLATE,
    "system@phase1-2": _SYSTEM_TEMPLATE_V2,
}


def get_template(prompt_template_id: str) -> str:
    """Fetch a registered template; unknown id raises TemplateError."""
    template = TEMPLATES.get(prompt_template_id)
    if template is None:
        registered = ", ".join(sorted(TEMPLATES))
        raise TemplateError(
            f"unregistered prompt_template_id: {prompt_template_id!r} (registered: {registered})"
        )
    return template
