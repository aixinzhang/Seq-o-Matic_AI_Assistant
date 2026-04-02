"""
Knowledge Base Indexer for Seq-o-Matic AI Agent.

This script reads your project files, splits them into searchable chunks,
and stores them in a local ChromaDB vector database.

Run this once to build the database, and re-run whenever code changes:
    cd agent/
    pip install -r requirements.txt
    python index_knowledge.py

What this does step by step:
    1. Reads each file from your project
    2. Splits it into overlapping chunks (so no context is lost at boundaries)
    3. Stores each chunk in ChromaDB with its source file path
    4. ChromaDB automatically computes embedding vectors for searching

After running, the ./vector_db/ folder contains your searchable knowledge base.
"""

import os
import json
import chromadb

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Where the Seq-o-Matic code lives (adjust if needed)
PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
CODE_DIR = os.path.join(PROJECT_ROOT, "code")

# Where to save the vector database
DB_PATH = os.path.join(os.path.dirname(__file__), "vector_db")

# Chunk sizes (in lines)
# Docs get smaller chunks for precise retrieval
# Code gets larger chunks to keep functions intact
DOC_CHUNK_LINES = 30
DOC_OVERLAP_LINES = 5
CODE_CHUNK_LINES = 50
CODE_OVERLAP_LINES = 10


# ---------------------------------------------------------------------------
# Files to index
# ---------------------------------------------------------------------------

# High-value documentation files (smaller chunks for precise answers)
DOC_FILES = [
    os.path.join(PROJECT_ROOT, "README.md"),
    os.path.join(PROJECT_ROOT, "docs", "architecture.md"),
    os.path.join(PROJECT_ROOT, "docs", "config_files.md"),
    os.path.join(PROJECT_ROOT, "docs", "reagent_sequences.md"),
]

# Source code files (larger chunks to keep functions together)
CODE_FILES = [
    # Core infrastructure
    "constants.py",
    "types_seq.py",
    "logging_config.py",
    "mainwindow.py",

    # Device interfaces and implementations
    "device/base.py",
    "device/Pump.py",
    "device/Selector.py",
    "device/Heatingstage.py",
    "device/Relay.py",

    # Drivers
    "driver/ismatec_ipc.py",
    "driver/kmtronic_relay.py",

    # System orchestration - fluidics
    "system/fluidics_exchange_system.py",
    "system/fluidics/protocol_loader.py",
    "system/fluidics/sequence_runner.py",

    # System orchestration - imaging
    "system/imaging/imaging_system.py",
    "system/imaging/focus.py",
    "system/imaging/alignment.py",
    "system/imaging/tiling.py",
    "system/imaging/max_projection.py",
    "system/imaging/position_utils.py",

    # Front-end
    "front_end/logwindow.py",
    "front_end/Widgets.py",
    "front_end/automation_controller.py",
    "front_end/experiment_profile.py",
    "front_end/recipe_builder.py",
    "front_end/tissue_scanner.py",

    # Front-end panels
    "front_end/panels/workspace_panel.py",
    "front_end/panels/experiment_config_panel.py",
    "front_end/panels/device_panel.py",
    "front_end/panels/fluidics_control_panel.py",
    "front_end/panels/imaging_control_panel.py",
    "front_end/panels/status_panel.py",
]

# Config files (index as-is, no chunking -- they're small)
CONFIG_FILES = [
    "config_file/IsmatecPumpDevice_pump.json",
    "config_file/ElveflowMuxDevice_selector.json",
    "config_file/Heat_stage.json",
    "config_file/KMtronic_relay.json",
    "config_file/Fluidics_Reagent_Components.json",
    "config_file/scope.json",
]

# Example protocol file (so the agent understands the format)
PROTOCOL_FILES = [
    "reagent_sequence_file/Fluidics_sequence_bcseq01.json",
    "reagent_sequence_file/Fluidics_sequence_HYB.json",
    "reagent_sequence_file/Fluidics_sequence_fill_all.json",
]


# ---------------------------------------------------------------------------
# Chunking functions
# ---------------------------------------------------------------------------

def chunk_by_lines(text, chunk_lines, overlap_lines):
    """Split text into overlapping chunks by line count.

    Args:
        text: Full file content as string.
        chunk_lines: Number of lines per chunk.
        overlap_lines: Number of lines to overlap between chunks.

    Returns:
        List of chunk strings.

    Example with chunk_lines=4, overlap_lines=1:
        Line 1     ─┐
        Line 2      │ Chunk 1
        Line 3      │
        Line 4     ─┘
        Line 4     ─┐  ← overlap
        Line 5      │ Chunk 2
        Line 6      │
        Line 7     ─┘
    """
    lines = text.split("\n")
    chunks = []
    step = chunk_lines - overlap_lines

    for i in range(0, len(lines), step):
        chunk = "\n".join(lines[i:i + chunk_lines])
        if chunk.strip():  # skip empty chunks
            chunks.append(chunk)

    return chunks


def chunk_by_functions(text):
    """Split Python code by function/class definitions for more natural boundaries.

    Falls back to line-based chunking if the file has no clear structure.

    Returns:
        List of chunk strings.
    """
    lines = text.split("\n")
    chunks = []
    current_chunk = []

    for line in lines:
        # Start a new chunk at class/function definitions (but keep some context)
        if (line.startswith("class ") or line.startswith("def ") or
                line.startswith("    def ")) and len(current_chunk) > 10:
            chunks.append("\n".join(current_chunk))
            # Keep last 3 lines as overlap context
            current_chunk = current_chunk[-3:]

        current_chunk.append(line)

    # Don't forget the last chunk
    if current_chunk:
        chunks.append("\n".join(current_chunk))

    # If we only got 1 chunk (no functions found), fall back to line-based
    if len(chunks) <= 1:
        return chunk_by_lines(text, CODE_CHUNK_LINES, CODE_OVERLAP_LINES)

    return chunks


# ---------------------------------------------------------------------------
# Main indexing logic
# ---------------------------------------------------------------------------

def index_all():
    """Read all project files, chunk them, and store in ChromaDB."""

    # Create (or open) the database
    client = chromadb.PersistentClient(path=DB_PATH)

    # Delete old collection if it exists (clean re-index)
    try:
        client.delete_collection("software_knowledge")
        print("Deleted old collection")
    except Exception:
        pass

    collection = client.create_collection(
        name="software_knowledge",
        metadata={"description": "Seq-o-Matic codebase and documentation"},
    )

    total_chunks = 0

    # --- Index documentation (small chunks for precision) ---
    print("\n=== Indexing documentation ===")
    for filepath in DOC_FILES:
        if not os.path.exists(filepath):
            print(f"  SKIP (not found): {filepath}")
            continue
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
        chunks = chunk_by_lines(text, DOC_CHUNK_LINES, DOC_OVERLAP_LINES)
        rel_path = os.path.relpath(filepath, PROJECT_ROOT)
        for i, chunk in enumerate(chunks):
            collection.add(
                documents=[chunk],
                ids=[f"doc:{rel_path}:chunk{i}"],
                metadatas=[{
                    "source": rel_path,
                    "type": "documentation",
                    "chunk_index": i,
                }],
            )
        total_chunks += len(chunks)
        print(f"  {rel_path}: {len(chunks)} chunks")

    # --- Index source code (function-based chunks) ---
    print("\n=== Indexing source code ===")
    for rel_file in CODE_FILES:
        filepath = os.path.join(CODE_DIR, rel_file)
        if not os.path.exists(filepath):
            print(f"  SKIP (not found): {rel_file}")
            continue
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
        chunks = chunk_by_functions(text)
        for i, chunk in enumerate(chunks):
            collection.add(
                documents=[chunk],
                ids=[f"code:{rel_file}:chunk{i}"],
                metadatas=[{
                    "source": f"code/{rel_file}",
                    "type": "source_code",
                    "chunk_index": i,
                }],
            )
        total_chunks += len(chunks)
        print(f"  {rel_file}: {len(chunks)} chunks")

    # --- Index config files (whole file, no chunking) ---
    print("\n=== Indexing config files ===")
    for rel_file in CONFIG_FILES:
        filepath = os.path.join(CODE_DIR, rel_file)
        if not os.path.exists(filepath):
            print(f"  SKIP (not found): {rel_file}")
            continue
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
        collection.add(
            documents=[f"Config file: {rel_file}\n\n{text}"],
            ids=[f"config:{rel_file}"],
            metadatas=[{
                "source": f"code/{rel_file}",
                "type": "config",
            }],
        )
        total_chunks += 1
        print(f"  {rel_file}: 1 chunk (whole file)")

    # --- Index example protocol files (whole file) ---
    print("\n=== Indexing protocol examples ===")
    for rel_file in PROTOCOL_FILES:
        filepath = os.path.join(CODE_DIR, rel_file)
        if not os.path.exists(filepath):
            print(f"  SKIP (not found): {rel_file}")
            continue
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
        collection.add(
            documents=[f"Example protocol file: {rel_file}\n\n{text}"],
            ids=[f"protocol:{rel_file}"],
            metadatas=[{
                "source": f"code/{rel_file}",
                "type": "protocol_example",
            }],
        )
        total_chunks += 1
        print(f"  {rel_file}: 1 chunk (whole file)")

    print(f"\n{'='*50}")
    print(f"DONE! Indexed {total_chunks} total chunks")
    print(f"Database saved to: {os.path.abspath(DB_PATH)}")
    print(f"\nTo test, run: python test_search.py")


if __name__ == "__main__":
    index_all()
