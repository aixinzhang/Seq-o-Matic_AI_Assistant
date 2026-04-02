"""
Test the knowledge base by running sample queries.

Run after index_knowledge.py:
    python test_search.py

This shows you what chunks the agent would retrieve for each question,
WITHOUT calling the Claude API (no cost).
"""

import chromadb
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "vector_db")

def search(query, n_results=3):
    """Search the knowledge base and print results."""
    client = chromadb.PersistentClient(path=DB_PATH)
    collection = client.get_collection("software_knowledge")

    results = collection.query(
        query_texts=[query],
        n_results=n_results,
    )

    print(f"\n{'='*60}")
    print(f"QUERY: {query}")
    print(f"{'='*60}")

    for i in range(len(results["documents"][0])):
        doc = results["documents"][0][i]
        meta = results["metadatas"][0][i]
        distance = results["distances"][0][i] if results["distances"] else "?"

        print(f"\n--- Result {i+1} (distance: {distance:.3f}) ---")
        print(f"Source: {meta['source']} ({meta['type']})")
        print(f"Preview: {doc[:200]}...")
        print()


if __name__ == "__main__":
    # Test with questions that span different parts of the codebase
    test_queries = [
        "How does the cascaded selector addressing work?",
        "What happens when the user presses the Cancel button?",
        "How is the pump serial protocol structured?",
        "What config files do I need to set up for a new microscope?",
        "How does the phase correlation alignment algorithm work?",
        "What is the fluidics sequence state machine?",
    ]

    for q in test_queries:
        search(q)
