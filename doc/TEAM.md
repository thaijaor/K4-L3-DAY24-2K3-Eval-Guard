# Nhóm thực hiện K4 Track 3B

Tên nhóm: 2K3

Repo chung: https://github.com/thaijaor/K4-L3-DAY24-2K3-Eval-Guard

Trưởng nhóm/người nộp: Nguyễn Hồng Thái — 2A202602894

Ngày lab/deadline áp dụng: {{Ngày giờ theo thông báo lớp}} — Asia/Ho_Chi_Minh (UTC+07:00)

Commit dùng để chấm: {{Commit SHA}}

Mỗi nhóm nộp một repo. Điền đủ thành viên và một mục INDIVIDUAL cho từng người.

## Thành viên và phân công

| STT | Họ và tên | MSSV | Vai trò / công việc thật | Bằng chứng |
|---|---|---|---|---|
| 1 | Nguyễn Hồng Thái | 2A202602894 | Setup + tích hợp pipeline (m1–m5 từ Day18, `config.py`, `scripts/setup_answers.py`), sinh answers; Phase A Tasks 1–4 (`src/phase_a_ragas.py`, adapter `src/m4_eval.py`), `failure_clusters.md` | Commits 0531a7e, f051cc8, 151ba55, 3c01d22; `artifacts/answers_50q.json`, `artifacts/ragas_50q.json`, `doc/reports/failure_clusters.md` |
| 2 | {{Họ tên}} | {{MSSV}} | {{Phase/file/hàm}} | {{Commit/PR/report}} |

Người tích hợp/chạy batch/nộp link: Nguyễn Hồng Thái — tích hợp m1–m5, chạy setup + Phase A live, chạy `check_lab.py` và nộp link.

## Môi trường và chuẩn bị trước lớp

OS/Python/compiler: Windows 11 (10.0.26200), Python 3.11.9, MSVC 14.44 (VS 2022 Build Tools, workload Desktop development with C++), Docker 29.8.0.
Virtualenv/dependencies/imports: `.venv` + `pip install -r requirements/requirements.txt -c requirements/constraints-core.txt`; annoy 1.17.3 và nemoguardrails 0.10.0 build/cài thành công; `pip check`: No broken requirements; `import ragas, nemoguardrails, presidio_analyzer, spacy` OK. Phải pin thêm `pyarrow<18` (bản mới đòi NumPy 2). Trên Windows torch phải import trước ragas/langchain (WinError 1114 c10.dll), đã xử lý trong m4.
Models/Qdrant/50 answers đã chuẩn bị: Qdrant `qdrant/qdrant:v1.9.7` (Docker), bge-m3 + bge-reranker-v2-m3 cache local, LLM Gemini `google/gemini-3.5-flash-lite` qua Vertex AI (endpoint OpenAI-compatible). `artifacts/answers_50q.json`: 50 câu 20/20/10, 50/50 `llm`, không fallback. 2 PDF scan trong `data/` không có text layer nên không vào corpus.

## INDIVIDUAL

### NguyenHongThai-2A202602894

- Phần được giao và phần thực tế đã làm: đưa m1–m5 từ bài Day18 của mình (repo `thaijaor/K4-Track3B-Day18-Production-RAG`, commit 286a1a6) vào `src/`; thêm `get_llm_client()` trong `config.py` cho Gemini/Vertex và cho support scripts dùng chung; sửa m2 dùng `client.search()` (qdrant-client <1.10), m4 trả `metadata.evaluator_models` và chấm lại câu NaN; sửa prompt generation để trả lời bằng câu hoàn chỉnh; implement Phase A Tasks 1–4; viết `failure_clusters.md`.
- Bằng chứng: commits 0531a7e, f051cc8, 151ba55, 3c01d22; `artifacts/answers_50q.json`, `artifacts/ragas_50q.json`, `doc/reports/failure_clusters.md`.
- Cách kiểm tra: `pytest tests/test_phase_a.py` (6 passed), `pytest -m support` (60 passed); live `python scripts/setup_answers.py --live` và `python scripts/run_experiments.py --phase a --live`; `python scripts/check_lab.py` → PASS answers_50q.json, Phase A artifact, failure_clusters.md.
- Điều đã học: bốn metric RAGAS đo bốn chỗ khác nhau (generation vs retrieval) nên phải đọc answer/contexts trước khi tin diagnosis tự động — bottom 10 bị gắn "hallucinating" nhưng thực chất là từ chối thừa ở câu multi_hop; nhóm yếu chọn theo mean, không theo số câu; điểm adversarial cao không chứng minh pipeline xử lý được bản chính sách cũ/mới.
- Giới hạn/cách xử lý: lần chạy đầu RAGAS trả faithfulness NaN cho answer cụt ("Có.", "Không tìm thấy.") → không điền điểm giả, sửa prompt generation và sinh lại answers; prompt mới làm tăng từ chối ở multi_hop (12/20), đã ghi trong report kèm hướng sửa. Evaluator trùng model với generation.
- Nguồn/AI hỗ trợ nếu có: Claude Code (Claude Opus 5.5) hỗ trợ cài môi trường, viết adapter/Phase A và nháp report; tôi kiểm tra bằng unit tests, chạy live, đối chiếu từng câu bottom 10 với `ragas_50q.json` và checker. Mã m1–m5 là bài Day18 của tôi.

{{Mục INDIVIDUAL của thành viên 2 — tự điền.}}

## Cập nhật sau khi nộp

{{Ghi phiên bản nộp; nếu sửa sau deadline, ghi commit/thời điểm/lý do và thông báo
coach cho phép áp dụng bản cập nhật. Nếu không có cập nhật, ghi rõ không có.}}
