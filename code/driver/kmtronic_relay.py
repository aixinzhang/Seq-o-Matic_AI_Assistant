"""
Author: Ben Sutton
Description: Driver for KMtronic USB Solenoid Relay
Meta: https://info.kmtronic.com/usb-four-channel-relay-controller-pcb.html
"""

import serial
import time
from typing import Optional, Union, List


class KmtronicRelay:
    RESPONSE_TIME = 0.2

    def __init__(self, com_port: Union[str, int]) -> None:
        """
        original 3
        Constructor taking com_port.  Does not establish connection.
        :param com_port: (str or int)
        """
        self._com_port = com_port
        self._serial_con: Optional[serial.serialwin32.Serial] = None

        self._lks = [False, False, False, False]  # last known state (for comparisons), set upon connection

    def connect(self) -> bool:
        """
        Connects to device.  Must be called before other actions.
        :returns: (bool) Success or Failure
        """
        try:
            self._serial_con = serial.Serial(
                self._com_port,
                9600,
                8,
                serial.PARITY_NONE,
                1,
                timeout=1.0)
        except serial.serialutil.SerialException as e:
            # not sure if you want to propogate this up or not
            print(e)

        if self._serial_con and self._serial_con.is_open:
            # maybe test status with FF 09 00
            self._lks = self._get_relay_states()
            return True
        else:
            return False

    def disconnect(self) -> None:
        """
        Disconnects from device.  Called automatically on object cleanup.
        """
        if self._serial_con:
            self._serial_con.close()
            print("disconnect relay,close the port!")

    def _send_cmd(self, cmd: bytearray) -> None:
        """
        Internal f() to send serial command to device.
        :param cmd: (str) Command to execute
        """
        if self._serial_con and self._serial_con.is_open:
            self._serial_con.reset_input_buffer()
            self._serial_con.reset_output_buffer()
            self._serial_con.write(cmd)
            self._serial_con.flush()

    def _get_response(self) -> bytes:
        """
        Gets response from serial buffer.  Not sure if this will be needed
        for this device.  Can build this f() out further if needed to keep
        reading over a period of time.
        :returns: (str) Response.
        """
        val: bytes = b""

        try:
            val = self._serial_con.readline()
        except Exception as e:
            # can catch and throw customs here if you want
            ...  # TODO: Make more robust

        return val

    def __del__(self) -> None:
        """
        Deconstructor disconnects automatically.
        """
        self.disconnect()

    @property
    def connected(self) -> bool:
        return self._serial_con.is_open

    def operate_relay(self, relay_number: int, state: bool = False, verify: bool = False) -> None:
        """
        Turns relay switches on and off.
        :param relay_number: (int) 0-n
        :param state: (bool) True = on, False = off
        :param verify: (bool) if True, will query the device for the final relay positions
        """

        if self._serial_con and self._serial_con.is_open:
            if self._lks[relay_number] != state:
                self._send_cmd(bytearray([255, relay_number + 1, state]))
                if verify:
                    time.sleep(self.RESPONSE_TIME)
                    self._lks = self._get_relay_states()  # might want to just check the device
                else:
                    self._lks[relay_number] = state

    def operate_relays(self, states: List[bool]) -> None:
        """
        Same as operate_relay but optimized for multi-use relay switches.
        :param states: list(bool) A bool List representing each relay's desired state
        """
        if self._serial_con and self._serial_con.is_open:
            for relay_pair in [(index, rh) for index, (lh, rh) in enumerate(zip(self._lks, states)) if lh != rh]:
                self.operate_relay(relay_pair[0], bool(relay_pair[1]))

            self._lks = self._get_relay_states()

    @property
    def relay_states(self) -> List[bool]:
        return self._lks

    def _get_relay_states(self) -> List[bool]:
        """
        Returns list of relay states as true or false vals depending on each
            state.
        Example: [True, False, False, True] would indicate that the first and
            fourth relay are currently on.
        :returns: List of bools
        """
        self._send_cmd(bytearray([255, 9, 0]))
        time.sleep(self.RESPONSE_TIME)
        self._lks = [bool(x) for x in self._get_response()]
        return self._lks


if __name__ == "__main__":
    print("Using COM6... please change for test if different")
    sr = KmtronicRelay(6)  # change this for your com port

    if sr.connect():
        print("Opening relay 1")
        sr.operate_relay(0, True, True)

        print("Getting relay states...")
        print(sr.relay_states)

        print("Closing relay 1")
        sr.operate_relays([False, False, False, False])

        print("Getting relay states...")
        print(sr.relay_states)

        sr.disconnect()