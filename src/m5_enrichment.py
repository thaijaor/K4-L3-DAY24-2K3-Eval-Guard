from __future__ import annotations

"""
Module 5: Enrichment Pipeline
==============================
Làm giàu chunks TRƯỚC khi embed: Summarize, HyQA, Contextual Prepend, Auto Metadata.

Test: pytest tests/test_m5.py
"""

import os, sys, json, re, time, hashlib
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import OPENAI_API_KEY, OPENAI_MODEL, ENRICH_CACHE_PATH, ENRICH_WORKERS


@dataclass
class EnrichedChunk:
    """Chunk đã được làm giàu."""
    original_text: str
    enriched_text: str
    summary: str
    hypothesis_questions: list[str]
    auto_metadata: dict
    method: str  # "contextual", "summary", "hyqa", "full"


# ─── LLM helper ──────────────────────────────────────────


def _chat(system: str, user: str, max_tokens: int, json_mode: bool = False, retries: int = 5) -> str:
    """Gọi LLM (Gemini qua endpoint OpenAI-compatible), retry khi 429/5xx."""
    from config import get_llm_client
    client = get_llm_client()
    kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                max_tokens=max_tokens, temperature=0, reasoning_effort="minimal", **kwargs,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as e:
            status = getattr(e, "status_code", None)
            if attempt == retries - 1 or (status is not None and status < 500 and status != 429):
                raise
            time.sleep(min(2 ** attempt * 2, 30))
    return ""


def _parse_json(raw: str) -> dict:
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
    data = json.loads(raw)
    return data if isinstance(data, dict) else {}


# ─── Technique 1: Chunk Summarization ────────────────────


def summarize_chunk(text: str) -> str:
    """
    Tạo summary ngắn cho chunk.
    Embed summary thay vì (hoặc cùng với) raw chunk → giảm noise.
    """
    if OPENAI_API_KEY:
        try:
            summary = _chat("Tóm tắt đoạn văn sau trong 2-3 câu ngắn gọn bằng tiếng Việt, "
                            "không dài hơn đoạn gốc.", text, max_tokens=150)
            # Đoạn gốc đã rất ngắn thì summary không được dài hơn nó
            return summary if summary and len(summary) <= len(text) else text
        except Exception as e:
            print(f"  ⚠️  LLM summarize failed: {e}")

    # Extractive fallback (không cần API)
    sentences = [s.strip() for s in text.replace("\n", " ").split(". ") if s.strip()]
    return ". ".join(sentences[:2]).rstrip(".") + "." if sentences else text


# ─── Technique 2: Hypothesis Question-Answer (HyQA) ─────


def generate_hypothesis_questions(text: str, n_questions: int = 3) -> list[str]:
    """
    Generate câu hỏi mà chunk có thể trả lời.
    Index cả questions lẫn chunk → query match tốt hơn (bridge vocabulary gap).
    """
    if OPENAI_API_KEY:
        try:
            raw = _chat(f"Dựa trên đoạn văn, tạo {n_questions} câu hỏi tiếng Việt mà đoạn văn có thể trả lời. "
                        "Trả về mỗi câu hỏi trên 1 dòng, không đánh số.", text, max_tokens=200)
            questions = [q.strip().lstrip("0123456789.-*) ").strip() for q in raw.split("\n")]
            return [q for q in questions if q][:n_questions]
        except Exception as e:
            print(f"  ⚠️  LLM HyQA failed: {e}")

    # Extractive fallback
    sentences = [s.strip() for s in re.split(r'[.!?\n]', text) if len(s.strip()) > 10]
    return [f"{s.rstrip('.')}?" for s in sentences[:n_questions]]


# ─── Technique 3: Contextual Prepend (Anthropic style) ──


def contextual_prepend(text: str, document_title: str = "") -> str:
    """
    Prepend context giải thích chunk nằm ở đâu trong document.
    Anthropic benchmark: giảm 49% retrieval failure (alone).
    """
    if OPENAI_API_KEY:
        try:
            context = _chat("Viết 1 câu ngắn mô tả đoạn văn này nằm ở đâu trong tài liệu và nói về chủ đề gì. "
                            "Chỉ trả về 1 câu.",
                            f"Tài liệu: {document_title}\n\nĐoạn văn:\n{text}", max_tokens=80)
            if context:
                return f"{context}\n\n{text}"
        except Exception as e:
            print(f"  ⚠️  LLM contextual failed: {e}")

    prefix = f"Trích từ {document_title}. " if document_title else ""
    return f"{prefix}{text}"


# ─── Technique 4: Auto Metadata Extraction ──────────────


def extract_metadata(text: str) -> dict:
    """
    LLM extract metadata tự động: topic, entities, date_range, category.
    """
    if OPENAI_API_KEY:
        try:
            raw = _chat('Trích xuất metadata từ đoạn văn. Trả về JSON: {"topic": "...", "entities": ["..."], '
                        '"category": "policy|hr|it|finance", "language": "vi|en"}',
                        text, max_tokens=200, json_mode=True)
            return _parse_json(raw)
        except Exception as e:
            print(f"  ⚠️  LLM metadata failed: {e}")

    return {"topic": "general", "entities": [], "category": "policy", "language": "vi"}


# ─── Combined Single-Call Mode ───────────────────────────

_COMBINED_PROMPT = """Phân tích đoạn văn (một phần của tài liệu nội bộ công ty) và trả về JSON:
{
  "summary": "tóm tắt 2-3 câu",
  "questions": ["câu hỏi 1", "câu hỏi 2", "câu hỏi 3"],
  "context": "1 câu mô tả đoạn văn nằm ở đâu trong tài liệu (tên tài liệu, phiên bản nếu có, mục) và nói về gì",
  "metadata": {"topic": "...", "entities": ["..."], "category": "policy|hr|it|finance", "language": "vi|en"}
}
Câu hỏi phải là câu người dùng có thể hỏi và đoạn văn trả lời được. Chỉ trả JSON."""


def _cache_key(text: str, source: str) -> str:
    return hashlib.sha256(f"{OPENAI_MODEL}\n{source}\n{text}".encode()).hexdigest()


def _load_cache() -> dict:
    try:
        with open(ENRICH_CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_cache(cache: dict) -> None:
    os.makedirs(os.path.dirname(ENRICH_CACHE_PATH), exist_ok=True)
    with open(ENRICH_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)


def _enrich_single_call(text: str, source: str) -> dict:
    """Single LLM call to get summary + questions + context + metadata.

    ⚠️ Cost optimization: 1 API call thay vì 4 calls riêng lẻ.
    """
    if OPENAI_API_KEY:
        for attempt in range(3):  # retry khi LLM trả JSON hỏng
            try:
                raw = _chat(_COMBINED_PROMPT, f"Tài liệu: {source}\n\nĐoạn văn:\n{text}",
                            max_tokens=800, json_mode=True)
                return _parse_json(raw)
            except Exception as e:
                if attempt == 2:
                    print(f"  ⚠️  Enrichment API failed: {e}")
    return {}


# ─── Full Enrichment Pipeline ────────────────────────────


def _combined_results(chunks: list[dict]) -> list[dict]:
    """Chạy _enrich_single_call song song + cache ra đĩa (chạy lại pipeline không tốn API)."""
    from concurrent.futures import ThreadPoolExecutor

    cache = _load_cache()
    keys = [_cache_key(c["text"], c.get("metadata", {}).get("source", "")) for c in chunks]
    todo = [i for i, k in enumerate(keys) if k not in cache]
    if todo:
        print(f"  {len(chunks) - len(todo)} cached, calling LLM for {len(todo)} chunks...", flush=True)

        def work(i):
            c = chunks[i]
            return i, _enrich_single_call(c["text"], c.get("metadata", {}).get("source", ""))

        with ThreadPoolExecutor(max_workers=ENRICH_WORKERS) as pool:
            for n, (i, result) in enumerate(pool.map(work, todo), 1):
                if result:
                    cache[keys[i]] = result
                if n % 50 == 0:
                    _save_cache(cache)
        _save_cache(cache)
    return [cache.get(k, {}) for k in keys]


def enrich_chunks(
    chunks: list[dict],
    methods: list[str] | None = None,
) -> list[EnrichedChunk]:
    """
    Chạy enrichment pipeline trên danh sách chunks.

    Có 2 chế độ:
    - methods cụ thể (["summary"], ["contextual"]...): gọi từng function riêng (tốt cho học/debug)
    - methods=["combined"] hoặc None: 1 API call duy nhất cho tất cả (tốt cho production)

    Args:
        chunks: List of {"text": str, "metadata": dict}
        methods: Default None → combined mode (1 call/chunk).
                 Options: "summary", "hyqa", "contextual", "metadata", "combined"
    """
    if methods is None:
        methods = ["combined"]

    use_combined = "combined" in methods
    combined = _combined_results(chunks) if use_combined else []

    enriched = []
    for i, chunk in enumerate(chunks):
        text = chunk["text"]
        source = chunk.get("metadata", {}).get("source", "")

        if use_combined:
            result = combined[i]
            summary = result.get("summary", "")
            questions = [q for q in result.get("questions", []) if isinstance(q, str)]
            context_line = result.get("context", "")
            enriched_text = f"{context_line}\n\n{text}" if context_line else text
            if questions:
                # HyQA: index thêm câu hỏi giả định để bắc cầu vocabulary giữa query và chunk
                enriched_text += "\n\nCâu hỏi liên quan: " + " | ".join(questions)
            auto_meta = result.get("metadata", {})
            auto_meta = auto_meta if isinstance(auto_meta, dict) else {}
        else:
            summary = summarize_chunk(text) if "summary" in methods else ""
            questions = generate_hypothesis_questions(text) if "hyqa" in methods else []
            enriched_text = contextual_prepend(text, source) if "contextual" in methods else text
            auto_meta = extract_metadata(text) if "metadata" in methods else {}

        enriched.append(EnrichedChunk(
            original_text=text,
            enriched_text=enriched_text,
            summary=summary,
            hypothesis_questions=questions,
            auto_metadata={**chunk.get("metadata", {}), **{f"auto_{k}": v for k, v in auto_meta.items()}},
            method="+".join(methods),
        ))

        if (i + 1) % 100 == 0 or (i + 1) == len(chunks):
            print(f"  Enriched {i + 1}/{len(chunks)} chunks...", flush=True)

    return enriched


# ─── Main ────────────────────────────────────────────────

if __name__ == "__main__":
    sample = "Nhân viên chính thức được nghỉ phép năm 12 ngày làm việc mỗi năm. Số ngày nghỉ phép tăng thêm 1 ngày cho mỗi 5 năm thâm niên công tác."

    print("=== Enrichment Pipeline Demo ===\n")
    print(f"Original: {sample}\n")

    s = summarize_chunk(sample)
    print(f"Summary: {s}\n")

    qs = generate_hypothesis_questions(sample)
    print(f"HyQA questions: {qs}\n")

    ctx = contextual_prepend(sample, "Sổ tay nhân viên VinUni 2024")
    print(f"Contextual: {ctx}\n")

    meta = extract_metadata(sample)
    print(f"Auto metadata: {meta}")
