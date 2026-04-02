"""
Imaging package for microscope control and image analysis.

Re-exports the main ImagingSystem class (aliased as ``scope`` for backward
compatibility) along with key utility functions.
"""
from system.imaging.imaging_system import ImagingSystem
from system.imaging.position_utils import get_pos_data, single_createtiles

# Backward-compatible alias
scope = ImagingSystem

__all__ = [
    "ImagingSystem",
    "scope",
    "get_pos_data",
    "single_createtiles",
]
