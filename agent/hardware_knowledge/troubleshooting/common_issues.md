# Common Hardware Issues

## Pump

### Pump not responding
1. Check USB cable connection
2. Verify COM port in Device Manager matches `IsmatecPumpDevice_pump.json`
3. Check power supply to pump
4. Try: disconnect and reconnect USB, then re-run Config Device

### Pump running but no flow
1. Check tubing for kinks or blockages
2. Check tubing is properly seated in pump head rollers
3. Check tubing diameter matches config (currently 0.51mm)
4. Replace tubing if worn (visible flattening or discoloration)

### Pump flow direction reversed
1. Check `flowReversed` setting in `IsmatecPumpDevice_pump.json`
2. Physically check tubing orientation in pump head

## Selector

### Selector not switching
1. Check both COM ports in Device Manager match `ElveflowMuxDevice_selector.json`
2. Listen for valve click sound when switching
3. Check 9600 baud rate matches selector DIP switch settings

### Wrong reagent delivered
1. Verify `Fluidics_Reagent_Components.json` address mapping matches physical tubing connections
2. Run Config Device -> selector group to test switching

## Heating Stage

### Heater not reaching temperature
1. Check NI DAQ device name matches `Heat_stage.json` (e.g., "Dev2")
2. Verify analog output voltage (should read ~5.7V during heating)
3. Check digital output line enables for each stage
4. Run Config Device -> heater group (15-second self-test)

### Temperature reading abnormal
1. Check analog input wiring for the specific stage
2. Normal idle reading: 1.5-3.0V
3. If reading is 0V or 5V: wiring is disconnected or shorted

## Microscope

### Micro-Manager not connecting
1. Ensure Micro-Manager 2.0 is running BEFORE launching Seq-o-Matic
2. Check that the correct config file is loaded in Micro-Manager
3. Verify ZMQ bridge port (default: 4827) is not blocked

### Stage not moving
1. Check XY stage safe positions in `scope.json` are within range
2. Verify `z_dir`, `stage_x_dir`, `stage_y_dir` signs match your setup
3. Check Z drive safe position (`ZDrive_safe_pos`) is correct

## Relay

### Relay not implemented
The relay controller (KMtronic) is currently stubbed in the software.
All relay methods are no-ops. The hardware may still be physically wired
but is not software-controlled.
