"""
Centralized constants for the Seq-o-Matic system.

Replaces magic numbers scattered across the codebase with named constants
for maintainability and clarity.
"""

# =============================================================================
# Heating Stage Constants
# =============================================================================
HEAT_RAMP_TIMEOUT_SECONDS = 300       # Max time (s) to wait for temp ramp-up
HEAT_TEMP_TOLERANCE = 0.15            # Voltage tolerance for "at target" check
HEAT_TEMP_FAILURE_TOLERANCE = 0.5     # Voltage delta indicating heater failure
HEAT_INITIAL_TEMP_MIN = 1.5           # Min acceptable initial temp voltage
HEAT_INITIAL_TEMP_MAX = 3.0           # Max acceptable initial temp voltage
HEAT_CONFIG_WARMUP_SECONDS = 15       # Duration of config self-test heat pulse
HEAT_CONFIG_DELTA_THRESHOLD = 0.05    # Min temp change to confirm heater works
HEAT_IDLE_VOLTAGE = 0.1               # Voltage to set when ending heat
HEAT_DEFAULT_TEMP_VOLTAGE = 5.7       # Default target temperature voltage
HEAT_MONITOR_INTERVAL_SECONDS = 5     # Sleep between temp reads during ramp
HEAT_HOLD_MONITOR_INTERVAL_SECONDS = 10  # Sleep between temp reads during hold
HEAT_THREAD_STAGGER_SECONDS = 3       # Delay between starting each heater thread

# =============================================================================
# Fluidics Constants
# =============================================================================
FLUIDICS_WAIT_BETWEEN_STEPS_SECONDS = 3   # Delay between sequence steps
PUMP_WAIT_BUFFER_SECONDS = 5              # Extra time after expected pump duration
SELECTOR_SETTLE_SECONDS = 2               # Wait after selector move
SELECTOR_UNIT_PORT_COUNT = 11             # Ports per selector unit
SELECTOR_PASSTHROUGH_PORT = 12            # Port for cascading to next selector
DEFAULT_PUMP_RATE_ML_PER_MIN = 1.5        # Default pump flow rate
DEFAULT_HEAT_TEMP_VOLTAGE = 5.6           # Default heat temp voltage for experiments
SEQUENCE_FINISH_DELAY_SECONDS = 5         # Delay after sequence completion

# =============================================================================
# Imaging Constants
# =============================================================================
IMAGE_WIDTH_PX = 3200                 # Camera image width in pixels
LIVEVIEW_CROP_START = 500             # Start pixel for live view crop
LIVEVIEW_CROP_END = 1200              # End pixel for live view crop
TOPHAT_FILTER_SIZE = (10, 10)         # Morphological top-hat filter kernel size
DENOISING_PERCENTILE = 85            # Percentile threshold for denoising

# =============================================================================
# GUI Constants
# =============================================================================
MAIN_WINDOW_GEOMETRY = "1250x800"
DEVICE_POPUP_GEOMETRY = "500x170"
