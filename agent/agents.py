"""
Specialist agents for the Seq-o-Matic AI assistant.

Each agent has:
- A system prompt (its identity and expertise)
- A search function (retrieves relevant knowledge from ChromaDB)
- A conversation history (remembers previous Q&A in the session)
- A run function (searches knowledge, sends to Claude, returns answer)

Usage:
    from agents import software_agent, hardware_agent, clear_history, save_last_qa

    answer = software_agent("How does the pump work?")
    answer = software_agent("What about the tubing?")  # remembers previous Q&A

    save_last_qa()     # save the last Q&A to knowledge base permanently
    clear_history()    # reset conversation memory
"""

import os
import json
from datetime import datetime
import anthropic
import chromadb

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

DB_PATH = os.path.join(os.path.dirname(__file__), "vector_db")

_api_client = None
_db_client = None

# Conversation history for each agent (persists within a session)
_software_history = []
_hardware_history = []


def _get_api():
    """Lazy-init Anthropic client (reads ANTHROPIC_API_KEY from env)."""
    global _api_client
    if _api_client is None:
        _api_client = anthropic.Anthropic()
    return _api_client


def _get_db():
    """Lazy-init ChromaDB client."""
    global _db_client
    if _db_client is None:
        _db_client = chromadb.PersistentClient(path=DB_PATH)
    return _db_client


def clear_history():
    """Clear conversation history for both agents. Call to start fresh."""
    global _software_history, _hardware_history
    _software_history = []
    _hardware_history = []
    print("  [Memory] Conversation history cleared")


# Track which agent answered last (for save_last_qa)
_last_agent = None


def save_last_qa():
    """Save the last Q&A pair permanently to the knowledge base.

    Extracts the original question (without the RAG context) and the
    answer, then stores them in ChromaDB so future searches can find them.
    Also saves to a JSON log file for backup.
    """
    global _last_agent

    # Find which agent has the most recent answer
    if _last_agent == "software" and len(_software_history) >= 2:
        history = _software_history
        collection_name = "software_knowledge"
    elif _last_agent == "hardware" and len(_hardware_history) >= 2:
        history = _hardware_history
        collection_name = "hardware_knowledge"
    else:
        print("  [Save] No Q&A to save")
        return

    # Extract the last Q&A pair
    last_user = history[-2]["content"]  # user message (includes RAG context)
    last_answer = history[-1]["content"]  # assistant answer

    # Extract just the question (after "User question:" marker)
    if "User question:" in last_user:
        question = last_user.split("User question:")[-1].strip()
    else:
        question = last_user.strip()

    # Build the document to index
    doc = f"Q: {question}\n\nA: {last_answer}"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    doc_id = f"saved_qa:{timestamp}"

    # Save to ChromaDB
    try:
        collection = _get_db().get_collection(collection_name)
        collection.add(
            documents=[doc],
            ids=[doc_id],
            metadatas=[{
                "source": "saved_qa",
                "type": "curated_qa",
                "question": question[:200],  # truncate for metadata
                "saved_at": timestamp,
            }],
        )
        print(f"  [Save] Indexed to {collection_name}: {question[:60]}...")
    except Exception as e:
        print(f"  [Save] Failed to index: {e}")

    # Also save to a JSON backup file
    saved_qa_dir = os.path.join(os.path.dirname(__file__), "saved_qa")
    os.makedirs(saved_qa_dir, exist_ok=True)
    backup_file = os.path.join(saved_qa_dir, "curated_qa.json")

    entry = {
        "timestamp": timestamp,
        "agent": _last_agent,
        "question": question,
        "answer": last_answer,
    }

    # Append to existing file
    existing = []
    if os.path.exists(backup_file):
        with open(backup_file, "r", encoding="utf-8") as f:
            existing = json.load(f)
    existing.append(entry)
    with open(backup_file, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    print(f"  [Save] Backed up to saved_qa/curated_qa.json")


# ---------------------------------------------------------------------------
# Knowledge search
# ---------------------------------------------------------------------------

def search_knowledge(collection_name: str, query: str, n_results: int = 5) -> str:
    """Search a ChromaDB collection and return formatted results."""
    collection = _get_db().get_collection(collection_name)
    results = collection.query(query_texts=[query], n_results=n_results)

    docs = results["documents"][0]
    metadatas = results["metadatas"][0]

    formatted = []
    for doc, meta in zip(docs, metadatas):
        source = meta.get("source", "unknown")
        formatted.append(f"[Source: {source}]\n{doc}")

    return "\n\n---\n\n".join(formatted)


# ---------------------------------------------------------------------------
# Software Agent
# ---------------------------------------------------------------------------

SOFTWARE_SYSTEM_PROMPT = """You are a software specialist for the Seq-o-Matic 2.5 codebase.

## Architecture (4 layers)
1. GUI (front_end/) -> Tkinter panels + automation_controller
2. System (system/) -> FluidicSystem facade + ImagingSystem facade
3. Device (device/) -> ABC interfaces: PumpDevice, SelectorDevice, HeaterDevice, RelayDevice
4. Driver (driver/) -> Ismatec serial protocol, KMtronic relay protocol

## Key patterns
- LogWindow singleton for all UI logging
- threading.Event for synchronization between fluidics and imaging
- SequenceState enum (IDLE/RUNNING/CANCELLED/FINISHED) for the fluidics state machine
- PROTOCOL_MAP in protocol_loader.py maps process types to JSON files
- All config in code/config_file/*.json
- Vendored pycromanager + ndtiff in supplementary/package/ (NOT pip installed)

## How to answer
- Reference specific file paths
- Explain data flow through the layers
- For bugs: trace the code path and identify root cause
- For new features: suggest which modules to modify and why
- If the retrieved code doesn't fully answer the question, say what you know
  and what the user should check manually
"""


def software_agent(question: str, n_results: int = 5) -> str:
    """Answer a software question using the codebase knowledge base.

    Remembers previous questions and answers within the session.
    """
    global _software_history, _last_agent
    _last_agent = "software"
    context = search_knowledge("software_knowledge", question, n_results)

    # Build the new user message with retrieved context
    user_message = f"""Here is relevant code and documentation retrieved from the Seq-o-Matic codebase:

{context}

---

User question: {question}"""

    # Add to conversation history
    _software_history.append({"role": "user", "content": user_message})

    response = _get_api().messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        system=SOFTWARE_SYSTEM_PROMPT,
        messages=_software_history,  # send full history
    )

    answer = response.content[0].text

    # Save assistant's answer to history
    _software_history.append({"role": "assistant", "content": answer})

    # Keep history manageable (last 20 messages = 10 Q&A pairs)
    if len(_software_history) > 20:
        _software_history = _software_history[-20:]

    return answer


# ---------------------------------------------------------------------------
# Hardware Agent
# ---------------------------------------------------------------------------

HARDWARE_SYSTEM_PROMPT = """You are a hardware specialist for the Seq-o-Matic laboratory automation system.

## Equipment you know about
- Ismatec IPC-N peristaltic pump (serial RS-232, 9600 baud, tubing: 0.51mm ID)
- Elveflow MUX multiplexer fluid selectors (2 units cascaded, 16 reagent ports)
- Nikon Ti2-E inverted microscope with Micro-Manager 2.0
- Piezo z-stage for z-stack acquisition
- NI DAQ (Dev2) controlling Bioptech heating stages (analog out for voltage, digital out per stage, analog in for temp)
- KMtronic 4-channel USB relay controller

## How to answer
- For broken parts: give exact replacement part numbers and vendors
- For troubleshooting: step-by-step diagnostic procedures
- Reference manual sections when possible
- For wiring/connections: specify COM ports, DAQ channels, pin assignments
- If you're unsure, say so -- wrong hardware advice can damage equipment
"""


def hardware_agent(question: str, n_results: int = 5) -> str:
    """Answer a hardware question using the hardware knowledge base.

    Remembers previous questions and answers within the session.
    """
    global _hardware_history, _last_agent
    _last_agent = "hardware"

    # Try to search hardware knowledge base
    try:
        context = search_knowledge("hardware_knowledge", question, n_results)
    except Exception:
        context = "(No hardware knowledge base indexed yet. Answering from general knowledge.)"

    user_message = f"""Relevant hardware documentation:

{context}

---

User question: {question}"""

    _hardware_history.append({"role": "user", "content": user_message})

    response = _get_api().messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        system=HARDWARE_SYSTEM_PROMPT,
        messages=_hardware_history,  # send full history
    )

    answer = response.content[0].text
    _hardware_history.append({"role": "assistant", "content": answer})

    # Keep history manageable (last 20 messages = 10 Q&A pairs)
    if len(_hardware_history) > 20:
        _hardware_history = _hardware_history[-20:]

    return answer
