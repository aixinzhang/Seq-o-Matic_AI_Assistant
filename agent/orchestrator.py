"""
Seq-o-Matic AI Assistant -- Unified Orchestrator.

Routes user questions to the appropriate handler:
- Q&A about software -> Software Agent (RAG search + Claude)
- Q&A about hardware -> Hardware Agent (RAG search + Claude)
- Hardware control commands -> Hardware Control (Claude tool_use + confirmation)

Usage:
    # Set your API key first:
    # PowerShell: $env:ANTHROPIC_API_KEY = "sk-ant-..."
    # cmd: set ANTHROPIC_API_KEY=sk-ant-...

    python orchestrator.py
"""

import anthropic
from agents import software_agent, hardware_agent, clear_history, save_last_qa
from hardware_tools import TOOLS, execute_tool, describe_action

# ---------------------------------------------------------------------------
# Question classifier
# ---------------------------------------------------------------------------

CLASSIFIER_PROMPT = """Classify this input about a laboratory automation system into ONE category:

- "control" = Direct commands to operate equipment: pump, select reagent, heat,
  start/stop, connect/disconnect, run protocol. Any request that requires
  physically doing something with the hardware NOW.
  Examples: "pump 2ml of PBST", "connect the pump", "heat for 3 minutes",
  "run bcseq01", "stop the pump", "select DAPI"
- "hardware" = Questions ABOUT equipment: broken parts, replacements, wiring,
  COM ports, manual procedures, maintenance, purchasing, troubleshooting
  Examples: "where do I buy pump tubing?", "how is the DAQ wired?"
- "software" = Questions about code: bugs, features, config files, error messages,
  how the code works, how to modify it
  Examples: "how does imregcorr work?", "what does FluidicSystem do?"
- "both" = Questions that span hardware AND software
  Examples: "pump not responding" (could be cable or code)

Respond with ONLY one word: control, hardware, software, or both"""


def classify(question: str) -> str:
    """Classify a question as control, hardware, software, or both."""
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=10,
        system=CLASSIFIER_PROMPT,
        messages=[{"role": "user", "content": question}],
    )
    category = response.content[0].text.strip().lower()

    if category not in ("control", "hardware", "software", "both"):
        category = "software"
    return category


# ---------------------------------------------------------------------------
# Hardware Control (tool_use)
# ---------------------------------------------------------------------------

CONTROL_SYSTEM_PROMPT = """You are a lab equipment controller for the Seq-o-Matic system.

You can control:
- Ismatec peristaltic pump (connect, pump volume, stop, check status)
- Elveflow fluid selectors (connect, select reagent)
- Bioptech heating stages (connect, heat for duration)
- Full protocol sequences (bcseq01, geneseq01, HYB, strip, etc.)

IMPORTANT RULES:
1. Before pumping, ensure the pump and selector are connected. If not sure, ask.
2. Before heating, ensure the heater is connected.
3. Always use pump_reagent when the user specifies both a reagent and volume.
4. Default pump rate is 1.5 mL/min unless the user specifies otherwise.
5. When the user says "3 minutes", convert to 180 seconds for heating.
6. If a command is ambiguous, ask for clarification rather than guessing.

Available reagents: incorporation buffer, PBST, Iodoacetamide Blocker, IRM, USM,
CRM, FISH WASH, STRIP, hyb oligos mix, DAPI, bc primer mix, gene primer mix,
hyb oligos mix 2, END, hyb oligos mix 3, hyb oligos mix 4
"""

# Persistent message history for the control agent
_control_history = []


def control_agent(question: str, confirm_fn=None) -> str:
    """Handle a hardware control command using Claude tool_use.

    Args:
        question: Natural language command (e.g., "pump 2ml of PBST")
        confirm_fn: Function that takes a description string and returns True/False.
                    If None, uses terminal input.

    Returns:
        Result string describing what happened.
    """
    global _control_history
    client = anthropic.Anthropic()

    _control_history.append({"role": "user", "content": question})

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        system=CONTROL_SYSTEM_PROMPT,
        tools=TOOLS,
        messages=_control_history,
    )

    # Collect text and tool calls
    assistant_text = ""
    tool_calls = []

    for block in response.content:
        if block.type == "text":
            assistant_text += block.text
        elif block.type == "tool_use":
            tool_calls.append(block)

    # If no tool calls, just return text (Claude is asking for clarification)
    if not tool_calls:
        _control_history.append({"role": "assistant", "content": response.content})
        return assistant_text

    # Show planned actions and ask for confirmation
    _control_history.append({"role": "assistant", "content": response.content})

    actions = []
    for tc in tool_calls:
        actions.append(describe_action(tc.name, tc.input))

    action_text = "\n".join(f"  {i+1}. {a}" for i, a in enumerate(actions))

    if confirm_fn:
        confirmed = confirm_fn(action_text)
    else:
        print(f"\n  Planned actions ({len(tool_calls)}):")
        print(action_text)
        confirm = input("\n  Execute? (yes/no): ").strip().lower()
        confirmed = confirm in ("yes", "y")

    if confirmed:
        tool_results = []
        for tc in tool_calls:
            print(f"  Executing: {tc.name}...")
            result = execute_tool(tc.name, tc.input)
            print(f"  Result: {result}")
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tc.id,
                "content": result,
            })

        _control_history.append({"role": "user", "content": tool_results})

        # Get Claude's final summary
        final = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            system=CONTROL_SYSTEM_PROMPT,
            tools=TOOLS,
            messages=_control_history,
        )

        final_text = ""
        for block in final.content:
            if block.type == "text":
                final_text += block.text
        _control_history.append({"role": "assistant", "content": final.content})

        return final_text if final_text else "Done."

    else:
        tool_results = []
        for tc in tool_calls:
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tc.id,
                "content": "CANCELLED by user",
            })
        _control_history.append({"role": "user", "content": tool_results})
        _control_history.append({"role": "assistant", "content": "Understood, action cancelled."})
        return "Cancelled."

    # Keep history manageable
    if len(_control_history) > 30:
        _control_history = _control_history[-30:]


# ---------------------------------------------------------------------------
# Unified ask
# ---------------------------------------------------------------------------

MERGE_PROMPT = """You are combining answers from a hardware specialist and a software specialist
about a laboratory automation system. Synthesize them into one clear, unified answer.
If they contradict, note both perspectives. Prioritize actionable advice."""


def ask(question: str) -> str:
    """Main entry point: classify, route to the right handler, return answer."""
    category = classify(question)
    print(f"  [Orchestrator] Category: {category}")

    if category == "control":
        return control_agent(question)

    elif category == "hardware":
        return hardware_agent(question)

    elif category == "software":
        return software_agent(question)

    elif category == "both":
        print("  [Orchestrator] Querying both specialists...")
        hw_answer = hardware_agent(question)
        sw_answer = software_agent(question)

        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system=MERGE_PROMPT,
            messages=[{
                "role": "user",
                "content": f"""Question: {question}

Hardware specialist says:
{hw_answer}

Software specialist says:
{sw_answer}

Provide a unified answer covering both perspectives."""
            }],
        )
        return response.content[0].text

    return software_agent(question)


# ---------------------------------------------------------------------------
# Interactive CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("  Seq-o-Matic AI Assistant")
    print("  Ask questions OR control hardware with natural language")
    print("  Commands: 'quit', 'clear', 'save'")
    print("=" * 60)

    while True:
        print()
        question = input("You: ").strip()
        if not question:
            continue
        if question.lower() in ("clear", "reset"):
            clear_history()
            _control_history = []
            continue
        if question.lower() == "save":
            save_last_qa()
            continue
        if question.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break

        try:
            answer = ask(question)
            print(f"\nAssistant:\n{answer}")
        except Exception as e:
            print(f"\nError: {e}")
            print("Make sure ANTHROPIC_API_KEY is set and vector_db/ exists (run index_knowledge.py first)")
