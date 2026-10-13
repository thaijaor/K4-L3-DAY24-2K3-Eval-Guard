# Phân tích lỗi Phase A

Nhóm: 2K3

Người phụ trách: Nguyễn Hồng Thái — 2A202602894

Nguồn: `artifacts/ragas_50q.json`; run timestamp: 2026-10-13T04:48:56Z.
Generation mode/fallback và điều kiện chạy: 50/50 câu `llm`, không extractive fallback. Pipeline lắp từ m1–m5 Day18: 107 child chunks (256 ký tự) có enrichment (context + HyQA), BM25 + bge-m3/Qdrant v1.9.7, RRF, rerank bge-reranker-v2-m3 lấy top-3 child chunk làm contexts. Hai PDF scan (BCTC, Nghị định 13) bị bỏ vì không có text layer. Prompt generation được sửa để trả lời bằng câu hoàn chỉnh (answer cụt "Có."/"Không tìm thấy." khiến faithfulness NaN do RAGAS không tách được statement).
Models generation/evaluator: generation `google/gemini-3.5-flash-lite`; evaluator (m4) `google/gemini-3.5-flash-lite` + embedding `BAAI/bge-m3`.

## Điểm theo distribution

| Metric | factual (20) | multi_hop (20) | adversarial (10) |
|---|---|---|---|
| faithfulness | 1.000 | 0.833 | 0.925 |
| answer_relevancy | 0.868 | 0.362 | 0.752 |
| context_precision | 0.967 | 0.562 | 0.783 |
| context_recall | 0.833 | 0.704 | 0.750 |
| avg_score | 0.917 | 0.615 | 0.803 |

## Bottom 10 và nguyên nhân

| Rank | ID | Distribution | avg_score | worst_metric | Diagnosis | Suggested fix |
|---|---|---|---|---|---|---|
| 1 | 39 | multi_hop | 0.0000 | faithfulness | LLM hallucinating | Tighten system prompt, lower temperature |
| 2 | 28 | multi_hop | 0.2500 | faithfulness | LLM hallucinating | Tighten system prompt, lower temperature |
| 3 | 21 | multi_hop | 0.2917 | answer_relevancy | Answer doesn't match question | Improve prompt template |
| 4 | 25 | multi_hop | 0.3333 | faithfulness | LLM hallucinating | Tighten system prompt, lower temperature |
| 5 | 27 | multi_hop | 0.3333 | answer_relevancy | Answer doesn't match question | Improve prompt template |
| 6 | 30 | multi_hop | 0.3750 | answer_relevancy | Answer doesn't match question | Improve prompt template |
| 7 | 35 | multi_hop | 0.4375 | answer_relevancy | Answer doesn't match question | Improve prompt template |
| 8 | 33 | multi_hop | 0.5000 | answer_relevancy | Answer doesn't match question | Improve prompt template |
| 9 | 50 | adversarial | 0.5000 | answer_relevancy | Answer doesn't match question | Improve prompt template |
| 10 | 49 | adversarial | 0.5359 | context_recall | Missing relevant chunks | Improve chunking or add BM25 |

Đọc answer/contexts/reference cho thấy nguyên nhân chung **không phải hallucination** mà là **từ chối thừa (over-refusal) khi context chỉ có từng mảnh**: 13/50 answer chứa "Không tìm thấy thông tin", 12 trong số đó là multi_hop.

- **#1 id 39, #2 id 28, #4 id 25 (faithfulness = 0):** contexts đã có đúng tài liệu (39: cả `mat_khau_v1.md` lẫn `mat_khau_v2.md`; 28: `phu_cap.md` ăn trưa + điện thoại; 25: `thu_viec.md` lương thử việc + `bang_luong_2024.md`), nhưng model trả "Không tìm thấy". Câu từ chối không được context hỗ trợ nên faithfulness = 0; diagnosis "hallucinating" của cây chẩn đoán ở đây là nhãn tổng quát, thực chất là lỗi generation ngược chiều (bỏ thông tin có sẵn).
- **id 21, 27, 33, 35 (answer_relevancy = 0):** câu hỏi cần ghép 2 nguồn + tính toán (thâm niên ÷ 3, 85% lương, cộng phụ cấp). Model trả lời một nửa rồi từ chối phần còn lại (21: đúng 18 ngày phép nhưng "không tìm thấy lương"; 33: đúng công thức phép nhưng không tính ra 19 ngày). RAGAS sinh câu hỏi ngược từ answer từ chối → relevancy 0.
- **Retrieval góp phần:** contexts là 3 child chunk ~545 ký tự (kể cả dòng context/HyQA của enrichment), nên câu multi_hop thường thiếu một vế (id 35: có bảng lương + lương thử việc, thiếu phụ cấp ăn trưa; context_recall 0.25). Câu 30 lấy 3 chunk đều từ `thu_viec.md`, không có `bao_hiem_suc_khoe.md`.
- **Hệ quả của việc sửa prompt:** câu "Nếu context không đủ → nói rõ không tìm thấy" làm model thận trọng hơn với câu nhiều vế; đó là đánh đổi để có answer đo được, cần sửa tiếp như dưới.

## Matrix và nhóm yếu nhất

| worst_metric | factual | multi_hop | adversarial | Tổng |
|---|---|---|---|---|
| faithfulness | 0 | 3 | 0 | 3 |
| answer_relevancy | 13 | 10 | 3 | 26 |
| context_precision | 2 | 2 | 2 | 6 |
| context_recall | 5 | 5 | 5 | 15 |

Nhóm yếu theo mean thấp nhất: multi_hop; mean: 0.615 (adversarial 0.803, factual 0.917).
Worst metric xuất hiện nhiều nhất: answer_relevancy; số câu: 26/50.

answer_relevancy là metric thấp nhất ở cả câu tốt (factual 13 câu, mean vẫn 0.868) vì answer có thêm câu dẫn nguồn "Theo tài liệu ... phiên bản ..." làm câu hỏi ngược lệch nhẹ; ở multi_hop nó sụp về 0 do từ chối. Bỏ các answer từ chối, relevancy multi_hop là 0.799 (8 câu) — gần factual, xác nhận vấn đề nằm ở từ chối chứ không ở cách diễn đạt.

Đề xuất sửa, theo thứ tự:
1. **Generation:** cho phép suy luận/tính toán từ số liệu trong context; trả lời từng vế, chỉ nói "không tìm thấy" cho vế thực sự thiếu. Kiểm tra: số answer chứa "Không tìm thấy" ở multi_hop giảm từ 12/20 và relevancy multi_hop tăng, faithfulness không giảm.
2. **Retrieval:** trả parent chunk (2048 ký tự, m1 đã có `parent_id`) thay cho child 256 ký tự, hoặc tăng top_k rerank lên 5 cho câu nhiều vế. Kiểm tra: context_recall multi_hop > 0.704, context_precision không giảm.
3. Chạy lại `python scripts/setup_answers.py --live` rồi `python scripts/run_experiments.py --phase a --live`, so sánh per_distribution và 10 câu bottom trên cùng 50 câu.

## Bẫy adversarial và giới hạn

adversarial mean 0.803 < factual 0.917 nhưng > multi_hop 0.615. Hai câu adversarial trong bottom 10 đúng là bẫy:
- **id 49 (version conflict):** contexts có cả `nghi_phep_nam_v2023.md` và `nghi_phep_nam_v2024.md`, model trả 12 ngày (v2023) và nói "không có thông tin chính sách nào đang hiệu lực" dù chunk v2024 nằm ngay trong contexts → pipeline **không** nhận ra bản hiện hành.
- **id 50 (policy contradiction):** câu hỏi "dùng NordVPN để tăng bảo mật" nghe hợp lý; reference là KHÔNG (VPN v1.3 cấm VPN cá nhân). Retrieval không lấy được đoạn cấm, model trả "không tìm thấy" thay vì từ chối theo chính sách.

Các câu adversarial khác điểm cao nhưng chưa chắc đúng phiên bản: id 42 trả theo v2023 ("từ 5 năm") còn id 44 liệt kê cả v1 lẫn v2 mà không nói bản nào hiệu lực; RAGAS vẫn cho ~0.82–0.85 vì answer được context (chứa bản cũ) hỗ trợ. Điểm adversarial thấp hơn factual vì vậy chỉ cho thấy nhóm này khó hơn, không chứng minh pipeline xử lý được version conflict. Cách sửa: metadata `version`/`effective_date` khi index và ưu tiên bản mới nhất khi rerank, hoặc yêu cầu generation nêu rõ bản hiện hành khi contexts có nhiều phiên bản.

Giới hạn: một lượt chạy, 50 câu (adversarial chỉ 10); evaluator cùng model với generation (`gemini-3.5-flash-lite`) nên có thể thiên vị cách diễn đạt của chính nó; answer_relevancy dùng embedding bge-m3 local; 2 PDF scan không vào corpus. Không có extractive fallback.
