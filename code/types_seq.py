"""
Shared type definitions for Seq-o-Matic.

Provides TypedDicts for structured data passed between modules,
and type aliases used across the codebase.
"""

from typing import TypedDict, Optional, Dict, List


class ReagentSource(TypedDict):
    """A single reagent in the Fluidics_Reagent_Components.json mapping."""
    solution: str
    address: int


class SequenceStep(TypedDict, total=False):
    """A single step in a fluidics protocol sequence JSON file.

    Fields vary by device type:
    - "pump": requires volume, source, flow_rate
    - "heat_device": requires time
    - "wait": requires time
    - "stopper": terminal step
    """
    volume: float
    source: Optional[str]
    flow_rate: Optional[float]
    time: Optional[int]
    temperature: Optional[float]
    device: str  # "pump" | "heat_device" | "wait" | "stopper"


class PumpConfig(TypedDict):
    """Configuration dict for IsmatecPumpDevice."""
    pump_name: str
    port: str
    tubingDiameter: float
    pumpID: str
    flowReversed: int


class SelectorConfig(TypedDict):
    """Configuration dict for a single Elveflow selector."""
    selector_name: str
    port: str


class HeaterStageConfig(TypedDict):
    """Configuration dict for a single heating stage."""
    heat_stage: str
    do_port: str
    do_line: str
    ai_line: str
    DAQ: str
    ao_port: str


class RelayConfig(TypedDict):
    """Configuration dict for the relay controller."""
    Relay_name: str
    port: str


class ScopeConfig(TypedDict, total=False):
    """Configuration dict from scope.json."""
    scope_name: str
    piezo: int
    ZDrive_safe_pos: float
    XYStage_fluidics_safe_pos: List[float]
    XYStage_image_safe_pos: List[float]
    scope_exposure_time_dict: Dict[str, int]
    z_dir: int
    stage_x_dir: int
    stage_y_dir: int
    pixel_size: float
    imwidth: int
    overlap: int
    geneseq_focus_target_channel: str
    Hyb_focus_target_channel: str
    maxproject_drive: str
    align_channel: str


# Type aliases
PositionList = List[Dict[str, float]]
ProtocolSequence = List[SequenceStep]
