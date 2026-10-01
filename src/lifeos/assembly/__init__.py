"""LifeOS Context Assembly (Phase 1, S2): pure function + versioned templates.

Import-discipline anchor; see assemble.py / templates.py.
"""

from lifeos.assembly.assemble import AssemblyError, ContextAssemblyResult, assemble
from lifeos.assembly.templates import PROMPT_TEMPLATE_VERSION, TEMPLATES, TemplateError, get_template

__all__ = [
    "AssemblyError",
    "ContextAssemblyResult",
    "assemble",
    "PROMPT_TEMPLATE_VERSION",
    "TEMPLATES",
    "TemplateError",
    "get_template",
]
