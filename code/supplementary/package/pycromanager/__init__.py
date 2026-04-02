name = "pycromanager"

# Ensure the vendored ndtiff package is importable from the local supplementary folder
import sys as _sys
import os as _os
# After flattening, ndtiff lives at .../package/ndtiff/ (sibling of pycromanager/)
# So we add .../package/ to sys.path
_vendor_path = _os.path.normpath(_os.path.join(_os.path.dirname(__file__), '..'))
if _vendor_path not in _sys.path:
    _sys.path.insert(0, _vendor_path)

from pycromanager.acquisition.java_backend_acquisitions import JavaBackendAcquisition, MagellanAcquisition, XYTiledAcquisition, ExploreAcquisition
from pycromanager.acquisition.acquisition_superclass import multi_d_acquisition_events
from pycromanager.acquisition.acq_constructor import Acquisition
from pycromanager.headless import start_headless, stop_headless
from pycromanager.mm_java_classes import Studio, Magellan
from pycromanager.core import Core
from pycromanager.zmq_bridge.wrappers import JavaObject, JavaClass, PullSocket, PushSocket
from pycromanager.acquisition.acq_eng_py.main.acq_notification import AcqNotification
from ndtiff import Dataset
from ._version import __version__, version_info
