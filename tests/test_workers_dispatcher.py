from apt.constants import (
    OP_ATTACH_FOV,
    OP_BASIC_SORTING,
    OP_BTJ,
    OP_CROP,
    OP_DATE_COPY,
    OP_IMAGE_COPY,
    OP_MIM_TO_BMP,
    OP_NG_COUNT,
    OP_NG_SORTING,
    OP_SIMULATION,
)
from apt.workers.base import _HANDLERS


def test_every_canonical_op_has_a_handler():
    expected = {
        OP_ATTACH_FOV,
        OP_BASIC_SORTING,
        OP_BTJ,
        OP_CROP,
        OP_DATE_COPY,
        OP_IMAGE_COPY,
        OP_MIM_TO_BMP,
        OP_NG_COUNT,
        OP_NG_SORTING,
        OP_SIMULATION,
    }
    assert expected.issubset(_HANDLERS.keys())


def test_handlers_are_callable():
    for handler in _HANDLERS.values():
        assert callable(handler)
