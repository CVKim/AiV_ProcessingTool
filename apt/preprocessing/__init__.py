"""Image preprocessing primitives + a node-graph pipeline executor.

This subpackage is intentionally Qt-free: it operates on numpy ``ndarray``
images and is unit-testable in isolation. The PyQt5 UI (``apt.dialogs.
preprocessing``) sits on top of it.
"""

from apt.preprocessing.categories import (
    CATEGORY_STYLES,
    STATUS_COLORS,
    CategoryStyle,
    ORIGIN_STYLE,
    format_time_ms,
    short_hint,
    status_color,
    style_for,
)
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
from apt.preprocessing.job import (
    JobFormatError,
    CURRENT_VERSION as JOB_FORMAT_VERSION,
    FORMAT_TAG as JOB_FORMAT_TAG,
    deserialize_pipeline,
    load_job,
    save_job,
    serialize_pipeline,
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
    "CATEGORY_STYLES",
    "STATUS_COLORS",
    "CategoryStyle",
    "ORIGIN_STYLE",
    "style_for",
    "short_hint",
    "status_color",
    "format_time_ms",
    "JobFormatError",
    "JOB_FORMAT_TAG",
    "JOB_FORMAT_VERSION",
    "save_job",
    "load_job",
    "serialize_pipeline",
    "deserialize_pipeline",
]
