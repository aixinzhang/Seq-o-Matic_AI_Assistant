"""
Seq-o-Matic AI Assistant -- Orchestrator.

Routes user questions to the appropriate specialist agent (hardware, software, or both).

Usage:
    # Set your API key first:
    # Windows: set ANTHROPIC_API_KEY=sk-ant-...
    # Linux:   export ANTHROPIC_API_KEY=sk-ant-...

    python orchestrator.py
"""

import anthropic
from agents import software_agent, hardware_agent, clear_history, save_last_qa

# ---------------------------------------------------------------------------
# Question classifier
# ---------------------------------------------------------------------------

CLASSIFIER_PROMPT = """Classify this question about a laboratory automation system into ONE category:

- "hardware" = Physical equipment: broken parts, replacements, wiring, COM ports,
  manual procedures, maintenance, purchasing, tubing, optics, DAQ channels
- "software" = Code questions: bugs, features, config files, error messages,
  how the code works, how to modify it, Python, JSON config
- "both" = Questions that span hardware AND software: e.g. "pump not responding"
  could be a cable issue OR a code bug

Respond with ONLY one word: hardware, software, or both"""


def classify(question: str) -> str:
    """Classify a question as hardware, software, or both.

    Uses Claude Haiku for speed and cost (classification is simple).
    """
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=10,
        system=CLASSIFIER_PROMPT,
        messages=[{"role": "user", "content": question}],
    )
    category = response.content[0].text.strip().lower()

    # Normalize to valid categories
    if category not in ("hardware", "software", "both"):
        category = "software"  # safe default
    return category


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

MERGE_PROMPT = """You are combining answers from a hardware specialist and a software specialist
about a laboratory automation system. Synthesize them into one clear, unified answer.
If they contradict, note both perspectives. Prioritize actionable advice."""


def ask(question: str) -> str:
    """Main entry point: classify, route to specialists, return answer.

    Args:
        question: Any question about the Seq-o-Matic system.

    Returns:
        The combined answer from the appropriate specialist(s).
    """
    category = classify(question)
    print(f"  [Orchestrator] Category: {category}")

    if category == "hardware":
        return hardware_agent(question)

    elif category == "software":
        return software_agent(question)

    elif category == "both":
        print("  [Orchestrator] Querying both specialists...")
        hw_answer = hardware_agent(question)
        sw_answer = software_agent(question)

        # Merge the two answers
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
    print("  Commands: 'quit' to exit, 'clear' to reset memory,")
    print("            'save' to save last Q&A to knowledge base")
    print("=" * 60)

    while True:
        print()
        question = input("You: ").strip()
        if not question:
            continue
        if question.lower() in ("clear", "reset"):
            clear_history()
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
