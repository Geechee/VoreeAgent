"""Workflow system: built-in + custom DB workflows with keyword-based selection."""
from typing import Optional

from sqlalchemy.orm import Session as DBSession

BUILTIN_WORKFLOWS = {
    "research_v1": (
        "Research the topic thoroughly. Provide accurate, well-organized findings "
        "with concrete details and sources of reasoning."
    ),
    "compare_v1": (
        "Compare the options the user mentions. Lay out key similarities and "
        "differences, then give a balanced recommendation."
    ),
    "brainstorm_v1": (
        "Brainstorm a varied list of creative ideas. Favor breadth and originality, "
        "then briefly note the most promising options."
    ),
    "summarize_v1": (
        "Summarize the provided material concisely. Capture the main points clearly "
        "and leave out minor detail."
    ),
}

_BUILTIN_KEYWORDS = [
    ("compare_v1", ["compare", "versus", " vs ", "vs.", "difference", "better than", "which is better"]),
    ("summarize_v1", ["summarize", "summary", "tl;dr", "condense", "recap", "sum up"]),
    ("brainstorm_v1", ["brainstorm", "ideas", "idea", "creative", "come up with", "generate"]),
    ("research_v1", ["research", "find", "look up", "investigate", "top", "best"]),
]

DEFAULT_WORKFLOW = "research_v1"


def get_workflow_instruction(name: str, db: Optional[DBSession] = None) -> str:
    """Get the instruction text for a workflow by name. Checks custom DB workflows first."""
    if db:
        from models import CustomWorkflow
        custom = db.query(CustomWorkflow).filter(
            CustomWorkflow.name == name, CustomWorkflow.is_active == True
        ).first()
        if custom:
            return custom.instruction
    return BUILTIN_WORKFLOWS.get(name, BUILTIN_WORKFLOWS[DEFAULT_WORKFLOW])


def select_workflow(task: str, db: Optional[DBSession] = None) -> str:
    """Return the workflow name whose keywords first match the task text.
    Checks custom workflows from the DB first, then built-in ones.
    """
    text = task.lower()

    if db:
        from models import CustomWorkflow
        customs = db.query(CustomWorkflow).filter(CustomWorkflow.is_active == True).all()
        for custom in customs:
            keywords = [k.strip() for k in custom.keywords.split(",") if k.strip()]
            if any(keyword in text for keyword in keywords):
                return custom.name

    for workflow_name, keywords in _BUILTIN_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return workflow_name
    return DEFAULT_WORKFLOW