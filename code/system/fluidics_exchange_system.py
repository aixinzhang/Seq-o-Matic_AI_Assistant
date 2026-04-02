"""
Fluidics exchange orchestration system.

Coordinates pump, selector, heating stages, and relay devices to execute
multi-step fluidics protocols for sequencing experiments. Manages device
connections, protocol loading, and a timer-based sequence state machine.

Author: Aixin Zhang
"""
import json
import os
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from pytz import timezone

from device.Pump import IsmatecPumpDevice
from device.Selector import ElveflowMux
from device.Relay import KmtronicRelayCh4
from device.Heatingstage import heat_stage_group
from front_end.logwindow import (
    update_error, add_fluidics_status, add_fluidics_reagent,
    update_process_bar, update_process_label,
)
from constants import (
    FLUIDICS_WAIT_BETWEEN_STEPS_SECONDS, SELECTOR_SETTLE_SECONDS,
    DEFAULT_PUMP_RATE_ML_PER_MIN, DEFAULT_HEAT_TEMP_VOLTAGE,
    HEAT_DEFAULT_TEMP_VOLTAGE, SEQUENCE_FINISH_DELAY_SECONDS,
)
from system.fluidics.protocol_loader import load_protocol
from system.fluidics.sequence_runner import SequenceState
from logging_config import get_logger
from types_seq import ProtocolSequence, SequenceStep

logger = get_logger("fluidics")


class bcolors:
    """ANSI color codes for terminal output formatting."""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END='\033[0m'


def get_time() -> str:
    time_now = timezone('US/Pacific')
    time = str(datetime.now(time_now))[0:19] + "\n"
    return time

class FluidicSourceInfo(object):
    """Metadata for a single fluidic reagent source."""

    def __init__(self, name="sourceName", indexInComponentList=None, hardwareIndices=None):
        self.name = name
        self.index = indexInComponentList
        self.hardwareId = hardwareIndices


class FluidicsConstants():
    """Configuration constants for fluidics system timing and relay channels."""
    pumpBlockDeviceChannel=1
    vacuumChannel=2
    chamberSelectChannel= 0
    sinkBased=True
    pumpRate = 1.0
    vol = 1e-4
    bufferseconds = 1
    bufferms = 5*bufferseconds

    PUMP_BLOCK_OPEN_STATE = True
    PUMP_BLOCK_CLOSED_STATE = not PUMP_BLOCK_OPEN_STATE

    SELECT_BYPASS_STATE = True
    SELECT_CHAMBER_STATE = not SELECT_BYPASS_STATE

    VACUUM_OPEN_STATE = True
    VACUUM_CLOSED_STATE = not VACUUM_OPEN_STATE
    System_device=['pumpDevice','FluidicSelector','pumpBlockDevice']

class FluidicSystem():
    """Orchestrates all fluidics hardware for automated sequencing.

    Manages pump, selector, heating stages, and relay device lifecycles.
    Loads and executes multi-step fluidics protocols via a timer-based
    state machine (runSequence).

    Sequence status codes:
        0  = IDLE (not running)
        1  = RUNNING (sequence in progress)
        -1 = CANCELLED (user cancelled)
        -2 = FINISHED (sequence completed)

    Args:
        system_path: Root path to the code/ directory (for config files).
        pos_path: Experiment working directory (for logs and protocol copies).
        slide_hearter_dictionary: Dict mapping slide names to heater stage names.
    """

    def __init__(self, system_path: str, pos_path: str, slide_hearter_dictionary: Dict[str, str]) -> None:
        self.system_path = system_path
        with open(os.path.join(system_path,"config_file", "IsmatecPumpDevice_pump.json"), 'r') as r:
            self.pump1_cfg = json.load(r)
        with open(os.path.join(system_path, "config_file", "ElveflowMuxDevice_selector.json"), 'r') as r:
            self.selector_cfg = json.load(r)
        with open(os.path.join(system_path, "config_file", 'Fluidics_Reagent_Components.json'), 'r') as r:
            self.Fluidics_selector_components = json.load(r)
        self.selector_reagent = [i['solution'] for i in self.Fluidics_selector_components]
        self.address = [i['address'] for i in self.Fluidics_selector_components]
        self.selector_fluidics_dict = dict(zip(self.address, self.selector_reagent))

        self.slide_heater_dict = slide_hearter_dictionary
        with open(os.path.join(system_path, "config_file", "Heat_stage.json"), 'r') as r:
            self.Heater_cfg = json.load(r)
        self.Heater_cfg = [i for i in self.Heater_cfg if i['heat_stage'] in list(self.slide_heater_dict.values())]
        with open(os.path.join(self.system_path,"config_file", "KMtronic_relay.json"), 'r') as r:
            self.Relay_cfg = json.load(r)

        self.start_fluidics =1
        self.sourceInfoList = []
        self.currentSpeed = 0.0
        self.currentSource = None
        self.sequenceStatus = SequenceState.IDLE
        self.last_sequenceStatus = SequenceState.FINISHED
        self.sequenceIndex = 0
        self.config_fluidics_sequences = {}
        self.sequenceStateEndTime = 0
        self.pos_path=pos_path
        self.cycle_done=0
        self.start_image=0
        # Threading events for non-polling synchronization
        self.cycle_done_event = threading.Event()
        self.start_image_event = threading.Event()
        self.mlToPump=0
        self.disconnect_device=0
        self.waiting_time=FLUIDICS_WAIT_BETWEEN_STEPS_SECONDS
        self.heat_temp=DEFAULT_HEAT_TEMP_VOLTAGE
        self.chamber1=0
        self.chamber2=1
        self.chamber3=2
        self.chamber4 = 3
        self.cancel=0
        self.pumprate = DEFAULT_PUMP_RATE_ML_PER_MIN

        with open(os.path.join(self.system_path, "reagent_sequence_file", 'Fluidics_sequence_flush_all.json'), 'r') as r:
            self.FLUSH_ALL_SEQUENCE = json.load(r)
        with open(os.path.join(self.system_path, "reagent_sequence_file", 'Fluidics_sequence_fill_all.json'), 'r') as r:
            self.Fill_ALL_SEQUENCE = json.load(r)




    def write_log(self, txt: str) -> None:
        """Append text to the experiment log file (silently ignores errors).

        Also sends the message to the Python logger for structured logging.
        """
        logger.debug(txt.strip())
        try:
            f = open(os.path.join(self.pos_path, "log.txt"), "a")
            f.write(txt)
            f.close()
        except OSError:
            pass

    def config_pump(self) -> None:
        """Test pump connection: initialize, verify ID, then disconnect."""
        logger.info("Configuring pump on %s", self.pump1_cfg[0].get('port', '?'))
        self.pump = IsmatecPumpDevice(self.pump1_cfg[0])
        self.pump.initialize()
        self.pump.PumpDisconnect()
        logger.info("Pump configured successfully")

    def config_heater(self) -> None:
        """Test heater connection: connect, run self-test, then disconnect."""
        logger.info("Configuring heater (%d stages)", len(self.Heater_cfg))
        self.Heatingdevice=heat_stage_group(self.Heater_cfg,HEAT_DEFAULT_TEMP_VOLTAGE,self.pos_path)
        self.Heatingdevice.connect_heater_group()
        self.Heatingdevice.config()
        self.Heatingdevice.disconnect_heater_group()
        logger.info("Heater configured successfully")


    def connect_heater(self) -> None:
        """Create and connect heating device for experiment use."""
        self.Heatingdevice = heat_stage_group(self.Heater_cfg, self.heat_temp, self.pos_path)
        self.Heatingdevice.connect_heater_group()

    def disconnect_heater(self) -> None:
        """Disconnect heating device and release DAQ resources."""
        self.Heatingdevice.disconnect_heater_group()

    def connect_pump(self) -> None:
        """Create pump device and initialize serial connection."""
        logger.info("Connecting pump")
        self.pump  = IsmatecPumpDevice(self.pump1_cfg[0])
        self.pump.initialize()

    def is_pump_running(self) -> None:
        """Check if the pump is currently running."""
        self.pump.isPumpRunning()

    def disconnect_pump(self) -> None:
        """Disconnect the pump and close serial port."""
        self.pump.PumpDisconnect()

    def config_selector(self) -> None:
        """Test selector connection by cycling through known reagent paths."""
        self.selector=ElveflowMux(self.selector_cfg)
        self.selector.config_selector()

    def connect_selector(self) -> None:
        """Open serial connections to both selectors."""
        self.selector.connect()

    def disconnect_selector(self) -> None:
        """Close serial connections to both selectors."""
        self.selector.disconnect()

    def config_relay(self) -> None:
        """Test relay connection (stub -- relay is not fully implemented)."""
        self.relay=KmtronicRelayCh4(self.Relay_cfg[0]['port'])
        self.relay.on_connect_requested()
        self.relay.quit()

    def connect_relay(self) -> None:
        """Connect relay and enable channel 0 (stub -- no-op)."""
        self.relay=KmtronicRelayCh4(self.Relay_cfg[0]['port'])
        self.relay.on_connect_requested()
        self.relay.change_relay_state(0, True)

    def disconnect_relay(self) -> None:
        """Disconnect relay device (stub -- no-op)."""
        self.relay.quit()


    
    def isPumpRunning(self) -> int:
        return self.pump.isPumpRunning()
    def Get_Response(self) -> None:
        try:
            self.pump.GetResponse()
        except Exception:
            txt=get_time()+"pump is not connected correctly \n"
            logger.error("Pump is not connected correctly")
            print("pump is not connected correctly \n")
            update_error(txt)
            self.write_log(txt)
        return 
    
    def select_bypass(self, SELECT_BYPASS_STATE: bool) -> None:
        """Set all relay chambers to bypass state (stub -- relay not implemented)."""
        pass

    def select_chamber(self, SELECT_CHAMBER_STATE: bool) -> None:
        """Set all relay chambers to chamber state (stub -- relay not implemented)."""
        pass
    
    def stopPumping(self) -> None:
        self.pump.stopPump()


    def startPumping(self) -> None:
        self.pump.startPump()
    
    def cancelSequence(self) -> None:
        """Cancel the currently running sequence, stop pump, and signal heater cancel."""
        logger.warning("Sequence cancelled by user")
        self.stopPumping()
        self.Heatingdevice.cancel=1
        self.sequenceStatus = SequenceState.CANCELLED
        self.sequenceIndex = 0
        self.cycle_done = 1
        self.cycle_done_event.set()
        self.start_image=0

    
    def pumpVol(self, vol: float, rate: float) -> None:
        """Pump a specified volume at the given rate."""
        self.pump.pumpVolume(vol,rate)

    def setSource(self, sourceName: str) -> None:
        """Route the selector to the named reagent source, then wait for settling."""
        self.selector.set_path(sourceName)
        time.sleep(SELECTOR_SETTLE_SECONDS)

    def loadSequence(self, fluidicsSequence: ProtocolSequence) -> None:
        """Load a fluidics protocol sequence (list of step dicts) for execution."""
        self.fluidSequence=fluidicsSequence

        
    def updateStatus(self) -> None:
        """Log the current sequence status if it has changed."""
        if self.sequenceStatus == SequenceState.CANCELLED:
            if self.sequenceStatus != self.last_sequenceStatus:
                txt=get_time()+"Status Check : fluidics sequence was cancelled \n"
                self.write_log(txt)
                add_fluidics_status(txt)
                print(bcolors.OKBLUE+"Status Check: fluidics sequence cancelled"+bcolors.END)
                self.last_sequenceStatus = self.sequenceStatus
                self.last_sequenceStatus = SequenceState.CANCELLED
            return
        elif self.sequenceStatus == -2:
            txt=get_time()+"Status Check:sequence finished successfully\n"
            add_fluidics_status(txt)
            self.write_log(txt)
            print(bcolors.OKBLUE+" Status Check:sequence finished successfully"+bcolors.END)
            self.last_sequenceStatus = SequenceState.FINISHED
        elif self.sequenceStatus == SequenceState.RUNNING:
            pass
            return
        
    def startSequence(self) -> None:
        """Begin executing the loaded fluidics sequence.

        Resets progress tracking and starts the runSequence state machine.
        No-op if a sequence is already running.
        """
        if self.sequenceStatus == SequenceState.RUNNING:
            txt="System is still running! \n"
            print('System is still running!')
            self.write_log(txt)
            add_fluidics_status(txt)
            return
        self.cycle_done = 0
        self.cycle_done_event.clear()
        self.start_image=0
        self.start_image_event.clear()
        self.idx=100/len(self.fluidSequence)
        update_process_bar(0)
        update_process_label("Fluidics exchanging")
        self.runSequence()

    def finishSequence(self) -> None:
        """Mark the current sequence as complete and signal readiness for imaging."""
        self.cycle_done = 1
        self.cycle_done_event.set()
        self.start_image=1
        self.start_image_event.set()
        self.sequenceIndex = 0
        self.sequenceStatus = 0
        self.last_sequenceStatus=-2



    def runSequence(self) -> None:
        """Execute the next step in the loaded fluidics sequence.

        This is the core state machine, called recursively via threading.Timer.
        Each invocation processes one step from self.fluidSequence and schedules
        the next call after a waiting_time delay (default 3 seconds).

        Step types handled:
        - "pump": Select reagent source, pump specified volume, wait for completion.
        - "heat_device": Heat all stages for specified duration (blocking via threads).
        - "wait": Incubate at room temperature for specified duration.
        - "stopper"/other: Select end source and continue.

        Sets cycle_done=1 and start_image=1 when the full sequence completes.
        """
        # --- Guard: check for cancel signals before processing ---
        if self.cancel==1:
            txt = "Sequence is canceled!\n"
            print("Sequence is canceled!")
            self.write_log(txt)
            add_fluidics_reagent(txt)
            return
        if self.sequenceStatus == SequenceState.CANCELLED:
            print("system canceled (from runsequence tread)!")
            update_process_bar(0)
            update_process_label("Process")
            self.updateStatus()
            return

        # --- Guard: check if all steps have been executed ---
        if self.sequenceIndex >= len(self.fluidSequence):
            self.sequenceStatus = SequenceState.FINISHED
            txt=get_time()+"sequence finished successfully!"+"\n"
            print(txt)
            self.write_log(txt)
            update_process_bar(0)
            update_process_label("Process")
            add_fluidics_reagent(get_time()+"sequence finished successfully!"+"\n")
            self.long_heat=0
            # Signal to the automation controller that this cycle's fluidics are done
            self.cycle_done = 1
            self.start_image=1
            self.sequenceIndex = 0
            self.sequenceStatus = 0
            self.last_sequenceStatus = SequenceState.FINISHED
            time.sleep(SEQUENCE_FINISH_DELAY_SECONDS)
            return

        # --- Guard: if pump is still running from previous step, retry immediately ---
        if self.pump.isPumpRunning() == 1:
            txt = "System is still running!\n"
            print("pump still running. wait ")
            self.write_log(txt)
            add_fluidics_reagent(txt)
            self.run_sequence_thread = threading.Timer(0, self.runSequence)
            self.run_sequence_thread.start()
            return

        # --- Process the current step ---
        sequenceIndex = self.sequenceIndex
        sequenceState = self.fluidSequence[sequenceIndex]
        self.idx =self.idx+ 100 / len(self.fluidSequence)
        update_process_bar(self.idx)
        self.sequenceStatus = SequenceState.RUNNING

        if sequenceState["device"] =="pump" :
            expectedTime = int(60 * (sequenceState["volume"] / self.pumprate))
            txt = "timer  = " + str(expectedTime + FluidicsConstants.bufferms) + "\n"
            add_fluidics_reagent(txt)
            self.write_log(txt)
            source=self.selector_fluidics_dict[int(sequenceState["source"])]
            self.setSource(source)
            add_fluidics_reagent(f"name: {sequenceState['Solution name']}\n")
            print(sequenceState["source"])
            txt=get_time()+f"current in step {str(sequenceIndex+1)} pumping: {sequenceState['Solution name']}\n"
            logger.info("Step %d/%d: pumping %.1f mL of %s at %.1f mL/min",
                        sequenceIndex + 1, len(self.fluidSequence),
                        sequenceState["volume"], sequenceState['Solution name'], self.pumprate)
            add_fluidics_reagent(txt)
            self.write_log(txt)
            print(bcolors.WARNING + txt+bcolors.END)
            self.pumpVol(sequenceState["volume"],self.pumprate)
            start=datetime.now()
            time_diff=0
            self.updateStatus()
            self.sequenceIndex += 1
            while time_diff<=expectedTime + FluidicsConstants.bufferms:
                if self.sequenceStatus==-1:
                    break
                time.sleep(2)
                time_diff=(datetime.now()-start).total_seconds()
            if self.sequenceStatus != -1:
                self.run_sequence_thread = threading.Timer(self.waiting_time, self.runSequence)
                self.run_sequence_thread.start()

        elif sequenceState["device"] =="heat_device" :
            txt=get_time()+f"current in step {str(sequenceIndex+1)} heating: {str(sequenceState['time'])} seconds\n"
            logger.info("Step %d/%d: heating for %d seconds",
                        sequenceIndex + 1, len(self.fluidSequence), sequenceState["time"])
            add_fluidics_reagent(txt)
            self.write_log(txt)
            print(bcolors.WARNING + txt+bcolors.END)
            self.Heatingdevice.heat_for_3min(sequenceState["time"])
            self.sequenceIndex += 1
            self.updateStatus()
            if self.Heatingdevice.cancel==1 :
                txt = get_time() + "Heater is cancelled "+ "\n"
                add_fluidics_reagent(txt)
                self.write_log(txt)
                print(bcolors.WARNING + txt + bcolors.END)
            elif self.Heatingdevice.heat_status==0:
                txt = get_time() + "Heater is wrong " + "\n"
                add_fluidics_reagent(txt)
                self.write_log(txt)
                print(bcolors.WARNING + txt + bcolors.END)
                return
            else:
                self.run_sequence_thread = threading.Timer(self.waiting_time, self.runSequence)
                self.run_sequence_thread.start()

        elif sequenceState["device"] == "wait":
            txt = get_time() + "Incubating for " + str(sequenceState["time"])+" seconds."+"\n"
            logger.info("Step %d/%d: incubating for %d seconds",
                        sequenceIndex + 1, len(self.fluidSequence), sequenceState["time"])
            add_fluidics_reagent(txt)
            self.write_log(txt)
            print(bcolors.WARNING + txt + bcolors.END)
            time_diff = 0
            start = datetime.now()
            self.updateStatus()
            self.sequenceIndex += 1
            expectedTime=sequenceState["time"]
            while time_diff <= expectedTime + FluidicsConstants.bufferms:
                if self.sequenceStatus == SequenceState.CANCELLED:
                    break
                time.sleep(2)
                time_diff = (datetime.now() - start).total_seconds()
            if self.sequenceStatus != -1:
                self.run_sequence_thread = threading.Timer(self.waiting_time, self.runSequence)
                self.run_sequence_thread.start()
        else:
            source = self.selector_fluidics_dict[int(sequenceState["source"])]
            self.setSource(source)
            self.sequenceIndex += 1
            self.run_sequence_thread = threading.Timer(0, self.runSequence)
            self.run_sequence_thread.start()
        return

    def find_protocol(self, Type: str) -> ProtocolSequence:
        """Load a fluidics protocol JSON file based on process type name.

        Delegates to system.fluidics.protocol_loader.load_protocol().

        Args:
            Type: Process type string identifying which protocol to load.

        Returns:
            List of step dicts parsed from the protocol JSON file.
        """
        return load_protocol(
            protocol_type=Type,
            sequence_dir="reagent_sequence_file",
            backup_dir=self.pos_path,
            write_log=self.write_log,
        )













