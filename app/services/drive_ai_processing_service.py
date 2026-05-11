"""
SF Drive AI Processing Pipeline – MVP stubs.

Implementations will be filled in with actual text extraction,
LLM summarisation, and embedding generation.
"""
import time


def extract_text(file_path: str) -> str:
    """Extract raw text from a file. Stub."""
    # TODO: integrate PyPDF2, python-docx, etc.
    return ""


def generate_summary(text: str) -> dict:
    """Generate short + long summaries using an LLM. Stub."""
    return {
        "short_summary": "Automatically generated summary (placeholder)",
        "long_summary": "Longer, more detailed summary (placeholder)"
    }


def generate_tags(text: str) -> list:
    """Suggest knowledge_type and tags from content. Stub."""
    return []


def chunk_text(text: str) -> list:
    """Split text into chunks for embedding. Stub."""
    return [text[i:i+1000] for i in range(0, len(text), 1000)]


def generate_embeddings(chunks: list) -> list:
    """Convert each chunk into a vector embedding. Stub."""
    return []


def process_file_async(file_id: int):
    """
    Background task entry point.
    Marks file as processing, performs extraction/summary/embedding,
    then marks as indexed.
    """
    from app.extensions import db
    from app.models.drive_file import DriveFile

    file = DriveFile.query.get(file_id)
    if not file:
        return
    file.state = 'processing'
    db.session.commit()

    # Simulate work
    time.sleep(2)

    # Set AI fields (for now, placeholders)
    file.short_summary = "Placeholder summary – AI processing not yet implemented"
    file.long_summary = "This is a placeholder long summary."
    file.tags_json = ["auto-generated"]
    file.vector_index_status = 'completed'
    file.state = 'indexed'
    db.session.commit()