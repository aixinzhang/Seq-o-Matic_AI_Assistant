"""
Device wrapper for KMtronic 4-channel USB Solenoid Relay.

This is currently a stub -- all methods are no-ops (pass). The relay
functionality was previously implemented but has been disabled.
The low-level driver in driver/kmtronic_relay.py is fully functional.

Author: Ben Sutton
Meta: https://info.kmtronic.com/usb-four-channel-relay-controller-pcb.html
"""

from typing import List, Optional

from driver.kmtronic_relay import KmtronicRelay
from device.base import RelayDevice
from types_seq import RelayConfig

BUTTON_TEXT_TRUE = "Open"
BUTTON_TEXT_FALSE = "Closed"


class KmtronicRelayCh4(RelayDevice):
    """Stub device wrapper for KMtronic 4-channel USB relay.

    All methods are currently no-ops. To re-enable relay functionality,
    uncomment the KmtronicRelay driver instantiation and method bodies.

    Args:
        port: Serial COM port for the relay controller.
    """

    def __init__(self, port: str) -> None:
        self.block_all_changes: bool = False

    def set_change_blocker(self, value: bool) -> None:
        """Enable/disable relay change blocking (stub -- no-op)."""
        print("adjust relay")

    @property
    def connected(self) -> Optional[bool]:
        """Return whether the relay is connected (stub -- always None)."""
        pass

    def change_relay_state(self, relay_num: int, relay_state: bool) -> None:
        """Set a single relay channel state (stub -- no-op)."""
        pass
        # print("checking connection...")
        # if self.block_all_changes:
        #
        #     print("relay changes blocked in change_relay_state! ")
        #     return
        #
        # if self.connected:
        #     self._kmt_relay.operate_relay(relay_num, relay_state)
        #     print(self._kmt_relay.relay_states)

    def change_relay_states(self, relay_states: List[bool]) -> None:
        """Set all relay channel states at once (stub -- no-op)."""
        pass

    def on_connect_requested(self) -> None:
        """Attempt to connect to the relay device (stub -- no-op)."""
        pass

    def quit(self) -> None:
        """Disconnect and clean up the relay device (stub -- no-op)."""
        pass

    # --- RelayDevice interface methods (stubs) ---

    def connect(self) -> None:
        """Open serial connection (stub -- no-op)."""
        pass

    def disconnect(self) -> None:
        """Close serial connection (stub -- no-op)."""
        pass

    def is_connected(self) -> bool:
        """Return whether the relay is connected (stub -- always False)."""
        return False

    def set_relay(self, channel: int, state: bool) -> None:
        """Set a single relay channel (stub -- no-op)."""
        pass

    def set_all_relays(self, states: List[bool]) -> None:
        """Set all relay channels (stub -- no-op)."""
        pass