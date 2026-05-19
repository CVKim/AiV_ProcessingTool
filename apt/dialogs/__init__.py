"""Task panels (formerly QDialog subclasses).

Each panel is a self-contained QWidget that exposes ``get_parameters``,
``validate_parameters`` and a ``start_task`` slot. They are designed to be
embedded into the main window's stacked layout, but can also be popped out
as a standalone QDialog if needed.
"""

from apt.dialogs.base import BaseTaskPanel
from apt.dialogs.basic_sorting import BasicSortingPanel
from apt.dialogs.ng_sorting import NGSortingPanel
from apt.dialogs.ng_count import NGCountPanel
from apt.dialogs.date_copy import DateBasedCopyPanel
from apt.dialogs.image_copy import ImageFormatCopyPanel
from apt.dialogs.simulation import SimulationFolderingPanel
from apt.dialogs.crop import CropPanel
from apt.dialogs.mim_to_bmp import MIMtoBMPPanel
from apt.dialogs.attach_fov import AttachFOVPanel
from apt.dialogs.btj import BMPtoJPGPanel
from apt.dialogs.preprocessing import PreprocessingPanel

__all__ = [
    "BaseTaskPanel",
    "BasicSortingPanel",
    "NGSortingPanel",
    "NGCountPanel",
    "DateBasedCopyPanel",
    "ImageFormatCopyPanel",
    "SimulationFolderingPanel",
    "CropPanel",
    "MIMtoBMPPanel",
    "AttachFOVPanel",
    "BMPtoJPGPanel",
    "PreprocessingPanel",
]
