"""
Fluidics sequence execution state machine.

Provides a SequenceState enum for clear status tracking and the
SequenceRunner class that executes multi-step fluidics protocols
via a timer-based state machine.
"""

from enum import IntEnum


class SequenceState(IntEnum):
    """Status codes for the fluidics sequence state machine."""
    FINISHED = -2
    CANCELLED = -1
    IDLE = 0
    RUNNING = 1
