"""
app/services/drive_pipeline.py
SF Drive — File ingestion pipeline.

On every upload this runs:
  1. Extract text  (PyMuPDF for PDF, python-docx for DOCX, plain read for txt/md/csv)
  2. Auto-classify knowledge_type from mime + filename heuristics
  3. Auto-generate tags
  4. Call Groq (primary) / OpenAI (fallback) to generate summary_short + summary_long
  5. Persist results and mark file as indexed

Usage:
    from app.services.drive_pipeline import run_pipeline
    run_pipeline(drive_file_id)     # call after commit so id exists
"""

import os
import re
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Optional heavy imports — graceful degradation ─────────────────────────────
try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

try:
    from docx import Document as DocxDocument
    HAS_PYTHON_DOCX = True
except ImportError:
    HAS_PYTHON_DOCX = False

try:
    from groq import Groq
    _groq_client = Groq(api_key=os.getenv('GROQ_API_KEY', ''))
    HAS_GROQ = bool(os.getenv('GROQ_API_KEY'))
except Exception:
    HAS_GROQ = False
    _groq_client = None

try:
    import openai
    openai.api_key = os.getenv('OPENAI_API_KEY', '')
    HAS_OPENAI = bool(os.getenv('OPENAI_API_KEY'))
except Exception:
    HAS_OPENAI = False


# ══════════════════════════════════════════════════════════════════════════════
# 1. Text extraction
# ══════════════════════════════════════════════════════════════════════════════

def extract_text(file_path: str, mime_type: str) -> str:
    """
    Extract plain text from a file. Returns '' on failure.
    Supported: PDF, DOCX, TXT, MD, CSV. Everything else returns ''.
    """
    try:
        if mime_type == 'application/pdf' or file_path.endswith('.pdf'):
            return _extract_pdf(file_path)

        if mime_type in (
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/msword',
        ) or file_path.endswith(('.docx', '.doc')):
            return _extract_docx(file_path)

        if mime_type in ('text/plain', 'text/markdown', 'text/csv') or \
                file_path.endswith(('.txt', '.md', '.csv', '.json', '.yaml', '.yml')):
            return _extract_plain(file_path)

    except Exception as exc:
        logger.warning("Text extraction failed for %s: %s", file_path, exc)

    return ''


def _extract_pdf(path: str) -> str:
    if not HAS_PYMUPDF:
        logger.warning("PyMuPDF not installed — PDF extraction skipped. pip install pymupdf")
        return ''
    text_parts = []
    with fitz.open(path) as doc:
        for page in doc:
            text_parts.append(page.get_text())
    return '\n'.join(text_parts)


def _extract_docx(path: str) -> str:
    if not HAS_PYTHON_DOCX:
        logger.warning("python-docx not installed — DOCX extraction skipped. pip install python-docx")
        return ''
    doc = DocxDocument(path)
    return '\n'.join(p.text for p in doc.paragraphs if p.text.strip())


def _extract_plain(path: str) -> str:
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        return f.read()


# ══════════════════════════════════════════════════════════════════════════════
# 2. Knowledge type classification
# ══════════════════════════════════════════════════════════════════════════════

# Keyword → knowledge_type mapping (checked against lowercased filename)
_KT_RULES = [
    (['roadmap', 'timeline'],                   'roadmap'),
    (['transcript', 'meeting-notes', 'call-notes'], 'meeting-transcript'),
    (['notes', 'minutes'],                      'meeting-notes'),
    (['milestone', 'proof', 'evidence'],        'milestone-proof'),
    (['pitch', 'deck', 'investor'],             'pitch'),
    (['contract', 'agreement', 'nda'],          'contract'),
    (['invoice', 'receipt', 'payment'],         'invoice'),
    (['spec', 'specification', 'requirements'], 'spec'),
    (['architecture', 'system-design', 'tech'], 'architecture'),
    (['gtm', 'go-to-market', 'marketing'],      'gtm'),
    (['research', 'report', 'analysis'],        'research'),
    (['design', 'mockup', 'wireframe', 'figma'],'design'),
    (['legal', 'compliance', 'policy'],         'legal'),
    (['product', 'prd', 'feature'],             'product'),
]

def classify_knowledge_type(filename: str, mime_type: str) -> str:
    name_lower = filename.lower().replace('_', '-').replace(' ', '-')
    for keywords, kt in _KT_RULES:
        if any(kw in name_lower for kw in keywords):
            return kt
    # Fallback by mime
    if 'video' in (mime_type or ''):
        return 'recording'
    if 'audio' in (mime_type or ''):
        return 'recording'
    if 'image' in (mime_type or ''):
        return 'design'
    return 'other'


# ══════════════════════════════════════════════════════════════════════════════
# 3. Auto-tag generation
# ══════════════════════════════════════════════════════════════════════════════

# Context tags inferred from filename
_TAG_RULES = [
    (['roadmap'],                   ['roadmap', 'planning']),
    (['pitch', 'deck'],             ['pitch', 'investor-ready']),
    (['transcript'],                ['meeting', 'transcript']),
    (['notes', 'minutes'],          ['meeting', 'notes']),
    (['milestone'],                 ['milestone']),
    (['spec', 'specification'],     ['spec', 'technical']),
    (['architecture'],              ['architecture', 'technical']),
    (['invoice'],                   ['finance', 'invoice']),
    (['contract', 'agreement'],     ['legal', 'contract']),
    (['research'],                  ['research']),
    (['gtm', 'go-to-market'],       ['marketing', 'gtm']),
    (['design', 'mockup'],          ['design']),
    (['mvp'],                       ['mvp']),
    (['v1', 'v2', 'v3'],            ['versioned']),
    (['draft'],                     ['draft']),
    (['final'],                     ['final']),
    (['approved'],                  ['approved']),
]

def auto_generate_tags(filename: str, mime_type: str, knowledge_type: str) -> list:
    tags = set()
    name_lower = filename.lower().replace('_', '-').replace(' ', '-')

    for keywords, tag_group in _TAG_RULES:
        if any(kw in name_lower for kw in keywords):
            tags.update(tag_group)

    # Add knowledge_type as a tag too
    if knowledge_type and knowledge_type != 'other':
        tags.add(knowledge_type)

    # Mime-based tags
    if mime_type:
        if 'pdf'   in mime_type: tags.add('pdf')
        if 'image' in mime_type: tags.add('image')
        if 'video' in mime_type: tags.add('video')
        if 'audio' in mime_type: tags.add('audio')
        if 'spreadsheet' in mime_type or 'excel' in mime_type: tags.add('spreadsheet')

    return list(tags)


# ══════════════════════════════════════════════════════════════════════════════
# 4. AI summary generation
# ══════════════════════════════════════════════════════════════════════════════

_SUMMARY_SYSTEM = (
    "You are an AI assistant inside SF Collab, a startup collaboration platform. "
    "You receive extracted text from a file uploaded by a startup team. "
    "Your job is to produce a JSON object with exactly two keys: "
    "'summary_short' (1-2 sentences, plain English, max 60 words) and "
    "'summary_long' (detailed summary, plain English, 100-250 words, structured). "
    "Return ONLY valid JSON. No markdown, no code blocks, no preamble."
)

def _build_prompt(filename: str, knowledge_type: str, text: str) -> str:
    preview = text[:4000] if text else '(no text could be extracted from this file)'
    return (
        f"File name: {filename}\n"
        f"Knowledge type: {knowledge_type}\n\n"
        f"Extracted content:\n{preview}\n\n"
        "Generate the JSON summary."
    )


def generate_summary(filename: str, knowledge_type: str, text: str) -> dict:
    """
    Returns {'summary_short': str, 'summary_long': str} or empty strings on failure.
    Tries Groq first, falls back to OpenAI, then returns empty.
    """
    prompt = _build_prompt(filename, knowledge_type, text)

    if HAS_GROQ:
        try:
            return _call_groq(prompt)
        except Exception as exc:
            logger.warning("Groq summary failed: %s", exc)

    if HAS_OPENAI:
        try:
            return _call_openai(prompt)
        except Exception as exc:
            logger.warning("OpenAI summary failed: %s", exc)

    logger.warning("No AI provider available — summaries skipped for %s", filename)
    return {'summary_short': '', 'summary_long': ''}


def _call_groq(prompt: str) -> dict:
    response = _groq_client.chat.completions.create(
        model='llama3-8b-8192',
        messages=[
            {'role': 'system',  'content': _SUMMARY_SYSTEM},
            {'role': 'user',    'content': prompt},
        ],
        temperature=0.3,
        max_tokens=600,
    )
    raw = response.choices[0].message.content.strip()
    return _parse_summary_json(raw)


def _call_openai(prompt: str) -> dict:
    response = openai.chat.completions.create(
        model='gpt-4o-mini',
        messages=[
            {'role': 'system',  'content': _SUMMARY_SYSTEM},
            {'role': 'user',    'content': prompt},
        ],
        temperature=0.3,
        max_tokens=600,
    )
    raw = response.choices[0].message.content.strip()
    return _parse_summary_json(raw)


def _parse_summary_json(raw: str) -> dict:
    # Strip markdown fences if present
    raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.MULTILINE)
    raw = re.sub(r'\s*```$',          '', raw, flags=re.MULTILINE)
    data = json.loads(raw.strip())
    return {
        'summary_short': str(data.get('summary_short', '')),
        'summary_long':  str(data.get('summary_long',  '')),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 5. Main pipeline entry point
# ══════════════════════════════════════════════════════════════════════════════

def run_pipeline(drive_file_id: int) -> bool:
    """
    Run the full ingestion pipeline for a DriveFile record.
    Call this AFTER the record has been committed to DB (id must exist).

    Returns True on success, False on failure.
    """
    # Import here to avoid circular imports at module load time
    from app.extensions import db
    from app.models.DriveFile import DriveFile

    drive_file = DriveFile.query.get(drive_file_id)
    if not drive_file:
        logger.error("DriveFile %s not found", drive_file_id)
        return False

    try:
        drive_file.file_state      = 'processing'
        drive_file.indexing_status = 'processing'
        db.session.commit()

        # Resolve physical file path
        base_dir   = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
        file_path  = os.path.join(base_dir, 'uploads', 'drive_files', drive_file.filename)

        # Step 1: Extract text
        text = extract_text(file_path, drive_file.mime_type or '')
        drive_file.extracted_text = text[:50000] if text else ''  # cap at 50k chars

        # Step 2: Classify knowledge type (only if not already set by user)
        if not drive_file.knowledge_type or drive_file.knowledge_type == 'other':
            drive_file.knowledge_type = classify_knowledge_type(
                drive_file.original_name, drive_file.mime_type or ''
            )

        # Step 3: Auto-generate tags (merge with any existing manual tags)
        auto_tags = auto_generate_tags(
            drive_file.original_name,
            drive_file.mime_type or '',
            drive_file.knowledge_type,
        )
        drive_file.add_tags(auto_tags)

        # Step 4: Generate AI summaries
        summaries = generate_summary(
            drive_file.original_name,
            drive_file.knowledge_type,
            text,
        )
        drive_file.summary_short = summaries.get('summary_short', '')
        drive_file.summary_long  = summaries.get('summary_long',  '')

        # Step 5: Mark as indexed
        drive_file.file_state      = 'indexed'
        drive_file.indexing_status = 'done'
        drive_file.indexed_at      = datetime.utcnow()

        db.session.commit()
        logger.info("Drive pipeline complete | file_id=%s", drive_file_id)
        return True

    except Exception as exc:
        db.session.rollback()
        drive_file.file_state      = 'uploaded'   # revert so retry is possible
        drive_file.indexing_status = 'failed'
        db.session.commit()
        logger.exception("Drive pipeline failed | file_id=%s: %s", drive_file_id, exc)
        return False