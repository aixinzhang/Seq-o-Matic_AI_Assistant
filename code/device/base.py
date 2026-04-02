"""
Abstract base classes for laboratory hardware devices.

Defines standard interfaces that all device wrappers must implement,
enabling consistent connection lifecycle management and making it
possible to mock devices for testing.
"""

from abc import ABC, abstractmethod
from typing import List


class SerialDevice(ABC):
    """Base interface for all serial-connected lab devices."""

    @abstractmethod
    def connect(self) -> None:
        """Open the serial connection to the device."""
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Close the serial connection and release resources."""
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        """Return True if the device is currently connected."""
        ...


class PumpDevice(SerialDevice):
    """Interface for peristaltic pump devices."""

    @abstractmethod
    def initialize(self) -> None:
        """Connect, configure, and verify the pump."""
        ...

    @abstractmethod
    def pump_volume(self, volume_ml: float, rate_ml_per_min: float) -> None:
        """Dispense a specified volume at a given flow rate.

        Args:
            volume_ml: Volume to pump in mL.
            rate_ml_per_min: Flow rate in mL/min.
        """
        ...

    @abstractmethod
    def start(self) -> None:
        """Start the pump."""
        ...

    @abstractmethod
    def stop(self) -> None:
        """Stop the pump."""
        ...

    @abstractmethod
    def is_running(self) -> bool:
        """Return True if the pump is currently running."""
        ...

    @abstractmethod
    def set_flow_rate(self, ml_per_min: float) -> bool:
        """Set the pump flow rate.

        Args:
            ml_per_min: Target flow rate in mL/min.

        Returns:
            True if the rate was set successfully.
        """
        ...

    @abstractmethod
    def get_speed(self) -> float:
        """Return the current pump speed in mL/min."""
        ...


class SelectorDevice(SerialDevice):
    """Interface for fluid selector/multiplexer devices."""

    @abstractmethod
    def set_path(self, reagent_name: str) -> None:
        """Route the selector to the specified reagent source.

        Args:
            reagent_name: Name of the reagent to select.
        """
        ...


class HeaterDevice(ABC):
    """Interface for heating stage devices.

    Heaters may use DAQ rather than serial, so they do not inherit
    from SerialDevice.
    """

    @abstractmethod
    def connect(self) -> None:
        """Initialize hardware connections."""
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Release hardware resources."""
        ...

    @abstractmethod
    def heat(self, duration_seconds: float) -> bool:
        """Heat for the specified duration.

        Args:
            duration_seconds: How long to hold at target temperature.

        Returns:
            True if all stages heated successfully, False otherwise.
        """
        ...

    @abstractmethod
    def config(self) -> None:
        """Run a self-test to verify the heater is working."""
        ...


class RelayDevice(SerialDevice):
    """Interface for relay controller devices."""

    @abstractmethod
    def set_relay(self, channel: int, state: bool) -> None:
        """Set a single relay channel.

        Args:
            channel: Relay channel number (0-indexed).
            state: True = on/open, False = off/closed.
        """
        ...

    @abstractmethod
    def set_all_relays(self, states: List[bool]) -> None:
        """Set all relay channels at once.

        Args:
            states: List of booleans, one per relay channel.
        """
        ...
