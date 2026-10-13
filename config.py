"""Shared configuration for K4 / Track 3B: Eval + Guardrail Stack."""

import os
from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

# --- API Keys ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL") or None
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "google/gemini-3.5-flash-lite")
HF_TOKEN = os.getenv("HF_TOKEN", "")  # Optional: for HuggingFace models

# Vertex AI OpenAI-compatible endpoint chỉ nhận API key qua header x-goog-api-key;
# key đặt trong Authorization (Bearer) bị hiểu là OAuth token → 401.
_IS_VERTEX = bool(OPENAI_BASE_URL and "aiplatform.googleapis.com" in OPENAI_BASE_URL)
LLM_CLIENT_KWARGS = {
    "api_key": "vertex-header-auth" if _IS_VERTEX else OPENAI_API_KEY,
    "base_url": OPENAI_BASE_URL,
    "default_headers": {"x-goog-api-key": OPENAI_API_KEY} if _IS_VERTEX else None,
    "max_retries": 8,  # SDK tự backoff khi 429 (Vertex rate limit theo phút)
}


def get_llm_client():
    """OpenAI client trỏ tới Gemini (Vertex AI hoặc AI Studio) theo .env."""
    from openai import OpenAI
    return OpenAI(**LLM_CLIENT_KWARGS)

# --- Qdrant (same as Day 18) ---
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
COLLECTION_NAME = "lab24_production"
NAIVE_COLLECTION = "lab24_naive"

# --- Embedding (same as Day 18) ---
EMBEDDING_MODEL = "BAAI/bge-m3"
EMBEDDING_DIM = 1024

# --- Chunking (same as Day 18) ---
HIERARCHICAL_PARENT_SIZE = 2048
HIERARCHICAL_CHILD_SIZE = 256
SEMANTIC_THRESHOLD = 0.85
SEMANTIC_MODEL = "BAAI/bge-m3"

# --- Search (same as Day 18) ---
BM25_TOP_K = 20
DENSE_TOP_K = 20
HYBRID_TOP_K = 20
RERANK_TOP_K = 3

# --- Enrichment (M5, same as Day 18) ---
ENRICH_WORKERS = 8

# --- Paths ---
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT_DIR, "data")
FIXTURES_DIR = os.path.join(ROOT_DIR, "fixtures")
ARTIFACTS_DIR = os.path.join(ROOT_DIR, "artifacts")
TEST_SET_PATH = os.path.join(FIXTURES_DIR, "test_set_50q.json")
ANSWERS_PATH = os.path.join(ARTIFACTS_DIR, "answers_50q.json")
HUMAN_LABELS_PATH = os.path.join(FIXTURES_DIR, "human_labels_10q.json")
ADVERSARIAL_SET_PATH = os.path.join(FIXTURES_DIR, "adversarial_set_20.json")
CLEAN_SET_PATH = os.path.join(FIXTURES_DIR, "clean_set_8.json")
OUTPUT_SET_PATH = os.path.join(FIXTURES_DIR, "output_set_4.json")
GUARDRAILS_CONFIG_DIR = os.path.join(ROOT_DIR, "guardrails")
ENRICH_CACHE_PATH = os.path.join(ROOT_DIR, ".cache", "enrich_cache.json")
PAIR_QUESTION_IDS = (1, 5, 12, 21, 41)

# --- LLM Judge ---
GENERATION_MODEL = OPENAI_MODEL
JUDGE_MODEL = OPENAI_MODEL

# --- Guardrail latency budget ---
LATENCY_BUDGET_P95_MS = 500  # Full guard target; Task 12 currently measures input guards only.
PRESIDIO_LANGUAGE = "en"    # Presidio base language; custom VN recognizers added via PatternRecognizer
