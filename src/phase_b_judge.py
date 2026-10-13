from __future__ import annotations

"""Phase B: LLM-as-Judge — pairwise, swap-and-average, Cohen κ, bias analysis."""

import json
import os
import sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import OPENAI_API_KEY, JUDGE_MODEL, HUMAN_LABELS_PATH, get_llm_client


@dataclass
class JudgeResult:
    question: str
    answer_a: str
    answer_b: str
    winner_pass1: str       # "A" | "B" | "tie"  (original order)
    winner_pass2: str       # "A" | "B" | "tie"  (after swap, ALREADY converted back)
    final_winner: str       # consensus after swap-and-average
    reasoning_pass1: str
    reasoning_pass2: str
    position_consistent: bool  # True if both passes agree on same answer
    scores_pass1: dict = field(default_factory=dict)  # {"A": float, "B": float}
    scores_pass2: dict = field(default_factory=dict)


# ─── Task 5: Pairwise Judge ───────────────────────────────────────────────────

PAIRWISE_SYSTEM_PROMPT = """Bạn là chuyên gia đánh giá chất lượng câu trả lời RAG dựa trên chính sách tham chiếu.
So sánh Answer A và Answer B theo 3 tiêu chí ưu tiên:
1. Độ chính xác (accuracy): khớp chính xác với chính sách tham chiếu, đúng phiên bản, bảo toàn điều kiện và phủ định.
2. Độ đầy đủ (completeness): trả lời đủ các khía cạnh thiết yếu của câu hỏi.
3. Tính súc tích (conciseness): không thừa thãi hay lan man. Độ dài không phải là lý do để một câu trả lời thắng.

Đánh giá khách quan, không thiên vị vị trí xuất hiện (A hay B) hay độ dài văn bản.
Trả về định dạng JSON duy nhất:
{"winner": "A" hoặc "B" hoặc "tie", "reasoning": "giải thích ngắn gọn", "scores": {"A": float trong [0,1], "B": float trong [0,1]}}"""


def pairwise_judge(question: str, answer_a: str, answer_b: str, reference: str = "") -> dict:
    """Task 5: Gọi LLM để chọn answer tốt hơn (A hoặc B) theo 3 tiêu chí.

    Tiêu chí đánh giá:
        - Độ chính xác (accuracy): có khớp với thực tế chính sách không?
        - Độ đầy đủ (completeness): có trả lời đủ câu hỏi không?
        - Tính súc tích (conciseness): có thừa / thiếu thông tin không?

    Returns:
        {"winner": "A"|"B"|"tie", "reasoning": str, "scores": {"A": float, "B": float}}
    """
    client = get_llm_client()
    user_content = (
        f"Câu hỏi: {question}\n\n"
        f"Chính sách/đáp án tham chiếu: {reference}\n\n"
        f"Answer A:\n{answer_a}\n\n"
        f"Answer B:\n{answer_b}\n\n"
        "Hãy đánh giá và trả về kết quả JSON theo yêu cầu."
    )
    resp = client.chat.completions.create(
        model=JUDGE_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": PAIRWISE_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    )
    result = json.loads(resp.choices[0].message.content)

    winner = result.get("winner")
    if winner not in ("A", "B", "tie"):
        raise ValueError(f"Invalid winner in judge response: {winner}")

    reasoning = result.get("reasoning", "")
    if not isinstance(reasoning, str) or not reasoning.strip():
        raise ValueError("Judge response must provide reasoning.")

    scores = result.get("scores", {})
    if not isinstance(scores, dict) or "A" not in scores or "B" not in scores:
        raise ValueError("Judge response must provide scores dict with 'A' and 'B'.")

    score_a = float(scores["A"])
    score_b = float(scores["B"])
    if not (0.0 <= score_a <= 1.0 and 0.0 <= score_b <= 1.0):
        raise ValueError(f"Scores must be in [0.0, 1.0], got A={score_a}, B={score_b}")

    return {
        "winner": winner,
        "reasoning": reasoning.strip(),
        "scores": {"A": score_a, "B": score_b},
    }


# ─── Task 6: Swap-and-Average ─────────────────────────────────────────────────

def swap_and_average(question: str, answer_a: str, answer_b: str, reference: str = "") -> JudgeResult:
    """Task 6: Chạy pairwise 2 lần (hoán đổi thứ tự), lấy kết quả nhất quán.

    Lý do: LLM thường có position bias (ưu tiên answer xuất hiện trước).
    Bằng cách swap, ta phát hiện và giảm bias này.

    Logic:
        Pass 1: judge(q, A, B) → winner_1 (trong không gian A/B)
        Pass 2: judge(q, B, A) → winner_2_raw (trong không gian B/A)
        Convert: nếu winner_2_raw="A" thì thực ra là B (vì đã swap)
        Final:   nếu winner_1 == winner_2 → final = winner_1
                 nếu khác nhau → final = "tie"
    """
    pass1 = pairwise_judge(question, answer_a, answer_b, reference=reference)
    pass2_raw = pairwise_judge(question, answer_b, answer_a, reference=reference)

    swap_map = {"A": "B", "B": "A", "tie": "tie"}
    winner_pass2 = swap_map[pass2_raw["winner"]]

    position_consistent = (pass1["winner"] == winner_pass2)
    final_winner = pass1["winner"] if position_consistent else "tie"

    scores_pass1 = pass1.get("scores", {})
    raw_scores_pass2 = pass2_raw.get("scores", {})
    scores_pass2 = {
        "A": raw_scores_pass2.get("B", 0.0),
        "B": raw_scores_pass2.get("A", 0.0),
    }

    return JudgeResult(
        question=question,
        answer_a=answer_a,
        answer_b=answer_b,
        winner_pass1=pass1["winner"],
        winner_pass2=winner_pass2,
        final_winner=final_winner,
        reasoning_pass1=pass1["reasoning"],
        reasoning_pass2=pass2_raw["reasoning"],
        position_consistent=position_consistent,
        scores_pass1=scores_pass1,
        scores_pass2=scores_pass2,
    )


# ─── Task 7: Cohen's κ ────────────────────────────────────────────────────────

def cohen_kappa(judge_labels: list[int], human_labels: list[int]) -> float:
    """Task 7: Tính Cohen's κ giữa LLM judge và human labels.

    Args:
        judge_labels:  nhãn từ LLM judge (0 = bad answer, 1 = good answer)
        human_labels:  nhãn từ human_labels_10q.json

    Returns:
        κ ∈ [-1, 1]
        Thang đo Landis-Koch: <0=poor, 0-0.2=slight, 0.2-0.4=fair,
                               0.4-0.6=moderate, 0.6-0.8=substantial, 0.8-1=almost perfect
    """
    if not judge_labels or not human_labels or len(judge_labels) != len(human_labels):
        return 0.0
    n = len(judge_labels)
    if n == 0:
        return 0.0

    p_o = sum(j == h for j, h in zip(judge_labels, human_labels)) / n
    p_e = (
        judge_labels.count(1) * human_labels.count(1) +
        judge_labels.count(0) * human_labels.count(0)
    ) / (n * n)

    if p_e >= 1.0:
        return 1.0 if p_o == 1.0 else 0.0

    return (p_o - p_e) / (1.0 - p_e)


# ─── Task 8: Bias Report ──────────────────────────────────────────────────────

def bias_report(judge_results: list[JudgeResult]) -> dict:
    """Task 8: Đo lường position bias và verbosity bias.

    Position bias: LLM chọn answer theo vị trí (A hay B) thay vì chất lượng.
        → Đo bằng % cases where position_consistent = False

    Verbosity bias: LLM ưu tiên answer dài hơn dù không chính xác hơn.
        → Đo bằng: trong các case A thắng, A có dài hơn B không? Tương tự cho B.

    Returns:
        {
          "total_judged": int,
          "position_bias_rate": float,        # 0-1, cao = bias nhiều
          "position_bias_count": int,
          "verbosity_bias": float,            # 0-1, > 0.6 = đáng lo ngại
          "verbosity_details": {
            "a_wins_a_longer": int,           # A thắng VÀ A dài hơn
            "b_wins_b_longer": int,           # B thắng VÀ B dài hơn
            "total_decisive": int,            # tổng case có winner rõ ràng
          },
          "interpretation": str,
        }
    """
    total = len(judge_results)
    if total == 0:
        return {
            "total_judged": 0,
            "position_bias_rate": 0.0,
            "position_bias_count": 0,
            "verbosity_bias": 0.0,
            "verbosity_details": {
                "a_wins_a_longer": 0,
                "b_wins_b_longer": 0,
                "total_decisive": 0,
            },
            "interpretation": "Không có dữ liệu đánh giá.",
        }

    position_bias_count = sum(1 for r in judge_results if not r.position_consistent)
    position_bias_rate = position_bias_count / total

    a_wins_a_longer = sum(
        1 for r in judge_results
        if r.final_winner == "A" and len(r.answer_a) > len(r.answer_b)
    )
    b_wins_b_longer = sum(
        1 for r in judge_results
        if r.final_winner == "B" and len(r.answer_b) > len(r.answer_a)
    )
    decisive = sum(1 for r in judge_results if r.final_winner != "tie")
    verbosity_bias = (a_wins_a_longer + b_wins_b_longer) / decisive if decisive > 0 else 0.0

    interpretation_parts = []
    if position_bias_rate > 0.3:
        interpretation_parts.append(
            f"Position bias cao ({position_bias_rate:.1%}) — judge nhạy cảm với thứ tự trình bày, swap-and-average là bắt buộc để khử bias."
        )
    else:
        interpretation_parts.append(
            f"Position bias thấp ({position_bias_rate:.1%}) — judge có tính nhất quán vị trí tốt giữa hai lượt đánh giá."
        )
    if decisive > 0:
        if verbosity_bias > 0.6:
            interpretation_parts.append(
                f"Verbosity bias đáng kể ({verbosity_bias:.1%}) — câu trả lời dài hơn chiếm ưu thế trong các trường hợp phân định thắng thua."
            )
        else:
            interpretation_parts.append(
                f"Verbosity bias thấp ({verbosity_bias:.1%}) — độ dài không phải yếu tố quyết định thắng thua."
            )
    else:
        interpretation_parts.append("Không có trường hợp phân định thắng thua rõ ràng (tất cả đều hòa).")

    return {
        "total_judged": total,
        "position_bias_rate": round(position_bias_rate, 4),
        "position_bias_count": position_bias_count,
        "verbosity_bias": round(verbosity_bias, 4),
        "verbosity_details": {
            "a_wins_a_longer": a_wins_a_longer,
            "b_wins_b_longer": b_wins_b_longer,
            "total_decisive": decisive,
        },
        "interpretation": " ".join(interpretation_parts),
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from scripts.run_experiments import main
    raise SystemExit(main(["--phase", "b", *sys.argv[1:]]))
