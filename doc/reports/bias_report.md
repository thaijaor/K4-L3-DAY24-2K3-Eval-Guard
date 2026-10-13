# Đánh giá LLM Judge Phase B

Nhóm: 2K3

Người phụ trách: Lê Duy Quân — 2A202602731

Nguồn: `artifacts/judge_results.json`; run timestamp: 2026-10-13T05:24:12.734185+00:00.
Models generation/judge: generation=`google/gemini-3.5-flash-lite`, judge=`gemini-3.5-flash-lite`.

## Năm cặp A/B và hai lượt

Nguồn cố định: A từ artifacts/answers_50q.json:answer; B từ fixtures/human_labels_10q.json:model_answer; reference từ fixtures/test_set_50q.json:ground_truth.
Ids: 1, 5, 12, 21, 41. Không đổi nguồn sau khi xem kết quả judge.

| ID | Câu hỏi | Pass 1 Winner (A/B) | Pass 2 Winner (quy về A/B) | Final Winner | Nhất quán vị trí | Điểm Pass 1 (A/B) | Điểm Pass 2 (A/B) |
|---|---|---|---|---|---|---|---|
| 1 | Nhân viên được nghỉ bao nhiêu ngày khi kết hôn? | A | A | A | Có | A: 1.0, B: 0.8 | A: 1.0, B: 0.8 |
| 5 | Muốn mua thiết bị trị giá 55 triệu cần ai phê duyệt? | A | A | A | Có | A: 1.0, B: 0.0 | A: 1.0, B: 0.0 |
| 12 | Thưởng Tết tối thiểu cho nhân viên chính thức có từ 6 tháng trở lên là bao nhiêu? | A | B | tie | Không | A: 1.0, B: 0.5 | A: 0.9, B: 1.0 |
| 21 | Một nhân viên Senior có 9 năm thâm niên được nghỉ bao nhiêu ngày phép năm và lương trong khoảng nào? | B | B | B | Có | A: 0.6, B: 1.0 | A: 0.5, B: 1.0 |
| 41 | Nhân viên được nghỉ bao nhiêu ngày phép năm? | A | B | tie | Không | A: 0.8, B: 0.2 | A: 0.6, B: 0.3 |

Position bias count/rate: 2 / 5 (40.0%).
Verbosity win rate: 66.7% (2 / 3); decisive cases: 3 (ID 1, ID 5, ID 21).

### Phân tích chi tiết các ca đánh giá

1. **Ca nhất quán (ID 1, 5, 21):**
   - **ID 1:** Cả hai pass đều chấm Answer A thắng (score 1.0 vs 0.8). Lý do: Answer A trích dẫn chính xác và đầy đủ chi tiết quan trọng "không bị trừ vào phép năm" khớp với reference, trong khi Answer B chỉ nói 3 ngày làm việc có lương. Ở đây Answer A dài hơn B, nhưng chiến thắng hoàn toàn dựa trên tiêu chí Completeness & Accuracy theo reference, không phải vì độ dài thuần túy.
   - **ID 5:** Cả hai pass đều chấm Answer A thắng tuyệt đối (score 1.0 vs 0.0). Lý do: Answer A nêu đúng thẩm quyền phê duyệt cho đơn trên 50 triệu là Tổng Giám đốc (CEO), trong khi Answer B nêu sai thành Giám đốc phòng ban. Đây là khác biệt bản chất về Factual Accuracy.
   - **ID 21:** Cả hai pass đều chấm Answer B thắng (score 1.0 vs 0.5-0.6). Lý do: Answer A bị lỗi retrieval nên tuyên bố "Không tìm thấy thông tin về lương", trong khi Answer B trả lời trọn vẹn cả 2 vế (18 ngày phép và khung lương Senior 20-35 triệu). Dù Answer A dài hơn một chút, Answer B ngắn hơn và đầy đủ thông tin hơn vẫn chiến thắng thuyết phục, chứng minh judge không bị chi phối hoàn toàn bởi verbosity bias khi có sự chênh lệch rõ rệt về độ đầy đủ.

2. **Ca không nhất quán vị trí (ID 12, 41):**
   - **ID 12:** Ở Pass 1 (A trước, B sau), judge chọn A vì A nêu chi tiết các điều kiện (từ 6 tháng trở lên). Ở Pass 2 (B trước, A sau), judge chọn B vì đánh giá B súc tích, đi thẳng vào câu hỏi, còn A đưa thông tin siêu dữ liệu (tên file thuong_tet.md và phiên bản 2.0). Sự dao động này dẫn đến kết quả hòa (`tie`) sau khi swap-and-average, phản ánh đúng bản chất: cả hai câu trả lời đều đúng về mặt cốt lõi (1 tháng lương) nhưng khác nhau về phong cách trình bày.
   - **ID 41:** Đây là câu hỏi bẫy phiên bản chính sách cũ/mới (v2023: 12 ngày vs v2024: 15 ngày). Answer A đưa cả hai bản (15 ngày theo v2024 và 12 ngày theo v2023), còn Answer B chỉ đưa thông tin cũ (12 ngày). Ở Pass 1, judge ưu tiên A vì có thông tin v2024 (15 ngày). Ở Pass 2, judge bối rối vì A đưa cả thông tin cũ lẫn mới, trong khi B đưa ngắn gọn (dù sai phiên bản). Swap-and-average đã quy về `tie`, loại bỏ sự phán đoán thiếu nhất quán của LLM trước câu hỏi đa phiên bản.

3. **Về Verbosity Bias:**
   - Trong 3 case decisive (thắng thua dứt khoát), có 2 case answer dài hơn thắng (ID 1 và ID 5), đạt tỷ lệ 66.7%. Tuy nhiên, khi phân tích nội dung, ID 1 thắng do có thêm chi tiết chính sách cốt lõi, ID 5 thắng do đối thủ trả lời sai người duyệt. Ở ID 21, câu trả lời ngắn hơn (Answer B) vẫn thắng câu trả lời dài hơn (Answer A). Như vậy, hiện tượng answer dài thắng chủ yếu do answer dài chứa nhiều thông tin chính xác theo reference hơn, chứ không phải do mô hình thiên vị số lượng từ thuần túy.

## Calibration đúng model_answer

Helper đánh giá đúng question/model_answer đang có trong fixtures/human_labels_10q.json; không lấy answer mới của pipeline. Prompt chỉ nhận question, answer, reference. Không gửi human_label, human_note hoặc phân bố nhãn human vào prompt.

| STT | Question ID | Model Answer đánh giá | Judge Label | Human Label | Trùng khớp | Lý do từ LLM Judge |
|---|---|---|---|---|---|---|
| 1 | 1 | Nhân viên được nghỉ 3 ngày làm việc có lương khi kết hôn. | 1 | 1 | Trùng | Nêu đúng số ngày nghỉ (3 ngày làm việc có lương khi kết hôn) theo reference, không bỏ sót ý thiết yếu. |
| 2 | 5 | Cần Giám đốc phòng ban phê duyệt. | 0 | 0 | Trùng | Sai thẩm quyền phê duyệt: theo reference, đơn hàng trên 50 triệu cần Tổng Giám đốc (CEO) phê duyệt. |
| 3 | 12 | Nhân viên được thưởng Tết tối thiểu 1 tháng lương. | 1 | 1 | Trùng | Trả lời chính xác và đầy đủ ý thiết yếu theo reference (thưởng Tết tối thiểu 1 tháng lương). |
| 4 | 21 | Được nghỉ 18 ngày phép (15 cơ bản + 3 thâm niên). Lương Senior từ 20 đến 35 triệu. | 1 | 1 | Trùng | Đáp ứng chính xác cả số ngày phép (18 ngày) và khoảng lương (20-35 triệu) theo reference chính sách v2024. |
| 5 | 23 | Hoàn trả 25 triệu vì chưa đủ 1 năm cam kết. | 1 | 1 | Trùng | Chính xác theo reference về số tiền hoàn trả (25 triệu) và lý do (nghỉ việc sau 8 tháng, chưa đủ 1 năm cam kết). |
| 6 | 29 | Trưởng phòng phê duyệt. Phạt 2% tháng trên 8 triệu. | 0 | 0 | Trùng | Thiếu người phê duyệt (Kế toán trưởng) và tính sai mức phí phạt quá hạn (chỉ phạt 80.000 VNĐ cho 15 ngày). |
| 7 | 33 | Phép: 19 ngày. Phụ cấp: 1.500.000 VNĐ/tháng. | 1 | 1 | Trùng | Nêu chính xác số ngày phép là 19 ngày và tổng phụ cấp hàng tháng 1.500.000 VNĐ theo reference. |
| 8 | 41 | Nhân viên được nghỉ 12 ngày phép năm. | 0 | 0 | Trùng | Sai phiên bản: sử dụng thông tin chính sách cũ (v2023 là 12 ngày) thay vì chính sách hiện hành v2024 (15 ngày cơ bản). |
| 9 | 46 | Nhân viên thử việc không được nghỉ phép năm và phải xin nghỉ không lương nếu cần. | 1 | 1 | Trùng | Phản ánh chính xác reference: nhân viên thử việc không có phép năm và phải xin nghỉ không lương. |
| 10 | 50 | Được, miễn là đảm bảo kết nối an toàn. | 0 | 0 | Trùng | Vi phạm chính sách bảo mật: reference cấm VPN cá nhân và bắt buộc dùng VPN công ty, nhưng answer lại cho phép. |

Cohen’s κ: 1.0 (Hoàn hảo — Perfect Agreement theo thang Landis-Koch).

### Phép tính Observed / Chance Agreement và diễn giải:

- Tổng số mẫu hiệu chuẩn: $N = 10$.
- Số trường hợp Judge và Human đồng thuận: $10 / 10 \rightarrow P_o = 1.0$ (Observed Agreement = 100%).
- Phân bố nhãn của Human: 6 nhãn 1 (60%), 4 nhãn 0 (40%).
- Phân bố nhãn của Judge: 6 nhãn 1 (60%), 4 nhãn 0 (40%).
- Xác suất đồng thuận ngẫu nhiên (Chance Agreement):
  $$P_e = (P_{\text{judge}=1} \times P_{\text{human}=1}) + (P_{\text{judge}=0} \times P_{\text{human}=0}) = (0.6 \times 0.6) + (0.4 \times 0.4) = 0.36 + 0.16 = 0.52$$
- Hệ số Cohen's $\kappa$:
  $$\kappa = \frac{P_o - P_e}{1 - P_e} = \frac{1.0 - 0.52}{1.0 - 0.52} = \frac{0.48}{0.48} = 1.0$$
- **Nhận xét:** Judge đạt sự tương đồng tuyệt đối 10/10 với nhãn chuyên gia con người trên cả các câu hỏi chính xác (nhãn 1), câu hỏi thiếu sót điều kiện (nhãn 0), câu hỏi sai thẩm quyền (ID 5), câu hỏi sai công thức phạt (ID 29), câu hỏi dính bẫy phiên bản cũ (ID 41), và câu hỏi vi phạm an toàn thông tin (ID 50). Điều này cho thấy prompt đánh giá nhị phân với tiêu chí nghiêm ngặt về version và điều kiện hoạt động rất hiệu quả.

## Giới hạn và cách dùng judge

1. **Giới hạn cỡ mẫu:**
   - Tập calibration gồm 10 câu hỏi và tập pairwise gồm 5 cặp câu hỏi là mẫu kiểm thử đại diện (smoke validation), chưa đủ lớn về mặt thống kê để ngoại suy độ tin cậy cho toàn bộ hệ thống trong môi trường Production lớn.
   - Khi triển khai thực tế, cần duy trì tập benchmark calibration tối thiểu 100-200 câu với đa dạng phân bố (factual, multi-hop, adversarial).

2. **Hiện tượng Position Bias và giải pháp bắt buộc:**
   - Thực nghiệm cho thấy Position Bias Rate đạt 40.0% (2/5 cặp đổi kết quả khi hoán đổi thứ tự A và B).
   - Nếu chỉ gọi pairwise judge 1 lần, kết quả sẽ bị chi phối đáng kể bởi vị trí hiển thị (answer đứng trước thường có lợi thế tiếp nhận ngữ cảnh). Kỹ thuật `swap-and-average` là **bắt buộc** trong pipeline đánh giá để lọc bỏ các phán đoán thiếu nhất quán và đưa về kết quả hòa (`tie`).

3. **Nguyên tắc sử dụng LLM Judge trong hệ thống:**
   - LLM Judge không được xem là đáp án tuyệt đối thay thế con người. Judge đóng vai trò là tầng lọc tự động (automated triage) giúp phát hiện nhanh các câu trả lời sai lệch nghiêm trọng.
   - Cần thường xuyên audit ngẫu nhiên 5-10% kết quả của Judge bằng Human Reviewers, đặc biệt là các ca Judge chấm điểm trung gian (score từ 0.4 đến 0.7) hoặc các ca `swap-and-average` trả về `tie`.
