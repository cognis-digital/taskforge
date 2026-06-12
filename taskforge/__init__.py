"""taskforge — declarative YAML task runner. Part of the Cognis Neural Suite."""

from taskforge.core import (
    TOOL_NAME,
    TOOL_VERSION,
    Task,
    TaskFile,
    TaskforgeError,
    draft_taskfile,
    expand_matrix,
    interpolate,
    list_tasks,
    load_taskfile,
    parse_yaml_subset,
    plan_commands,
    resolve_order,
    run,
    validate_taskfile,
)

__version__ = TOOL_VERSION

__all__ = [
    "TOOL_NAME",
    "TOOL_VERSION",
    "__version__",
    "Task",
    "TaskFile",
    "TaskforgeError",
    "draft_taskfile",
    "expand_matrix",
    "interpolate",
    "list_tasks",
    "load_taskfile",
    "parse_yaml_subset",
    "plan_commands",
    "resolve_order",
    "run",
    "validate_taskfile",
]
