
"""
Heating stage controller for Bioptech heating stages via NI DAQ.

Controls one or more heating stages through a National Instruments DAQ device.
Each stage has:
- A shared analog output (ao) for voltage/power control
- An individual digital output (do) to enable/disable the heater
- An individual analog input (ai) for temperature monitoring

Heating runs in parallel threads (one per stage) with temperature monitoring
and timeout protection.

Author: Aixin Zhang
"""
import os
import time
import threading
import queue
from datetime import datetime
from typing import List

import nidaqmx
import nidaqmx.system
from pytz import timezone

from front_end.logwindow import update_error
from device.base import HeaterDevice
from types_seq import HeaterStageConfig
from constants import (
    HEAT_RAMP_TIMEOUT_SECONDS, HEAT_TEMP_TOLERANCE, HEAT_TEMP_FAILURE_TOLERANCE,
    HEAT_INITIAL_TEMP_MIN, HEAT_INITIAL_TEMP_MAX, HEAT_CONFIG_WARMUP_SECONDS,
    HEAT_CONFIG_DELTA_THRESHOLD, HEAT_IDLE_VOLTAGE, HEAT_MONITOR_INTERVAL_SECONDS,
    HEAT_HOLD_MONITOR_INTERVAL_SECONDS, HEAT_THREAD_STAGGER_SECONDS,
)
from logging_config import get_logger

logger = get_logger("device.heater")


def get_time() -> str:
    """Return the current US/Pacific time as a formatted string."""
    time_now = timezone('US/Pacific')
    time = str(datetime.now(time_now))[0:16] + "\n"
    return time


class heat_stage_group(HeaterDevice):
    """Controller for a group of Bioptech heating stages via NI DAQ.

    Manages multiple heating stages that share a single analog output
    for voltage control but have individual digital outputs for enable/disable
    and individual analog inputs for temperature readback.

    Args:
        config_file: List of dicts with DAQ channel assignments per stage.
        temp: Target temperature voltage (analog output value, e.g., 5.7).
        pos_path: Experiment directory path for writing log and temp files.
    """

    def __init__(self, config_file: List[HeaterStageConfig], temp: float, pos_path: str) -> None:
        self.heat_stage_id_ls = config_file
        self.heat_mode = False
        self.image_mode = True
        self.ao_port = self.heat_stage_id_ls[0]["DAQ"]+"/"+self.heat_stage_id_ls[0]["ao_port"]
        self.temp = temp
        self.cancel = 0
        self.num_devices = len(self.heat_stage_id_ls)
        self.status=[0]*self.num_devices
        self.pos_path=pos_path
        self.heat_status=0


    # --- HeaterDevice interface methods ---

    def connect(self) -> None:
        """Initialize hardware connections (alias for connect_heater_group)."""
        self.connect_heater_group()

    def disconnect(self) -> None:
        """Release hardware resources (alias for disconnect_heater_group)."""
        self.disconnect_heater_group()

    def heat(self, duration_seconds: float) -> bool:
        """Heat for the specified duration. Returns True if all stages succeeded."""
        self.heat_for_3min(duration_seconds)
        return self.heat_status == 1

    # --- Original methods ---

    def connect_heater_group(self) -> None:
        """Initialize DAQ tasks for all heating stages.

        Creates analog output (shared), digital output (per stage),
        and analog input (per stage) NI-DAQmx tasks.
        """
        self.do_task = [None] * self.num_devices
        self.ai_task = [None] * self.num_devices
        self.dev_name=[None] * self.num_devices
        self.ao_task = nidaqmx.Task()
        self.ao_task.ao_channels.add_ao_voltage_chan(self.ao_port, min_val=0.0, max_val=5.0)
        self.ao_task.start()
        for i in range(self.num_devices):
            print(i)
            self.dev_name[i]=self.heat_stage_id_ls[i]['heat_stage']
            self.do_task[i] = nidaqmx.Task()
            self.ai_task[i] = nidaqmx.Task()
            do_channel = self.heat_stage_id_ls[i]['DAQ'] + '/' + self.heat_stage_id_ls[i]['do_port'] + '/' + \
                         self.heat_stage_id_ls[i]['do_line']
            ai_channel = self.heat_stage_id_ls[i]['DAQ'] + '/' + self.heat_stage_id_ls[i]['ai_line']
            self.do_task[i].do_channels.add_do_chan(do_channel)
            self.ai_task[i].ai_channels.add_ai_voltage_chan(ai_channel)
            self.do_task[i].write(self.image_mode)



    def disconnect_heater_group(self) -> None:
        """Close all DAQ tasks and release hardware resources."""
        self.ao_task.close()
        for i in range(self.num_devices):
            self.ai_task[i].close()
            self.do_task[i].close()

    def start_heat(self) -> None:
        """Apply heating voltage and enable all digital heater outputs."""
        logger.info("Starting heat at voltage %.1f for %d stages", self.temp, self.num_devices)
        self.ao_task.write(self.temp)
        for i in range(self.num_devices):
            self.do_task[i].write(self.heat_mode)
        txt=get_time()+"start heat\n"
        print("start heat")
        self.write_log(txt)


    def end_heat(self) -> None:
        """Reduce heating voltage to idle level (0.1V)."""
        logger.info("Ending heat, reducing voltage to %.1f", HEAT_IDLE_VOLTAGE)
        self.ao_task.write(HEAT_IDLE_VOLTAGE)
        txt = get_time() + "End heat\n"
        print("End heat")
        self.write_log(txt)

    def heat_for_3min_single(self, i: int) -> None:
        """Heat a single stage, monitoring temperature until stable then holding.

        Two phases:
        1. Ramp-up: Wait until temperature reaches target (within 0.15V tolerance),
           with a 300-second timeout. If timeout and temp is >0.5V below target,
           the stage is flagged as failed.
        2. Hold: Maintain heat for self.heat_time seconds while logging temperature.

        Args:
            i: Index of the heating stage device.
        """
        try:
            temp = self.ai_task[i].read()
            name=self.dev_name[i]
            start_single = datetime.now()
            time_diff_single = 0
            while temp <= self.temp - HEAT_TEMP_TOLERANCE and time_diff_single <= HEAT_RAMP_TIMEOUT_SECONDS and self.cancel==0:
                time.sleep(HEAT_MONITOR_INTERVAL_SECONDS)
                time_diff_single = (datetime.now() - start_single).total_seconds()
                temp = self.ai_task[i].read()
                print(f"device {name} temp: {temp}")
                txt=get_time()+f"device {name} temp: {temp}\n"
                self.write_log(txt)
                with open(os.path.join(self.pos_path, 'temp.txt'), 'a') as fp:
                    fp.write(txt)
                fp.close()
            if time_diff_single >= HEAT_RAMP_TIMEOUT_SECONDS and temp <= self.temp - HEAT_TEMP_FAILURE_TOLERANCE:
                print(f"Heating stage had an issue: Device {name} is off!")
                txt=f"Heating stage had an issue: Device {name} is off!\n"
                self.write_log(txt)
                update_error(txt)
                with open(os.path.join(self.pos_path, 'temp.txt'), 'a') as fp:
                    fp.write(txt)
                fp.close()
                self.do_task[i].write(self.image_mode)
                self.status[i] = 0
            else:
                print(f"start stable heat {str(self.heat_time)} mins for Device {name}")
                print(f"heat for {str(self.heat_time)}")
                txt=get_time()+f"start stable heat for Device {name} \n"
                self.write_log(txt)
                with open(os.path.join(self.pos_path, 'temp.txt'), 'a') as fp:
                    fp.write(txt)
                fp.close()
                start_heat = datetime.now()
                heat_time_diff = 0
                while heat_time_diff <= self.heat_time and self.cancel == 0:
                    temp = self.ai_task[i].read()
                    txt = f"device {name}  temp: {str(temp)} \n"
                    with open(os.path.join(self.pos_path, 'temp.txt'), 'a') as fp:
                        fp.write(txt)
                    fp.close()
                    print(f"device {name}  temp: {str(temp)} \n")
                    heat_time_diff = (datetime.now() - start_heat).total_seconds()
                    time.sleep(HEAT_HOLD_MONITOR_INTERVAL_SECONDS)
                self.do_task[i].write(self.image_mode)
                txt=get_time()+f"Device {name} is done with heat successfully!\n"
                self.write_log(txt)
                self.status[i]=1

        except Exception as e:
            logger.error("Device %s heating error: %s", name, e)
            self.do_task[i].write(self.image_mode)
            self.result_queue.put((i, f"Error in device {name}: {str(e)}"))
            txt = get_time() + f"Device {name}  has error!\n"
            self.write_log(txt)
            update_error(txt)

    def heat_for_3min(self, heattime: float) -> None:
        """Heat all stages in parallel for the specified duration.

        Starts heating, then spawns one thread per stage for temperature
        monitoring and hold timing. Blocks until all threads complete.
        Sets self.heat_status to 1 if all stages succeed, 0 otherwise.

        Args:
            heattime: Duration to hold at target temperature in seconds.
        """
        self.heat_time=heattime
        threads=[]
        self.start_heat()
        self.result_queue = queue.Queue()
        for i in range(self.num_devices):
            t = threading.Thread(target=self.heat_for_3min_single, args=(i,))
            t.start()
            threads.append(t)
            time.sleep(HEAT_THREAD_STAGGER_SECONDS)
        for t in threads:
            t.join()

        if sum(self.status)==1*self.num_devices:
            txt = get_time() +"All stages heated successfully"+"\n"
            logger.info("All %d stages heated successfully", self.num_devices)
            self.write_log(txt)
            self.heat_status=1
        elif sum(self.status)==0:
            txt = get_time() + "All stages has issue" + "\n"
            logger.error("All stages failed heating")
            self.write_log(txt)
            self.heat_status = 0
        else:
            txt = get_time() + "One or more stages has issue" + "\n"
            logger.warning("Partial heating failure: %d/%d stages succeeded",
                          sum(self.status), self.num_devices)
            self.write_log(txt)
            self.heat_status = 0
        self.end_heat()
        return

    def check_temp(self) -> None:
        """Read and print the current temperature from all stages."""
        for i in range(self.num_devices):
            value = self.ai_task[i].read()
            print(value)

    def write_log(self, txt: str) -> None:
        """Append text to the experiment log file."""
        f = open(os.path.join(self.pos_path,"log.txt"), "a")
        f.write(txt)
        f.close()

    def config(self) -> None:
        """Self-test the heating stages.

        Validates that:
        1. Initial temperature readings are within a safe range (1.5-3.0V).
        2. Each heater responds to a 15-second heating pulse (temp delta > 0.05V).

        Raises:
            SystemError: If any heater fails validation.
        """
        temp_all_init = []
        for i in range(self.num_devices):
            temp = self.ai_task[i].read()
            print(temp)
            temp_all_init.append(temp)
        for temp in temp_all_init:
            if temp <= HEAT_INITIAL_TEMP_MIN or temp >= HEAT_INITIAL_TEMP_MAX:
                self.disconnect_heater_group()
                self.write_log(f"Heater {self.dev_name[i]} reads temp is extremly High/Low at beginning")
                raise SystemError(f"Heater {self.dev_name[i]} reads temp is extremly High/Low at beginning")
        self.start_heat()
        time.sleep(HEAT_CONFIG_WARMUP_SECONDS)
        self.end_heat()
        for i in range(self.num_devices):
            temp = self.ai_task[i].read()
            print(temp)
            if temp-temp_all_init[i]<=HEAT_CONFIG_DELTA_THRESHOLD:
                self.disconnect_heater_group()
                self.write_log(f"Heater {self.dev_name[i]} didn't heat!")
                raise SystemError(f"Heater {self.dev_name[i]} didn't heat!")


