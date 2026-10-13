from __future__ import annotations

"""Module 4: RAGAS Evaluation — 4 metrics + failure analysis."""

import os, sys, json, math
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
from dataclasses import dataclass, asdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import TEST_SET_PATH

METRICS = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]


@dataclass
class EvalResult:
    question: str
    answer: str
    contexts: list[str]
    ground_truth: str
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float


def load_test_set(path: str = TEST_SET_PATH) -> list[dict]:
    """Load test set from JSON. (Đã implement sẵn)"""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _is_nan(x) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))


def _nanmean(values: list[float]) -> float:
    vals = [v for v in values if not _is_nan(v)]
    return float(sum(vals) / len(vals)) if vals else 0.0


def _ragas_models():
    """LLM judge = Gemini (OpenAI-compatible endpoint), embeddings = bge-m3 local (dùng chung với M2)."""
    from langchain_core.embeddings import Embeddings
    from langchain_openai import ChatOpenAI
    from config import OPENAI_MODEL, LLM_CLIENT_KWARGS
    from src.m2_search import get_encoder

    class LocalEmbeddings(Embeddings):
        def embed_documents(self, texts):
            return get_encoder().encode(texts, normalize_embeddings=True).tolist()

        def embed_query(self, text):
            return get_encoder().encode(text, normalize_embeddings=True).tolist()

    # Gemini không hỗ trợ n>1 ("Multiple candidates is not enabled") → để RAGAS gọi n lần riêng
    # (answer_relevancy sinh 3 câu hỏi ngược với strictness=3).
    import ragas.llms.base as ragas_llm_base
    ragas_llm_base.is_multiple_completion_supported = lambda llm: False

    llm = ChatOpenAI(model=OPENAI_MODEL, api_key=LLM_CLIENT_KWARGS["api_key"],
                     base_url=LLM_CLIENT_KWARGS["base_url"],
                     default_headers=LLM_CLIENT_KWARGS["default_headers"],
                     temperature=0, max_retries=8, timeout=180)
    return llm, LocalEmbeddings()


def _ragas_rows(questions, answers, contexts, ground_truths, llm, embeddings) -> list[dict]:
    """Một lượt RAGAS; trả list dict 4 metric (có thể NaN nếu judge parse lỗi)."""
    from ragas import evaluate
    from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
    from ragas.run_config import RunConfig
    from datasets import Dataset

    dataset = Dataset.from_dict({
        "question": questions, "answer": answers,
        "contexts": contexts, "ground_truth": ground_truths,
    })
    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=llm, embeddings=embeddings,
        run_config=RunConfig(timeout=180, max_retries=10, max_wait=60, max_workers=4),
        raise_exceptions=False,
    )
    df = result.to_pandas()
    return [{m: (float(row[m]) if m in row and not _is_nan(row[m]) else float("nan")) for m in METRICS}
            for _, row in df.iterrows()]


def evaluate_ragas(questions: list[str], answers: list[str],
                   contexts: list[list[str]], ground_truths: list[str],
                   nan_retries: int = 3) -> dict:
    """Run RAGAS evaluation.

    Câu nào có metric NaN (judge trả JSON lỗi/timeout) được chấm lại tối đa `nan_retries` lượt;
    không tự thay NaN bằng điểm giả. metadata.evaluator_models ghi model thực sự dùng.
    """
    from config import OPENAI_MODEL, EMBEDDING_MODEL
    try:
        llm, embeddings = _ragas_models()
        rows = _ragas_rows(questions, answers, contexts, ground_truths, llm, embeddings)
        for attempt in range(nan_retries):
            pending = [i for i, r in enumerate(rows) if any(_is_nan(v) for v in r.values())]
            if not pending:
                break
            print(f"  RAGAS NaN ở {len(pending)} câu → chấm lại (lượt {attempt + 1}/{nan_retries})")
            redo = _ragas_rows([questions[i] for i in pending], [answers[i] for i in pending],
                               [contexts[i] for i in pending], [ground_truths[i] for i in pending],
                               llm, embeddings)
            for i, new in zip(pending, redo):
                rows[i] = {m: (new[m] if _is_nan(rows[i][m]) else rows[i][m]) for m in METRICS}
        per_question = [EvalResult(question=q, answer=a, contexts=list(c), ground_truth=gt, **r)
                        for r, q, a, c, gt in zip(rows, questions, answers, contexts, ground_truths)]
        scores = {m: _nanmean([getattr(r, m) for r in per_question]) for m in METRICS}
        return {**scores, "per_question": per_question,
                "metadata": {"evaluator_models": [OPENAI_MODEL, EMBEDDING_MODEL]}}
    except Exception as e:
        print(f"  ⚠️  RAGAS evaluation failed: {e}")
        return {"faithfulness": 0.0, "answer_relevancy": 0.0,
                "context_precision": 0.0, "context_recall": 0.0, "per_question": [],
                "metadata": {"evaluator_models": []}}


DIAGNOSTIC_TREE = {
    "faithfulness": ("LLM hallucinating — answer chứa thông tin không có trong context",
                     "Tighten prompt (chỉ dùng context), lower temperature, yêu cầu trích dẫn"),
    "context_recall": ("Missing relevant chunks — retriever bỏ sót tài liệu chứa đáp án",
                       "Improve chunking (parent-child), add BM25/HyQA, tăng top-k trước rerank"),
    "context_precision": ("Too many irrelevant chunks — context nhiễu xếp trên chunk đúng",
                          "Add reranking or metadata filter (version/department), giảm top-k"),
    "answer_relevancy": ("Answer doesn't match question — trả lời lan man hoặc từ chối",
                         "Improve prompt template: trả lời trực tiếp câu hỏi trước, rồi mới giải thích"),
}


def failure_analysis(eval_results: list[EvalResult], bottom_n: int = 10) -> list[dict]:
    """Analyze bottom-N worst questions using Diagnostic Tree."""
    analyzed = []
    for r in eval_results:
        scores = {m: getattr(r, m) for m in METRICS}
        valid = {m: s for m, s in scores.items() if not _is_nan(s)}
        avg = sum(valid.values()) / len(valid) if valid else 0.0
        worst_metric = min(valid, key=valid.get) if valid else "faithfulness"
        diagnosis, fix = DIAGNOSTIC_TREE[worst_metric]
        analyzed.append({
            "question": r.question,
            "worst_metric": worst_metric,
            "score": round(valid.get(worst_metric, 0.0), 4),
            "avg_score": round(avg, 4),
            "scores": {m: (None if _is_nan(s) else round(s, 4)) for m, s in scores.items()},
            "diagnosis": diagnosis,
            "suggested_fix": fix,
            "answer": r.answer,
            "ground_truth": r.ground_truth,
        })
    analyzed.sort(key=lambda x: x["avg_score"])
    return analyzed[:bottom_n]


def save_report(results: dict, failures: list[dict], path: str = "reports/ragas_report.json",
                extra: dict | None = None):
    """Save evaluation report to JSON."""
    parent_dir = os.path.dirname(path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    per_question = results.get("per_question", [])
    report = {
        "aggregate": {k: v for k, v in results.items() if k != "per_question"},
        "num_questions": len(per_question),
        "failures": failures,
        "per_question": [{k: (None if _is_nan(v) else v) for k, v in asdict(r).items()}
                         for r in per_question],
        **(extra or {}),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Report saved to {path}")


if __name__ == "__main__":
    test_set = load_test_set()
    print(f"Loaded {len(test_set)} test questions")
    print("Run pipeline.py first to generate answers, then call evaluate_ragas().")
