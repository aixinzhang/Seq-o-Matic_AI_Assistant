"""
Centralized logging configuration for Seq-o-Matic.

Sets up a logger hierarchy with three handlers:
- FileHandler: writes all messages (DEBUG+) to log.txt with timestamps
- StreamHandler: writes INFO+ to console (stdout)
- TkHandler: writes INFO+ to LogWindow Tkinter widgets with color coding

Usage:
    from logging_config import setup_logging, get_logger

    # Call once at startup (after LogWindow.initialize()):
    setup_logging(log_file_path="path/to/log.txt")

    # In any module:
    logger = get_logger("fluidics")
    logger.info("Pumping 1.5 mL of PBST")
    logger.warning("Heater ramp timeout")
    logger.error("Pump not connected")
"""

import logging
import os

# ---------------------------------------------------------------------------
# Custom Tkinter handler -- routes log records to LogWindow widgets
# ---------------------------------------------------------------------------

class TkHandler(logging.Handler):
    """Logging handler that writes to the LogWindow Tkinter ScrolledText widgets.

    Maps logger names to notification panel color tags, and routes
    WARNING/ERROR to the warning panel in red.
    """

    # Map logger name suffix -> notification panel tag
    TAG_MAP = {
        'fluidics': 'reagent_highlight_from_fluidics',       # purple
        'fluidics.status': 'status_highlight_from_fluidics',  # yellow
        'scope': 'highlight_from_scope',                       # blue
        'device': 'device_highlight_from_device',              # black
        'mainwindow': 'highlight_from_mainwindow',             # blue
    }

    def __init__(self):
        super().__init__()
        self._log_window = None

    def _get_log_window(self):
        """Lazy-load LogWindow to avoid circular import at module level."""
        if self._log_window is None:
            from front_end.logwindow import LogWindow
            try:
                self._log_window = LogWindow.get()
            except RuntimeError:
                return None
        return self._log_window

    def emit(self, record):
        """Write the log record to the appropriate Tkinter widget."""
        lw = self._get_log_window()
        if lw is None:
            return

        try:
            msg = self.format(record) + "\n"

            # WARNING and ERROR -> red warning panel
            if record.levelno >= logging.WARNING:
                lw.warning_stw.insert('end', msg, 'warning')
                return

            # INFO -> notification panel with color based on logger name
            tag = self._resolve_tag(record.name)
            lw.notification_stw.insert('end', msg, tag)

        except Exception:
            self.handleError(record)

    def _resolve_tag(self, logger_name):
        """Find the best matching color tag for a logger name.

        Tries exact match first, then progressively shorter prefixes.
        Falls back to 'highlight_from_mainwindow' (blue).
        """
        # Strip the root prefix "seqomatic."
        name = logger_name.replace('seqomatic.', '')

        # Try exact match, then progressively shorter
        while name:
            if name in self.TAG_MAP:
                return self.TAG_MAP[name]
            # Trim last segment: "fluidics.status" -> "fluidics"
            if '.' in name:
                name = name.rsplit('.', 1)[0]
            else:
                break

        return 'highlight_from_mainwindow'


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_configured = False

LOG_FORMAT_FILE = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_FORMAT_CONSOLE = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_FORMAT_TK = "%(message)s"  # Widget color already encodes the source


def setup_logging(log_file_path=None):
    """Configure the seqomatic logger hierarchy.

    Safe to call multiple times -- only configures on the first call.
    Call after LogWindow.initialize() so TkHandler can find the widgets.

    Args:
        log_file_path: Path to the experiment log file. If None, only
                       console and Tk handlers are attached.
    """
    global _configured
    if _configured:
        # If called again with a new log file, just add/update the file handler
        if log_file_path:
            _update_file_handler(log_file_path)
        return

    root_logger = logging.getLogger("seqomatic")
    root_logger.setLevel(logging.DEBUG)

    # Console handler (INFO+)
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(LOG_FORMAT_CONSOLE, datefmt="%Y-%m-%d %H:%M:%S"))
    root_logger.addHandler(console)

    # Tkinter handler (INFO+) -- message only, color from tag
    tk_handler = TkHandler()
    tk_handler.setLevel(logging.INFO)
    tk_handler.setFormatter(logging.Formatter(LOG_FORMAT_TK))
    root_logger.addHandler(tk_handler)

    # File handler (DEBUG+) -- added if log_file_path provided
    if log_file_path:
        _add_file_handler(root_logger, log_file_path)

    _configured = True


def update_log_file(log_file_path):
    """Update the file handler to write to a new log file.

    Call this when the experiment directory changes.
    """
    _update_file_handler(log_file_path)


def get_logger(name):
    """Get a child logger under the seqomatic hierarchy.

    Args:
        name: Logger name suffix (e.g., 'fluidics', 'scope', 'device').

    Returns:
        logging.Logger instance.
    """
    return logging.getLogger(f"seqomatic.{name}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _add_file_handler(logger, path):
    """Add a file handler to the logger."""
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)
    fh = logging.FileHandler(path, mode='a', encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(LOG_FORMAT_FILE, datefmt="%Y-%m-%d %H:%M:%S"))
    fh.set_name("seqomatic_file_handler")
    logger.addHandler(fh)


def _update_file_handler(path):
    """Replace the existing file handler with one pointing to a new path."""
    root_logger = logging.getLogger("seqomatic")

    # Remove existing file handler if any
    for handler in root_logger.handlers[:]:
        if getattr(handler, 'name', None) == "seqomatic_file_handler":
            handler.close()
            root_logger.removeHandler(handler)

    _add_file_handler(root_logger, path)
