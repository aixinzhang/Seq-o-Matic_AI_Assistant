"""
Hardware control tools for the AI agent.

Defines the tool schemas (what Claude can call) and the execution
functions (what actually talks to hardware). Every command requires
user confirmation before executing.

Usage:
    from hardware_tools import TOOLS, execute_tool

    # Claude returns tool_use blocks -> execute them
    result = execute_tool(tool_name, tool_input, confirm_fn)
"""

import sys
import os
import time

# Add code/ to path so we can import device modules
_code_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "code"))
if _code_path not in sys.path:
    sys.path.insert(0, _code_path)

# Add vendored packages
_vendor_path = os.path.join(_code_path, "supplementary", "package")
if _vendor_path not in sys.path:
    sys.path.insert(0, _vendor_path)


# ---------------------------------------------------------------------------
# Tool definitions (sent to Claude so it knows what it can call)
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "connect_pump",
        "description": "Connect to the Ismatec peristaltic pump via serial port. Must be called before any pump operations.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "disconnect_pump",
        "description": "Disconnect the pump and close the serial port.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "pump_volume",
        "description": "Pump a specified volume of fluid at a given flow rate. The selector must be set to the desired reagent first.",
        "input_schema": {
            "type": "object",
            "properties": {
                "volume_ml": {
                    "type": "number",
                    "description": "Volume to pump in milliliters (mL)",
                },
                "rate_ml_per_min": {
                    "type": "number",
                    "description": "Flow rate in mL/min. Default is 1.5",
                    "default": 1.5,
                },
            },
            "required": ["volume_ml"],
        },
    },
    {
        "name": "stop_pump",
        "description": "Immediately stop the pump.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "is_pump_running",
        "description": "Check if the pump is currently running. Returns running/stopped/error status.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "connect_selector",
        "description": "Connect to the Elveflow fluid selector multiplexers. Must be called before selecting reagents.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "disconnect_selector",
        "description": "Disconnect the fluid selectors.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "select_reagent",
        "description": "Route the fluid selector to a specific reagent. Available reagents: incorporation buffer, PBST, Iodoacetamide Blocker, IRM, USM, CRM, FISH WASH, STRIP, hyb oligos mix, DAPI, bc primer mix, gene primer mix, hyb oligos mix 2, END, hyb oligos mix 3, hyb oligos mix 4",
        "input_schema": {
            "type": "object",
            "properties": {
                "reagent_name": {
                    "type": "string",
                    "description": "Name of the reagent to select (must match Fluidics_Reagent_Components.json exactly)",
                },
            },
            "required": ["reagent_name"],
        },
    },
    {
        "name": "connect_heater",
        "description": "Connect to the heating stages via NI DAQ. Must be called before heating.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "disconnect_heater",
        "description": "Disconnect the heating stages and release DAQ resources.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "start_heating",
        "description": "Heat all connected stages for a specified duration in seconds.",
        "input_schema": {
            "type": "object",
            "properties": {
                "duration_seconds": {
                    "type": "number",
                    "description": "How long to heat in seconds. Typical value is 180 (3 minutes).",
                },
            },
            "required": ["duration_seconds"],
        },
    },
    {
        "name": "run_protocol",
        "description": "Run a complete fluidics protocol sequence (e.g., bcseq01, geneseq02+, HYB, strip). This executes multiple pump/heat/wait steps automatically.",
        "input_schema": {
            "type": "object",
            "properties": {
                "protocol_name": {
                    "type": "string",
                    "description": "Protocol type: geneseq01, geneseq02+, bcseq01, bcseq02+, HYB, HYB_rehyb, add_gene_primer, add_bc_primer, strip",
                },
            },
            "required": ["protocol_name"],
        },
    },
    {
        "name": "pump_reagent",
        "description": "Select a reagent AND pump a specified volume. Convenience tool that combines select_reagent + pump_volume.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reagent_name": {
                    "type": "string",
                    "description": "Name of the reagent to pump",
                },
                "volume_ml": {
                    "type": "number",
                    "description": "Volume in mL",
                },
                "rate_ml_per_min": {
                    "type": "number",
                    "description": "Flow rate in mL/min. Default 1.5",
                    "default": 1.5,
                },
            },
            "required": ["reagent_name", "volume_ml"],
        },
    },
]


# ---------------------------------------------------------------------------
# Hardware state (lazy-loaded devices)
# ---------------------------------------------------------------------------

_fluidics = None


def _get_fluidics():
    """Lazy-load the FluidicSystem."""
    global _fluidics
    if _fluidics is None:
        from system.fluidics_exchange_system import FluidicSystem
        _fluidics = FluidicSystem(
            system_path=_code_path,
            pos_path=os.getcwd(),
            slide_hearter_dictionary={},
        )
    return _fluidics


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------

def describe_action(tool_name, tool_input):
    """Return a human-readable description of what a tool call will do."""
    descriptions = {
        "connect_pump": "Connect to the Ismatec pump",
        "disconnect_pump": "Disconnect the pump",
        "pump_volume": f"Pump {tool_input.get('volume_ml', '?')} mL at {tool_input.get('rate_ml_per_min', 1.5)} mL/min",
        "stop_pump": "STOP the pump immediately",
        "is_pump_running": "Check pump status",
        "connect_selector": "Connect to the fluid selectors",
        "disconnect_selector": "Disconnect the fluid selectors",
        "select_reagent": f"Select reagent: {tool_input.get('reagent_name', '?')}",
        "connect_heater": "Connect to the heating stages",
        "disconnect_heater": "Disconnect the heating stages",
        "start_heating": f"Heat all stages for {tool_input.get('duration_seconds', '?')} seconds",
        "run_protocol": f"Run full protocol: {tool_input.get('protocol_name', '?')}",
        "pump_reagent": f"Select {tool_input.get('reagent_name', '?')} and pump {tool_input.get('volume_ml', '?')} mL at {tool_input.get('rate_ml_per_min', 1.5)} mL/min",
    }
    return descriptions.get(tool_name, f"Execute {tool_name}")


def execute_tool(tool_name, tool_input):
    """Execute a hardware tool command. Returns a result string.

    Args:
        tool_name: Name of the tool to execute.
        tool_input: Dict of parameters.

    Returns:
        String describing the result.
    """
    fs = _get_fluidics()

    try:
        if tool_name == "connect_pump":
            fs.connect_pump()
            return "Pump connected successfully"

        elif tool_name == "disconnect_pump":
            fs.disconnect_pump()
            return "Pump disconnected"

        elif tool_name == "pump_volume":
            volume = tool_input["volume_ml"]
            rate = tool_input.get("rate_ml_per_min", 1.5)
            fs.pumpVol(volume, rate)
            expected_time = int(60 * volume / rate)
            return f"Pumping {volume} mL at {rate} mL/min (estimated {expected_time} seconds)"

        elif tool_name == "stop_pump":
            fs.stopPumping()
            return "Pump stopped"

        elif tool_name == "is_pump_running":
            status = fs.isPumpRunning()
            if status == 1:
                return "Pump is RUNNING"
            elif status == 0:
                return "Pump is STOPPED"
            else:
                return "Pump status: ERROR (unexpected response)"

        elif tool_name == "connect_selector":
            fs.selector = __import__('device.Selector', fromlist=['ElveflowMux']).ElveflowMux(fs.selector_cfg)
            fs.connect_selector()
            return "Fluid selectors connected"

        elif tool_name == "disconnect_selector":
            fs.disconnect_selector()
            return "Fluid selectors disconnected"

        elif tool_name == "select_reagent":
            reagent = tool_input["reagent_name"]
            fs.setSource(reagent)
            return f"Selector routed to: {reagent}"

        elif tool_name == "connect_heater":
            fs.connect_heater()
            return "Heating stages connected"

        elif tool_name == "disconnect_heater":
            fs.disconnect_heater()
            return "Heating stages disconnected"

        elif tool_name == "start_heating":
            duration = tool_input["duration_seconds"]
            fs.Heatingdevice.heat_for_3min(duration)
            if fs.Heatingdevice.heat_status == 1:
                return f"Heating complete ({duration} seconds, all stages OK)"
            else:
                return f"Heating finished but one or more stages had issues"

        elif tool_name == "run_protocol":
            protocol_name = tool_input["protocol_name"]
            protocol = fs.find_protocol(protocol_name)
            fs.loadSequence(protocol)
            fs.startSequence()
            return f"Protocol '{protocol_name}' started ({len(protocol)} steps)"

        elif tool_name == "pump_reagent":
            reagent = tool_input["reagent_name"]
            volume = tool_input["volume_ml"]
            rate = tool_input.get("rate_ml_per_min", 1.5)
            fs.setSource(reagent)
            fs.pumpVol(volume, rate)
            expected_time = int(60 * volume / rate)
            return f"Selected {reagent}, pumping {volume} mL at {rate} mL/min ({expected_time}s)"

        else:
            return f"Unknown tool: {tool_name}"

    except Exception as e:
        return f"ERROR: {str(e)}"
