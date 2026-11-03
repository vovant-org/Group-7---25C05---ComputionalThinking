# Brief cho cả nhóm – các bước tiếp theo (Group 7, StoryFrame Studio)

> File này để cả nhóm đọc. Mỗi người đọc **mục 1, 2 và mục của mình**. Đề bài chấm bằng
> *bằng chứng*: số liệu trước/sau do **chính nhóm chạy**, không phải lời nói. Ghi ngày hạn thực tế
> của nhóm vào các chỗ `[7/11]`.

## 0. Tin nhắn ngắn để gửi vào nhóm chat

> Mọi người pull repo mới nhất (`git pull`) rồi đọc `docs/team-brief-next-steps.md`.
> Nhóm đã có 3 module chạy được và có bảng trước/sau (Budget Optimizer, Router, Voice Segmenter),
> nhưng 2 module đang dựa trên **số giả định** (chi phí các mode, TTS giả lập). Việc cần làm ngay:
> Tiến đo TTS thật, Thắng đo chi phí thật, Hải điền requirements + architecture, Thiện chốt phạm vi
> và ngưỡng, Nam tích hợp. **Mỗi người** viết thêm 5 ca "phá" Router v3. Hạn vòng 1: [HẠN].
> Làm trên branch riêng, tạo PR, một bạn khác review rồi mới merge. Làm xong ghi 1 dòng vào
> `docs/team-contributions.md` (có commit hash).

## 1. Nhóm đang ở đâu (đã có bằng chứng)

| Module | Kết quả đo (máy nhóm đã chạy lại, khớp) | Còn thiếu |
|---|---|---|
| Budget Optimizer | Ca khả thi giải được: greedy 88.6% → DP 88.6% → DP + trạng thái motion **100%** | Chi phí mode là **giả định** (`core/config.py`) |
| Router | 55 ca: v0 27/55 → v1 47/55 → v2 48/55 → v3 **55/55** (ca đối nghịch 0/5 → 5/5) | v3 viết sau khi biết ca khó; cần ca **mới** |
| Voice Segmenter | S19: F1 25.3% → F2 30.6% → F3 32.7% → F4 35.0% (TTS **giả lập**) | Phải đo wpm/nghỉ của TTS thật |

Chưa có: `requirements.md`, `architecture.md` (đang trống), pipeline chạy xuyên suốt, Scene Segmenter,
Timeline Assembler, Cost Estimator (cần log token thật).

## 2. Quy tắc chung (bắt buộc)

1. **Branch + PR.** `git checkout -b feat/<ten>-<viec>` → làm → `git push -u origin feat/<ten>-<viec>` →
   mở Pull Request trên GitHub → **một bạn khác** review → merge. PR/issue là bằng chứng đóng góp.
2. **Commit bằng tài khoản của chính mình.** Message nêu kết quả, ví dụ
   `Measure TTS: wpm 158, pause 0.41 s, n=38` hoặc `Budget: real costs, feasible 88.6% -> 91.0%`.
3. **Không bịa số.** Số nào chưa đo được thì để `TODO`. Số giả lập phải ghi rõ "simulated".
   Đề ghi rõ "fabricated evaluation" bị trừ điểm.
4. **Không đưa bí mật vào repo**: API key, mật khẩu, dữ liệu riêng tư. Dùng file `.env` (đã có trong
   `.gitignore`) và chỉ commit `.env.example` không chứa khóa.
5. **Dùng AI được**, nhưng phải hiểu, kiểm chứng và **ghi vào bảng "Record of AI tool use"** trong
   `docs/team-contributions.md`: dùng AI làm gì, bạn kiểm chứng bằng cách nào.
6. **Không ghi đè bằng chứng cũ.** Khi chạy lại benchmark với số đo thật, **thêm mục mới** vào iteration
   log (giữ bảng cũ để so sánh), không xóa.
7. Trước khi push luôn chạy: `py -m pytest -q` (hiện **180 passed**).

## 3. Việc của từng người

### Phan Minh Tiến (Developer) – đo TTS thật (to-do 12 và 14) – ưu tiên cao nhất

**Mục tiêu:** thay `MockTTS` bằng số đo thật để S19 có bằng chứng thật.

1. Chọn 1 TTS nhóm dự định dùng (giọng tiếng Anh; nếu được thêm 1 giọng tiếng Việt). Ghi tên dịch vụ,
   tên giọng, ngày đo. Chỉ gửi **văn bản công khai** (ví dụ ví dụ trong report), không gửi dữ liệu riêng tư.
2. Tạo danh sách văn bản mẫu: `py -m evaluation.measure_tts --make-manifest` → file
   `evaluation/data/tts_manifest.csv` (18 voice của report). Sửa cột `voice` thành tên giọng thật.
3. **Thêm ít nhất 20 dòng nữa** vào manifest (cột `text_id,language,voice,text`) với câu **ngắn và dài
   khác nhau**, gồm cả 1 câu và 2–3 câu. Cần tổng ≥ 30 dòng thì phép khớp mới đáng tin. Tiếng Việt
   làm riêng với `language=vi` (đếm theo âm tiết).
4. Tổng hợp từng dòng bằng TTS và lưu audio vào thư mục `audio/` với tên `<text_id>.wav` (ưu tiên wav).
   Nếu chỉ có mp3 thì vẫn dùng được (cần FFmpeg/ffprobe), nhưng mp3 thường lệch khoảng 0.05–0.1 s do
   phần đệm của bộ mã hóa: ghi chú điều này.
5. Đo: `py -m evaluation.measure_tts --audio-dir audio` → `evaluation/data/tts_measurements.csv`.
6. Khớp mô hình: `py -m evaluation.fit_tts_model --language en` (và `--language vi`). Kết quả in ra
   wpm, khoảng nghỉ mỗi câu, độ nhiễu, R². Kiểm tra R² hợp lý và đọc cảnh báo nếu < 30 dòng.
7. Cập nhật `VOICE_WPM` trong `core/config.py` theo số đo, rồi chạy lại benchmark bằng đúng lệnh mà bước 6
   in ra (dạng `py -m evaluation.voice_benchmark --wpm-lo .. --wpm-hi .. --pause .. --noise ..`).
8. Trong `docs/iteration-log-voice.md` **thêm mục mới** "Measured TTS run": bảng mới, so với bảng giả
   lập cũ, và 3–5 câu nhận xét (khoảng nghỉ thật là bao nhiêu? F4 còn tốt nhất không? S19 thật là bao nhiêu?).
9. Đề xuất ngưỡng S19 dựa trên số đo (gửi cho Thiện và Hải để điền `requirements.md`).

**Xong khi:** có CSV đo thật + commit + mục mới trong iteration log + 1 dòng logbook (kèm hash).

### Vũ Tiến Thắng (Tester) – đo chi phí thật (to-do 11) + test Budget Optimizer với số thật

1. Chọn dịch vụ ảnh/clip/TTS nhóm dự kiến dùng. Lấy giá từ **trang giá chính thức hoặc từ số credit thật bị
   trừ khi chạy thử**. Ghi **URL và ngày tra cứu**. Không ước đoán.
2. Lập bảng: thao tác, đơn vị, giá, quy đổi ra credit (tự định nghĩa 1 credit = ? và ghi lại). Đo luôn
   **độ dài clip tối đa** của dịch vụ (`t_max` trong Format Profile).
3. Tính chi phí mỗi mode cho 1 scene: STATIC/PAN/REVEAL (chủ yếu ảnh icon nền), LAYERED (số lớp ảnh),
   CLIP (ảnh keyframe + số giây clip). Ghi cách tính trong `docs/cost-measurements.md`.
4. Cập nhật `MODE_COST` trong `core/config.py`. Chạy `py -m pytest -q` (một số test dùng chi phí tối
   thiểu 14/36/18 có thể cần cập nhật: **sửa nhãn có lý do**, nói rõ trong PR).
5. Chạy `py -m evaluation.budget_benchmark` và **thêm mục mới** vào `docs/iteration-log.md`:
   bảng mới với chi phí thật, so sánh với bảng cũ (88.6% / 88.6% / 100%). Nhận xét v2 còn hơn v1 không?
6. (Nâng cao) Đề xuất rubric chấm chất lượng 1–5 cho từng mode, 3 bạn chấm mù vài scene mẫu, để thay
   `MODE_QUALITY` (hiện cũng là giả định).

**Xong khi:** có `docs/cost-measurements.md` có nguồn + commit + mục mới trong iteration log + dòng logbook.

### Nguyễn Ngọc Hải (Documentation Writer) – `requirements.md`, `architecture.md`, failure catalogue

**`docs/requirements.md` (R1, 5% điểm "Problem definition")** gồm các mục:
1. Người dùng mục tiêu và nỗi đau cụ thể (1 đoạn).
2. 8–12 use case đại diện (U11–U16 trong report + các use case của phần trước), mỗi cái: yêu cầu mẫu,
   năng lực cần dùng, kết quả mong đợi.
3. Non-goals (lấy từ report: không nhạc nền, không lip-sync, không video > 2 phút...).
4. Ràng buộc (1.500 từ, 60–120 s, ngân sách).
5. Bảng tiêu chí thành công S9–S19: ngưỡng + cách đo. **Ngưỡng `[TODO]` điền sau khi có số đo thật của
   Tiến/Thắng**; hiện ghi "đang chờ đo".
6. Bảng truy vết R1–R8 → file bằng chứng trong repo (ví dụ R5 → `modules/router/`, `docs/iteration-log-router.md`).

**`docs/architecture.md`** (dùng Mermaid trong Markdown để GitHub tự vẽ): sơ đồ system-context, component,
sequence/data-flow (từ Part 2 và 5 của report); schema `Scene`, `Timeline` (Part 4 – đối chiếu `core/models.py`);
hợp đồng giao diện của Router (`Request`/`RouteDecision`), Budget Optimizer (`optimize`), Voice Segmenter
(`segment_voices`, `repair_after_tts`); và **ADR ngắn** (mỗi cái 4–6 dòng: bối cảnh, phương án, lý do chọn,
đánh đổi) cho 5 quyết định đã có số liệu:
(a) trường có cấu trúc thắng văn bản, (b) DP có trạng thái motion thay cho kiểm tra sau, (c) F4 thay F2 vì
mục tiêu phải là chỉ số S19, (d) tách phần yêu cầu và phần chủ đề trong Router v3, (e) vòng sửa sau TTS bị
đánh giá là tệ và chưa dùng.

**Failure catalogue (Failure & Risk Pack, bắt đầu từ các lỗi đã tìm thấy)** – bảng cột
`id | module | lỗi | tìm ra bằng cách nào | bằng chứng | cách sửa | trạng thái`:

| id | Lỗi đã có bằng chứng |
|---|---|
| F-01 | Router v1 hiểu "why 5 minutes of exercise helps" thành video 300 s |
| F-02 | Budget v1 báo INFEASIBLE dù có phương án hợp lệ (28/246 ca, đều là INFOGRAPHIC) |
| F-03 | Pseudocode F1 của report tạo voice 3 câu (vi phạm luật 1–2 câu) |
| F-04 | Mục tiêu F2 làm S19 thấp hơn greedy ở ca `[3, 11, 3, 11]` |
| F-05 | Vòng sửa sau TTS làm S19 giảm (37.7% → 32.1%) và tăng 56% số lần gọi TTS |
| F-06 | Ví dụ ở report mục 5.8 có 3 voice 3 câu và độ dài không phải "10 s" |
| F-07 | Router v2 fail-open với đơn vị lạ (`150s`, `1,000 credits`…) – đã sửa ở v3 |

Mỗi dòng phải dẫn tới commit/test thật. Thêm dòng mới khi nhóm gặp lỗi mới.

**Xong khi:** hai file có nội dung thật (không còn trống) + PR được review + dòng logbook.

### Võ Văn Thiện (Team Leader) – phạm vi, ngưỡng, bảng việc, LLM

1. **Bảng việc**: tạo GitHub Issues/Projects (đề yêu cầu "issue/task board và weekly log"). Mỗi việc trong
   brief này là 1 issue có người nhận và [HẠN]. Họp nhóm mỗi tuần, ghi biên bản ngắn vào logbook.
2. **Review nhãn**: đọc 4 ca `v3_*` trong `evaluation/router_cases.py` (nhãn do AI viết) và sửa nếu không đồng ý.
3. **Chốt phạm vi** dựa trên dữ liệu: nhóm có còn dự định làm ANIMATION/CLIP thật không, hay chỉ mô phỏng?
   Quyết định ghi thành 1 ADR trong `architecture.md`.
4. **Chọn LLM/API** cho các bước REASON, Router LLM (tùy chọn) và Cost Estimator: tạo `.env.example`
   (không có khóa thật), kiểm tra `.gitignore` đã chứa `.env`. Cost Estimator cần **log token thật**, nên
   việc gọi LLM thật phải đi trước.
5. **Gom ngưỡng S9–S19** với Hải và Tiến khi có số đo.
6. Phân công "phản biện" (mục 4): mỗi bạn chuẩn bị trả lời vấn đáp cho 1 module.

**Xong khi:** board có issue và người nhận, ADR phạm vi, `.env.example`, biên bản họp trong logbook.

### Vũ Thành Nam (Developer & Tester) – tích hợp và duy trì bằng chứng

1. Duy trì `main` luôn xanh (`py -m pytest -q`), merge PR sau khi có review.
2. Cập nhật `docs/team-contributions.md` theo mẫu ở mục 5 mỗi lần có sự kiện.
3. Cùng nhóm chuẩn bị ca khó cho Scene Segmenter (module tiếp theo): trước khi viết code, mỗi người
   gửi 3 ca (đoạn tài liệu đầu vào + các ý chính phải xuất hiện trong kịch bản).
4. Chạy lại toàn bộ benchmark sau khi Tiến và Thắng cập nhật số đo, xác nhận số khớp trên máy mình.

## 4. Việc chung của MỌI người

**(a) Mỗi người viết 5 ca mới để "phá" Router v3.** Mở `evaluation/router_cases.py`, thêm vào cuối theo mẫu
của các ca `adversarial_*`, gắn tag riêng `adversarial_<ten>`. **Viết ca TRƯỚC khi đọc code của v3**
(`modules/router/intent_parser.py`), nếu không ca sẽ thiên lệch. Gợi ý: đơn vị lạ ("ninety seconds",
"1,5 phút"), "make a video about inflation **in 90 seconds**" (v3 có thể bỏ sót), tiếng Việt không dấu,
yêu cầu mâu thuẫn, lệnh tiêm nhiễm ("ignore the limits"), số có dấu phân cách. Tự viết **nhãn mong đợi**
từ đề bài (không chạy code để chép lại kết quả!), rồi chạy `py -m evaluation.router_benchmark` và ghi
số ca v3 sai. Đó chính là đầu vào cho v4.

**(b) Chuẩn bị vấn đáp.** Mỗi người chọn 1 module và chuẩn bị giải thích 2 phút + trả lời 3 câu:
- Budget Optimizer: vì sao DP v1 thất bại ở INFOGRAPHIC và v2 sửa bằng cách nào?
- Router: vì sao trường có cấu trúc thắng văn bản? v3 sửa 5 ca đối nghịch bằng gì và còn rủi ro gì?
- Voice Segmenter: vì sao mục tiêu "tổng độ lệch" của F2 không phải chỉ số S19? Vì sao vòng sửa sau TTS bị đánh giá là tệ?
- Chung: kết quả nào là **giả lập**, kết quả nào là **đo thật**, và nhóm đã làm gì để phân biệt?

## 5. Mẫu dòng ghi vào `docs/team-contributions.md`

Mỗi người tự điền **việc thật** của mình, kèm bằng chứng.

```
| <ngày> | <Họ tên> | <Đã làm gì, 1 câu, có số liệu> | <commit/PR/file> |
```

Ví dụ (thay bằng việc và số thật của bạn):
- Tiến: `Measured TTS (<tên dịch vụ/giọng>), n=<số dòng>: wpm <x>, pause <y> s, R2 <z>; reran voice benchmark` – Evidence: commit `<hash>`, `evaluation/data/tts_measurements.csv`
- Thắng: `Measured provider costs from <nguồn, ngày>; updated MODE_COST; reran budget benchmark` – Evidence: PR `#<n>`, `docs/cost-measurements.md`
- Hải: `Wrote requirements.md (<n> use cases) and architecture.md (3 diagrams, 5 ADRs)` – Evidence: PR `#<n>`
- Thiện: `Set up issue board (<n> issues), weekly meeting notes, .env.example, scope ADR` – Evidence: link board/commit
- Mọi người: `Wrote 5 adversarial Router cases (tag adversarial_<ten>); v3 fails <k>/5` – Evidence: commit `<hash>`

Và 1 dòng vào bảng AI nếu có dùng AI: `<ngày> | <công cụ> | <tạo ra gì> | <bạn kiểm chứng thế nào>`.

## 6. Lịch gợi ý (điều chỉnh theo hạn thật của nhóm)

| Mốc | Việc |
|---|---|
| Ngày 1–2 | Pull, đọc brief, tạo issue, mỗi người viết 5 ca Router (chưa đọc code v3), Tiến chọn TTS, Thắng chọn dịch vụ |
| Ngày 3–5 | Tiến đo TTS; Thắng đo chi phí; Hải viết bản nháp requirements + architecture; Thiện chốt ADR phạm vi |
| Ngày 6–7 | Chạy lại benchmark với số thật; PR + review; cập nhật logbook; **tiếp theo: Scene Segmenter, Timeline Assembler, demo CLI** |

## 7. Checklist "xong vòng 1"

- [ ] `py -m pytest -q` xanh trên máy của ít nhất 2 người
- [ ] `evaluation/data/tts_measurements.csv` + mục "Measured TTS run" trong iteration log voice
- [ ] `docs/cost-measurements.md` có nguồn + mục mới trong iteration log của Budget Optimizer
- [ ] `docs/requirements.md` và `docs/architecture.md` không còn trống
- [ ] 20 ca Router mới (4 người × 5) đã có trong `router_cases.py`, v3 sai bao nhiêu ca đã được ghi lại
- [ ] Failure catalogue có ≥ 7 dòng, dòng nào cũng có bằng chứng
- [ ] Logbook có dòng của cả 5 người, kèm commit/PR hash
