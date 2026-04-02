# -*- coding: utf-8 -*-
"""Device wrapper for Elveflow cascaded fluid selector multiplexers.

Controls two cascaded Elveflow rotary selectors to route fluid from
up to 16 reagent sources to a single output. Selector 1 handles
addresses 1-11 directly; addresses 12+ route through selector 2's
passthrough port (port 12) into selector 1.
"""

import json
import math
import os
import time

from typing import List

import serial

from constants import SELECTOR_UNIT_PORT_COUNT, SELECTOR_PASSTHROUGH_PORT, SELECTOR_SETTLE_SECONDS
from device.base import SelectorDevice
from logging_config import get_logger
from types_seq import SelectorConfig

logger = get_logger("device.selector")


class ElveflowMux(SelectorDevice):
    """Cascaded Elveflow fluid selector multiplexer.

    Manages two serial-connected Elveflow rotary valves to select
    reagent sources by name. The reagent-to-address mapping is loaded
    from Fluidics_Reagent_Components.json.

    Args:
        config: List of two dicts, each with a 'port' key for the serial COM port.
    """

    def __init__(self, config: List[SelectorConfig]) -> None:
            self.config = config
            with open(os.path.join("config_file", "Fluidics_Reagent_Components.json"), 'r') as r:
                  self.source_list= json.load(r)
            self.selector_reagent = [i['solution'] for i in self.source_list]
            self.address = [i['address'] for i in self.source_list]
            self.selector_fluidics_dict = dict(zip(self.selector_reagent, self.address))
            self.unit_port=SELECTOR_UNIT_PORT_COUNT
            self.pass_though_port=SELECTOR_PASSTHROUGH_PORT

            self.source_limit=self.unit_port*(math.ceil(len(self.source_list)/self.unit_port))
    def connect(self) -> None:
        """Open serial connections to both selectors."""
        self.selector1= serial.Serial(port = self.config[0]['port'],
                baudrate = 9600,
                parity= serial.PARITY_NONE,
                bytesize=serial.EIGHTBITS,
                stopbits=serial.STOPBITS_ONE)

        self.selector2= serial.Serial(port=self.config[1]['port'],
                                       baudrate=9600,
                                       parity=serial.PARITY_NONE,
                                       bytesize=serial.EIGHTBITS,
                                       stopbits=serial.STOPBITS_ONE)

    def disconnect(self) -> None:
        """Close serial connections to both selectors."""
        self.selector1.close()
        self.selector2.close()

    def is_connected(self) -> bool:
        """Return True if both selectors are connected and open."""
        return (hasattr(self, 'selector1') and self.selector1.is_open
                and hasattr(self, 'selector2') and self.selector2.is_open)

    def set_path(self, reagent: str) -> None:
        """Route the selector to the specified reagent source.

        Uses cascaded addressing: addresses 1-11 go directly through
        selector 1; addresses 12+ engage the passthrough port on
        selector 1 and route through selector 2.

        Args:
            reagent: Reagent name (must exist in Fluidics_Reagent_Components.json).

        Raises:
            ValueError: If the reagent address exceeds the available selector range.
        """
        selector_port = self.selector_fluidics_dict[reagent]
        logger.info("Selecting reagent '%s' -> port %d", reagent, selector_port)
        print(f"selector port is {str(selector_port)}")
        if selector_port > self.source_limit:
            raise ValueError("You don't have enough selecotr for your reagents")
        else:
            # Calculate which selector and port to use via modular addressing:
            # - port_address: position within a single selector (0 means last port of previous unit)
            # - selector_need: how many additional selectors beyond the first are needed
            # Example: address 14 with unit_port=11 -> selector_need=1, port_address=3
            #   -> route selector1 to passthrough (port 12), selector2 to port 3
            port_address = int(selector_port % self.unit_port)
            selector_need = int(selector_port / self.unit_port)
            print(f'selector_need:{str(selector_need)}')
            print(f'port_address:{str(port_address)}')
            if selector_need > 0 and port_address != 0:
                # Address beyond first selector: engage passthrough on selector1,
                # then route selector2 to the remainder port
                self.move(self.selector1, self.pass_though_port)
                time.sleep(SELECTOR_SETTLE_SECONDS)
                self.move(self.selector2, port_address)
                time.sleep(SELECTOR_SETTLE_SECONDS)

            elif selector_need > 0 and port_address == 0:
                # Exact multiple of unit_port (e.g., address 11):
                # use the last port on selector1 directly
                self.move(self.selector1, self.unit_port)
                time.sleep(SELECTOR_SETTLE_SECONDS)

                print(f"move the first one to 11")

            else:
                # Address within first selector range (1-11): route directly
                self.move(self.selector1, selector_port)
                time.sleep(SELECTOR_SETTLE_SECONDS)
                print(f"move the first one {str(selector_port)}")

            time.sleep(3)

    def config_selector(self) -> None:
        """Test the selector by connecting and cycling through known reagent paths."""
        self.connect()
        self.set_path("incorporation buffer")
        self.set_path("gene primer mix")
        self.set_path("incorporation buffer")
        self.disconnect()

    def move(self, device: serial.Serial, position: int) -> None:
        """Send a move command to a specific selector device.

        Args:
            device: Serial connection (selector1 or selector2).
            position: Target port number (1-12).
        """
        valve_address=1 #default
        command = f"/{valve_address}B{position}R\r"
        device.write(command.encode())