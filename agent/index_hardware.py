"""
Hardware Knowledge Base Indexer for Seq-o-Matic AI Agent.

Indexes hardware manuals (PDFs and text), parts catalogs, and
troubleshooting guides into a ChromaDB collection.

Run this after adding your manual PDFs:
    python index_hardware.py

PDF support:
    pip install pymupdf    (for reading PDFs)

If you don't have pymupdf, the script will skip PDFs and only index
text/markdown/json files.
"""

import os
import json
import base64
import chromadb

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

HW_DIR = os.path.join(os.path.dirname(__file__), "hardware_knowledge")
DB_PATH = os.path.join(os.path.dirname(__file__), "vector_db")

# PDF pages often have 40-60 lines, so chunk at ~40 lines
MANUAL_CHUNK_LINES = 40
MANUAL_OVERLAP_LINES = 8
TEXT_CHUNK_LINES = 30
TEXT_OVERLAP_LINES = 5


# ---------------------------------------------------------------------------
# PDF reading (optional dependency)
# ---------------------------------------------------------------------------

def read_pdf(filepath):
    """Read a PDF file and return text content.

    Requires pymupdf: pip install pymupdf
    Returns None if pymupdf is not installed.
    """
    try:
        import fitz  # pymupdf
    except ImportError:
        print(f"  WARNING: pymupdf not installed, skipping PDF: {filepath}")
        print(f"           Run: pip install pymupdf")
        return None

    doc = fitz.open(filepath)
    pages = []
    for page_num, page in enumerate(doc):
        text = page.get_text()
        if text.strip():
            pages.append(f"[Page {page_num + 1}]\n{text}")
    doc.close()
    return "\n\n".join(pages)


# ---------------------------------------------------------------------------
# Image reading (uses Claude API to describe diagrams)
# ---------------------------------------------------------------------------

def describe_image(filepath):
    """Send an image to Claude and get a detailed text description.

    Supports: .tif, .tiff, .png, .jpg, .jpeg
    Requires: ANTHROPIC_API_KEY environment variable set.
    Returns None if API key is not set.

    How it works:
        Image file -> base64 encode -> send to Claude -> get text description
        The text description is what gets stored in ChromaDB (not the image).
    """
    try:
        import anthropic
    except ImportError:
        print(f"  WARNING: anthropic not installed, skipping image: {filepath}")
        return None

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(f"  WARNING: ANTHROPIC_API_KEY not set, skipping image: {filepath}")
        print(f"           Set it with: set ANTHROPIC_API_KEY=sk-ant-...")
        return None

    # Convert TIF to PNG if needed (Claude API accepts PNG/JPEG/GIF/WEBP)
    ext = os.path.splitext(filepath)[1].lower()
    if ext in (".tif", ".tiff"):
        try:
            from PIL import Image
            img = Image.open(filepath)
            # Convert to RGB if needed (TIFFs can be CMYK, etc.)
            if img.mode not in ("RGB", "RGBA", "L"):
                img = img.convert("RGB")
            # Save as temporary PNG in memory
            import io
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            image_data = base64.standard_b64encode(buffer.getvalue()).decode("utf-8")
            media_type = "image/png"
        except ImportError:
            print(f"  WARNING: Pillow not installed, skipping TIF: {filepath}")
            print(f"           Run: pip install Pillow")
            return None
    elif ext in (".png",):
        with open(filepath, "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")
        media_type = "image/png"
    elif ext in (".jpg", ".jpeg"):
        with open(filepath, "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")
        media_type = "image/jpeg"
    else:
        print(f"  SKIP (unsupported image format): {filepath}")
        return None

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_data,
                    },
                },
                {
                    "type": "text",
                    "text": (
                        "This is a system diagram for a laboratory automation system called Seq-o-Matic. "
                        "It controls a microscope, peristaltic pump, fluid selectors, and heating stages "
                        "for tissue imaging and molecular sequencing. "
                        "Please describe this diagram in detail, including: "
                        "1. All components shown and their connections "
                        "2. Flow direction of fluids "
                        "3. Any labels, part numbers, or annotations "
                        "4. The overall system layout and purpose "
                        "Be thorough -- this description will be the only searchable record of this diagram."
                    ),
                },
            ],
        }],
    )
    return response.content[0].text


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_by_lines(text, chunk_lines, overlap_lines):
    """Split text into overlapping chunks by line count."""
    lines = text.split("\n")
    chunks = []
    step = chunk_lines - overlap_lines
    for i in range(0, len(lines), step):
        chunk = "\n".join(lines[i:i + chunk_lines])
        if chunk.strip():
            chunks.append(chunk)
    return chunks


# ---------------------------------------------------------------------------
# Main indexing
# ---------------------------------------------------------------------------

def index_hardware():
    """Index all hardware knowledge files into ChromaDB."""

    client = chromadb.PersistentClient(path=DB_PATH)

    # Delete old collection if exists
    try:
        client.delete_collection("hardware_knowledge")
        print("Deleted old hardware collection")
    except Exception:
        pass

    collection = client.create_collection(
        name="hardware_knowledge",
        metadata={"description": "Seq-o-Matic hardware manuals, parts, troubleshooting"},
    )

    total_chunks = 0

    # --- Index manuals (PDFs and text files) ---
    manuals_dir = os.path.join(HW_DIR, "manuals")
    if os.path.exists(manuals_dir):
        print("\n=== Indexing manuals ===")
        for filename in os.listdir(manuals_dir):
            filepath = os.path.join(manuals_dir, filename)
            if not os.path.isfile(filepath):
                continue

            # Read content based on file type
            if filename.endswith(".pdf"):
                text = read_pdf(filepath)
                if text is None:
                    continue
            elif filename.endswith((".tif", ".tiff", ".png", ".jpg", ".jpeg")):
                # Images: send to Claude API for description, then index the text
                print(f"  {filename}: describing image via Claude API...")
                text = describe_image(filepath)
                if text is None:
                    continue
                # Store as single chunk (description is already concise)
                collection.add(
                    documents=[f"System diagram: {filename}\n\n{text}"],
                    ids=[f"diagram:{filename}"],
                    metadatas=[{
                        "source": filename,
                        "type": "diagram",
                    }],
                )
                total_chunks += 1
                print(f"  {filename}: 1 chunk (image description)")
                continue
            elif filename.endswith((".md", ".txt", ".rst")):
                with open(filepath, "r", encoding="utf-8") as f:
                    text = f.read()
            else:
                print(f"  SKIP (unsupported format): {filename}")
                continue

            chunks = chunk_by_lines(text, MANUAL_CHUNK_LINES, MANUAL_OVERLAP_LINES)
            for i, chunk in enumerate(chunks):
                collection.add(
                    documents=[chunk],
                    ids=[f"manual:{filename}:chunk{i}"],
                    metadatas=[{
                        "source": filename,
                        "type": "manual",
                        "chunk_index": i,
                    }],
                )
            total_chunks += len(chunks)
            print(f"  {filename}: {len(chunks)} chunks")

    # --- Index parts catalog ---
    parts_dir = os.path.join(HW_DIR, "parts")
    if os.path.exists(parts_dir):
        print("\n=== Indexing parts catalog ===")
        for filename in os.listdir(parts_dir):
            filepath = os.path.join(parts_dir, filename)
            if filename.endswith(".json"):
                with open(filepath, "r", encoding="utf-8") as f:
                    parts = json.load(f)
                for i, part in enumerate(parts):
                    doc = json.dumps(part, indent=2)
                    collection.add(
                        documents=[f"Replacement part:\n{doc}"],
                        ids=[f"part:{filename}:{i}"],
                        metadatas=[{
                            "source": filename,
                            "type": "parts",
                            "part_name": part.get("part", "unknown"),
                        }],
                    )
                total_chunks += len(parts)
                print(f"  {filename}: {len(parts)} parts")

    # --- Index troubleshooting guides ---
    trouble_dir = os.path.join(HW_DIR, "troubleshooting")
    if os.path.exists(trouble_dir):
        print("\n=== Indexing troubleshooting guides ===")
        for filename in os.listdir(trouble_dir):
            filepath = os.path.join(trouble_dir, filename)
            if filename.endswith((".md", ".txt")):
                with open(filepath, "r", encoding="utf-8") as f:
                    text = f.read()
                chunks = chunk_by_lines(text, TEXT_CHUNK_LINES, TEXT_OVERLAP_LINES)
                for i, chunk in enumerate(chunks):
                    collection.add(
                        documents=[chunk],
                        ids=[f"troubleshoot:{filename}:chunk{i}"],
                        metadatas=[{
                            "source": filename,
                            "type": "troubleshooting",
                            "chunk_index": i,
                        }],
                    )
                total_chunks += len(chunks)
                print(f"  {filename}: {len(chunks)} chunks")

    print(f"\n{'='*50}")
    print(f"DONE! Indexed {total_chunks} total hardware chunks")
    print(f"Database saved to: {os.path.abspath(DB_PATH)}")


if __name__ == "__main__":
    index_hardware()
