"""Fluidics subsystem package.

Contains protocol loading and sequence execution logic extracted from
the FluidicSystem class.
"""

from system.fluidics.protocol_loader import load_protocol
from system.fluidics.sequence_runner import SequenceState

__all__ = ['load_protocol', 'SequenceState']
