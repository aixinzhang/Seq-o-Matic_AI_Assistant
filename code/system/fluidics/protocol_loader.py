"""
Protocol loader for fluidics sequences.

Replaces the 130-line if/elif chain in FluidicSystem.find_protocol()
with a clean mapping-based approach.
"""

import json
import os
import shutil
from datetime import datetime
from typing import Callable, Optional

from pytz import timezone

from front_end.logwindow import add_fluidics_reagent
from types_seq import ProtocolSequence


def get_time() -> str:
    """Return the current US/Pacific time as a formatted string."""
    time_now = timezone('US/Pacific')
    return str(datetime.now(time_now))[0:19] + "\n"


# Maps process type keywords to their JSON filename.
# Order matters: more specific patterns (with "rehyb") must be checked first.
PROTOCOL_MAP = [
    # (condition_func, filename)
    (lambda t: "geneseq" in t and "01" in t, "Fluidics_sequence_geneseq01.json"),
    (lambda t: "bcseq" in t and "01" in t, "Fluidics_sequence_bcseq01.json"),
    (lambda t: "geneseq" in t and "01" not in t, "Fluidics_sequence_geneseq02+.json"),
    (lambda t: "bcseq" in t and "01" not in t, "Fluidics_sequence_bcseq02+.json"),
    (lambda t: "add_gene_primer" in t and "rehyb" in t, "Fluidics_sequence_add_gene_primer_rehyb.json"),
    (lambda t: "add_bc_primer" in t and "rehyb" in t, "Fluidics_sequence_add_bc_primer_rehyb.json"),
    (lambda t: "HYB" in t and "rehyb" in t, "Fluidics_sequence_HYB_rehyb.json"),
    (lambda t: "add_gene_primer" in t and "rehyb" not in t, "Fluidics_sequence_add_gene_primer.json"),
    (lambda t: "add_bc_primer" in t and "rehyb" not in t, "Fluidics_sequence_add_bc_primer.json"),
    (lambda t: "HYB" in t and "rehyb" not in t, "Fluidics_sequence_HYB.json"),
    (lambda t: "strip" in t, "Fluidics_sequence_strip.json"),
]


def load_protocol(protocol_type: str, sequence_dir: str, backup_dir: str, write_log: Optional[Callable[[str], None]] = None) -> ProtocolSequence:
    """Load a fluidics protocol JSON file based on process type name.

    Maps process type strings (e.g., 'geneseq01', 'bcseq02+', 'HYB',
    'strip', 'add_bc_primer') to the corresponding JSON protocol file.
    Copies the protocol to the experiment directory for record-keeping.

    Args:
        protocol_type: Process type string identifying which protocol to load.
        sequence_dir: Directory containing reagent_sequence_file/ JSON files.
        backup_dir: Experiment directory to copy the protocol file into.
        write_log: Optional callable(str) to write to log file.

    Returns:
        List of step dicts parsed from the protocol JSON file.

    Raises:
        FileNotFoundError: If no matching protocol is found.
    """
    # Handle user-defined protocols
    if "user_defined" in protocol_type:
        file_name = protocol_type + ".json"
        return _load_and_copy(file_name, sequence_dir, backup_dir, write_log)

    # Match against known protocol patterns
    for condition, file_name in PROTOCOL_MAP:
        if condition(protocol_type):
            return _load_and_copy(file_name, sequence_dir, backup_dir, write_log)

    raise FileNotFoundError(f"No protocol found for type: {protocol_type}")


def _load_and_copy(file_name: str, sequence_dir: str, backup_dir: str, write_log: Optional[Callable[[str], None]] = None) -> ProtocolSequence:
    """Load a protocol JSON and copy it to the experiment directory.

    Args:
        file_name: JSON filename (e.g., 'Fluidics_sequence_geneseq01.json').
        sequence_dir: Base directory for reagent_sequence_file/.
        backup_dir: Experiment directory for backup copy.
        write_log: Optional callable(str) for logging.

    Returns:
        List of step dicts from the protocol.
    """
    source_path = os.path.join(sequence_dir, file_name)
    with open(source_path, 'r') as r:
        protocol = json.load(r)

    txt = get_time() + f"load {file_name} protocol!\n"
    print(txt)
    add_fluidics_reagent(txt)
    if write_log:
        write_log(txt)

    dest_path = os.path.join(backup_dir, file_name)
    if not os.path.exists(dest_path):
        shutil.copyfile(source_path, dest_path)

    return protocol
