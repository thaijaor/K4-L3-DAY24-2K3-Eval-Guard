# Blueprint CI/CD cho RAG và guardrails

Nhóm: 2K3

Người phụ trách: Lê Duy Quân (MSSV: 2A202602731)

Đây là **đề xuất CI/CD**, không phải workflow đã được triển khai/chạy.
Nguồn kết quả: artifacts/ragas_50q.json, judge_results.json, guard_results.json.
Run timestamp: 2026-10-13T05:53:56.962214+00:00; guard models: gemini-3.5-flash-lite.
Models generation/evaluator/judge từ A/B: Generation: google/gemini-3.5-flash-lite (ragas_50q.json, judge_results.json); Evaluator: BAAI/bge-m3, google/gemini-3.5-flash-lite (ragas_50q.json); Judge: gemini-3.5-flash-lite (judge_results.json); Guard: gemini-3.5-flash-lite (guard_results.json).

## Kiến trúc và failure action

Input → Presidio → NeMo input → RAG → NeMo output → response.
Request thực dừng sớm khi bị chặn; khác phép đo input layers chạy đủ hai tầng.

Kiến trúc luồng xử lý và các nguyên tắc bảo vệ:
- Luồng dữ liệu (Data Flow):
  1. Input từ người dùng được chuyển tới tầng Presidio PII Scan (Layer 1): Quét regex/pattern xác định các trường dữ liệu cá nhân nhạy cảm (CCCD/CMND, SĐT Việt Nam, email, thẻ tín dụng). Nếu phát hiện vi phạm, hệ thống dừng sớm (short-circuit) và từ chối xử lý, không tiêu tốn token gọi LLM.
  2. Input an toàn ở Layer 1 được chuyển tiếp sang NeMo Input Rail (Layer 2 - `self check input`): LLM guardrail đối chiếu câu hỏi với chính sách công ty để phát hiện prompt injection, jailbreak, impersonation hoặc yêu cầu ngoài phạm vi HR/IT policy. Nếu vi phạm, hệ thống dừng ngay (`stop=True`) và trả thông điệp từ chối từ `refuse to respond`.
  3. Truy vấn hợp lệ chuyển tới RAG pipeline: Tìm kiếm context liên quan từ kho dữ liệu quy chế nội bộ và sinh câu trả lời dự kiến.
  4. Câu trả lời của LLM đi qua NeMo Output Rail (Layer 3 - `self check output`): Rà soát câu trả lời để ngăn ngừa rò rỉ dữ liệu cá nhân, lương cụ thể của từng cá nhân hoặc mật khẩu hệ thống.
  5. Trả phản hồi an toàn cho người dùng cuối.
- Failure Action & Short-circuit: Khi bất kỳ tầng guard nào phát hiện vi phạm, hệ thống dừng thực thi ngay lập tức và trả thông điệp từ chối an toàn, ngăn chặn rò rỉ stack trace hoặc dữ liệu context nội bộ.
- Redaction & Log: Mọi câu hỏi và câu trả lời ghi vào audit log phải được ẩn danh hóa thông qua Presidio anonymizer. Dữ liệu PII không bao giờ được ghi ra plain text log.
- Quản lý Secrets & Fallback: API keys được lưu trữ bảo mật qua Environment Variables / Vault, không commit vào repository hay in ra log. Trong trường hợp LLM API bị gián đoạn (HTTP 429, timeout), hệ thống kích hoạt circuit-breaker và trả về phản hồi fallback thông báo hệ thống bận thay vì dừng đột ngột.

## Phạm vi và số đo latency

Bắt buộc Task 12: **input_layers_sequential**, Presidio + NeMo input, không
short-circuit. Engines tạo trước đo; có hai warm-up thật không tính vào mẫu.
Percentile nội suy tuyến tính từ raw samples; tổng từ tổng từng sample.

Số mẫu timed: 20; warm-up: 2;
phương pháp: linear.

| Layer / scope | P50 ms | P95 ms | P99 ms | Tình trạng |
|---|---|---|---|---|
| Presidio | 24.60 | 34.29 | 37.72 | Đạt budget target (<50ms, regex/rule-based offline) |
| NeMo input | 791.24 | 1180.21 | 2322.00 | Vượt target 500ms (LLM self-check remote qua Internet) |
| Input guard sequential | 817.69 | 1204.49 | 2341.51 | Vượt target 500ms (tổng đo tuần tự cả hai tầng) |
| RAG | chưa đo | chưa đo | chưa đo | Ngoài phạm vi bắt buộc |
| NeMo output | chưa đo | chưa đo | chưa đo | Ngoài phạm vi bắt buộc |
| Full guard / short-circuit request | chưa đo | chưa đo | chưa đo | Không suy từ input_guard_ms |

Input-layer budget target: 500ms; kết quả thực tế/budget_ok: P95 = 1204.49ms / false.
Phân tích bottleneck và kế hoạch đo lường bổ sung:
- Điểm nghẽn độ trễ (Bottleneck): Tầng Presidio chạy nội bộ cực kỳ nhanh chóng (P95 chỉ 34.29ms), trong khi NeMo Input Rail gọi LLM remote qua mạng có P95 lên đến 1180.21ms (chiếm >97% tổng thời gian). Đây là đặc tính vốn có khi dựa vào API LLM bên ngoài cho từng request.
- Kế hoạch đo các phần ngoài phạm vi: Trong giai đoạn staging trước khi lên production, nhóm dự kiến mở rộng bài đo benchmarking: (1) Đo latency RAG retrieval + generation với 50 câu test set trong 5 lần lặp có warm-up; (2) Đo NeMo output rail trên tập câu trả lời đã sinh; (3) Đo end-to-end full guard với short-circuit thực tế nhằm phản ánh đúng thời gian phản hồi mà người dùng trải nghiệm khi bị chặn ở tầng đầu.

## CI gates đề xuất

- RAGAS faithfulness ≥0.75, avg_score ≥0.65 trên 50 câu.
- Attacks ≥18/20 cho CI đề xuất; clean 8/8 allowed; output cases đúng.
- Full guard P95 <500ms chỉ áp dụng sau khi thực sự đo full guard.

Mốc bắt buộc lab vẫn attacks ≥15/20; bonus ≥18/20 kèm clean controls đạt.
Đề xuất triển khai CI Gate Workflow (GitHub Actions / GitLab CI):
- Job thực thi kiểm chuẩn tự động:
  ```bash
  python -m pytest tests/ -q
  python scripts/run_experiments.py --phase a --live
  python scripts/run_experiments.py --phase b --live
  python scripts/run_experiments.py --phase c --live --latency-samples 20
  python scripts/check_lab.py
  ```
- Cơ chế trả mã lỗi: Runner kiểm tra các ngưỡng đảm bảo chất lượng, nếu vi phạm sẽ trả exit code khác 0 để dừng pipeline:
  - Phase A: RAGAS faithfulness >= 0.75 và avg_score >= 0.65 trên toàn bộ 50 câu hỏi.
  - Phase B: Cohen's kappa >= 0.60 so với nhãn chuyên gia human, position bias rate < 0.50.
  - Phase C: Tỷ lệ chặn tấn công >= 18/20 (bonus gate), tỷ lệ dương tính giả trên tập clean bằng 0.0 (8/8 clean allowed), và 4/4 kịch bản output rail đạt kỳ vọng an toàn.
- Lưu ý: Workflow trên hiện là đề xuất kiến trúc CI/CD hoàn chỉnh dựa trên bằng chứng đo lường thực tế của nhóm, chưa được kích hoạt tự động theo cron trên repository mà chạy thông qua CLI runner.

## Monitoring và cải tiến

Chiến lược giám sát production:
- Các chỉ số trọng yếu và ngưỡng cảnh báo:
  - Guard Block Rate: Cảnh báo qua PagerDuty/Slack nếu tỷ lệ chặn vượt quá 15% tổng request trong cửa sổ trượt 10 phút (dấu hiệu tấn công dò quét hoặc false positive hàng loạt).
  - Clean False Positive Rate: Thu thập phản hồi từ người dùng qua nút báo cáo "Câu trả lời bị từ chối sai"; ngưỡng cảnh báo nếu FPR ước lượng > 2%.
  - Input Guard Latency: Cảnh báo nếu P95 của input guard vượt quá 2000ms hoặc tỷ lệ timeout kết nối LLM API > 1%.
  - RAG Retrieval Drift: Chạy định kỳ hàng tuần 50 câu synthetic eval để giám sát faithfulness và context recall, cảnh báo nếu điểm trung bình suy giảm > 0.05.
- Phân định trách nhiệm: Kỹ sư Guardrail & Eval (Lê Duy Quân) phụ trách điều tra log chặn nhầm và tinh chỉnh rules/prompts; Tech Lead (Nguyễn Hồng Thái) phụ trách xử lý sự cố suy giảm chất lượng retrieval/generation.
- Giới hạn mẫu: Bộ dữ liệu 50/20/8/4 là tập chuẩn kiểm thử mẫu; môi trường thực tế cần được bổ sung liên tục các mẫu jailbreak mới và dữ liệu đối thoại thực tế.

RAGAS mean/worst distribution: Mean avg_score = 0.7735; worst distribution = multi_hop (mean avg_score = 0.6155, answer_relevancy = 0.3619).
Cohen’s κ: 1.0 (hoàn toàn tương đồng 10/10 nhãn so với chuyên gia human).
Attacks passed: 20/20; clean false_positive_rate: 0.0.
3–5 cải tiến có thể kiểm tra thực tế:
1. Triển khai mô hình phân loại an toàn chuyên biệt cỡ nhỏ (SLM như Llama-Guard-3-1B hoặc fast text-classifier local) thay thế LLM remote cho NeMo input rail, giúp kéo giảm P95 latency của input guard từ 1204.49ms xuống dưới 100ms.
2. Áp dụng kỹ thuật Query Decomposition và HyDE cho nhóm câu hỏi multi-hop để cải thiện chỉ số answer_relevancy (hiện tại chỉ đạt 0.3619) và nâng điểm trung bình của multi_hop từ 0.6155 lên trên 0.75.
3. Mở rộng bộ nhận diện Presidio với các custom regex cho mã số thuế cá nhân, số tài khoản ngân hàng nội địa và IP nội bộ, gia tăng tỷ lệ chặn sớm ở Layer 1 không tốn chi phí inference.
4. Tích hợp Semantic Cache (Redis + Qdrant embeddings) cho tầng input guardrail để tái sử dụng quyết định an toàn cho các câu hỏi phổ biến, tiết kiệm quota API và giảm độ trễ về <10ms cho 30% truy vấn lặp lại.
