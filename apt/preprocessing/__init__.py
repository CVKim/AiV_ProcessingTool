"""Image preprocessing primitives + a node-graph pipeline executor.

This subpackage is intentionally Qt-free: it operates on numpy ``ndarray``
images and is unit-testable in isolation. The PyQt5 UI (``apt.dialogs.
preprocessing``) sits on top of it.
"""

from apt.preprocessing.operations import (
    OPERATIONS,
    Operation,
    ParamSpec,
    apply_operation,
    get_operation,
)
from apt.preprocessing.pipeline import (
    Node,
    Pipeline,
    PipelineError,
)

__all__ = [
    "OPERATIONS",
    "Operation",
    "ParamSpec",
    "apply_operation",
    "get_operation",
    "Node",
    "Pipeline",
    "PipelineError",
]
