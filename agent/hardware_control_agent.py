"""
Hardware Control Agent -- Natural language control of lab equipment.

Uses Claude's tool_use feature to translate natural language commands
into hardware function calls. Always asks for confirmation before executing.

Usage:
    python hardware_control_agent.py

Examples:
    "Pump 2ml of PBST"
    "Select incorporation buffer"
    "Heat for 3 minutes"
    "Run the bcseq01 protocol"
    "Stop the pump"
    "Is the pump running?"
"""

import anthropic
from hardware_tools import TOOLS, execute_tool, describe_action

SYSTEM_PROMPT = """You are a lab equipment controller for the Seq-o-Matic system.

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


def run_control_agent():
    """Interactive loop for natural language hardware control."""
    client = anthropic.Anthropic()
    messages = []

    print("=" * 60)
    print("  Seq-o-Matic Hardware Controller")
    print("  Control lab equipment with natural language")
    print("  Commands: 'quit' to exit")
    print("=" * 60)

    while True:
        print()
        user_input = input("You: ").strip()
        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break

        messages.append({"role": "user", "content": user_input})

        # Send to Claude with tools
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        # Process response -- may contain text and/or tool calls
        assistant_text = ""
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                assistant_text += block.text
            elif block.type == "tool_use":
                tool_calls.append(block)

        # Show any text response
        if assistant_text:
            print(f"\nAssistant: {assistant_text}")

        # If Claude wants to use tools, ask for confirmation
        if tool_calls:
            messages.append({"role": "assistant", "content": response.content})

            print(f"\n  Planned actions ({len(tool_calls)}):")
            for i, tc in enumerate(tool_calls):
                desc = describe_action(tc.name, tc.input)
                print(f"    {i+1}. {desc}")

            confirm = input("\n  Execute? (yes/no): ").strip().lower()

            if confirm in ("yes", "y"):
                # Execute each tool and collect results
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

                # Send results back to Claude for final response
                messages.append({"role": "user", "content": tool_results})

                final_response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=500,
                    system=SYSTEM_PROMPT,
                    tools=TOOLS,
                    messages=messages,
                )

                final_text = ""
                for block in final_response.content:
                    if block.type == "text":
                        final_text += block.text

                if final_text:
                    print(f"\nAssistant: {final_text}")
                messages.append({"role": "assistant", "content": final_response.content})

            else:
                print("  Cancelled.")
                # Tell Claude the action was cancelled
                tool_results = []
                for tc in tool_calls:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tc.id,
                        "content": "CANCELLED by user",
                    })
                messages.append({"role": "user", "content": tool_results})
                messages.append({"role": "assistant", "content": "Understood, action cancelled."})

        else:
            # No tool calls, just text response
            messages.append({"role": "assistant", "content": response.content})

        # Keep message history manageable
        if len(messages) > 30:
            messages = messages[-30:]


if __name__ == "__main__":
    run_control_agent()
