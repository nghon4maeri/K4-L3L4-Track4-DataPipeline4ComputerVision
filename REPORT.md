# REPORT — Lab Day 9

> Điền **bằng lời và số liệu của chính bạn** (lấy từ đầu ra của `scripts/lab.sh step ...` và từ `report/evidence/*.json`). Bài làm công khai trên GitHub; giảng viên đối chiếu với lịch sử commit và với bài của các bạn khác. Mỗi câu 3 đến 8 dòng là đủ.

| | |
|---|---|
| Họ và tên | Nguyen Nam |
| MSSV (đúng bằng `LAB_STUDENT_ID` trong `.env`) | 2A202602788 |
| GitHub | nghon4maeri |
| Trip dùng cho bài tập sập và chạy lại (xem GUIDE, bước 5) | trip-02086 |

## Kết quả cuối

- `dataset_version` của bạn: `79425da8f28e`  (khớp `report/evidence/run_summary.json`)
- Số khung hình train / val / test của bạn: **676 / 172 / 171** (tổng 1019)
- `report/verify.txt`: tạo bằng `python3 scripts/check_submission.py --save-verify` (phải có `27/27 checks passed`).
- Ảnh chụp trong `report/screenshots/`: `airflow_graph.png`, `minio_lake.png`, `metabase_dashboard.png`, và ảnh bài tập sập/chạy lại (log task đỏ thấy trip của bạn).

## Bước 1 · Bronze

### Câu 1
Nguồn A có cột `ts_utc` (chuỗi ISO UTC, ví dụ `2025-10-07T08:00:00.014Z`), `speed_mps` (m/s), `heading_deg`, `lat`/`lon`, `gas`/`brake` (0–1). Nguồn B có `timestamp_ms` (số nguyên epoch ms, `1759933801509`), `spd_kmh` (km/h, `55.11`), `hdg`, `latitude`/`longitude`, `throttle_pct`/`brake_pct` (%). Ít nhất 4 khác biệt: (1) tên cột khác nhau, (2) đơn vị tốc độ khác (m/s vs km/h), (3) kiểu timestamp khác (chuỗi ISO vs epoch ms), (4) đồng hồ B lệch video 1500 ms (khai báo trong `sources.json`). Pipeline giữ mỗi nguồn một bảng bronze và để mọi cột ở dạng chữ: bronze là tầng **ghi nguyên bản, chỉ thêm** (append-only) — nếu ép kiểu sai hay gộp sai, dữ liệu gốc đã bị hỏng và không cách nào quay lại (slide 14). Ép kiểu/unit là việc của silver, nơi có test và lineage.

## Bước 2 · Silver telemetry

### Câu 2
Staging model `stg_telemetry_b.sql` đổi tên cột về chung (`ts_utc`, `speed_mps`...), chia tốc độ cho 3.6 để về m/s, chuyển epoch ms sang timestamp UTC, và **trừ 1500 ms** độ lệch đồng hồ khai báo trong `sources.json`. Bằng chứng: mẫu đầu của B trong silver là `2025-10-08 14:30:00.009` khớp thời điểm bắt đầu video (`14:30:00`). Bảng quarantine của tôi (từng lý do, từng drive):

| drive | duplicate | speed_missing | speed_out_of_range | tổng cách ly | sạch | tổng nhận |
|---|---|---|---|---|---|---|
| drive_a | 20 | 30 | 3 | 53 | 2968 | 3021 |
| drive_b | 20 | 30 | 3 | 53 | 3181 | 3234 |

Dòng lỗi vào `rejects` thay vì bị xoá: xoá im lặng làm mất dấu vết, không debug được nguồn lỗi, và không tái xử lý được khi luật thay đổi. Giữ trong rejects cho phép sửa luật rồi "replay" — đúng tinh thần medallion.

### Câu 3
Test `in_range` (tốc độ 0–70 m/s) là `error` vì tốc độ vô lý **làm hỏng dữ liệu huấn luyện** — không thể tin model huấn luyện trên dữ liệu sai. Test `max_gap_ms` là `warn` vì gap cảm biến là hiện tượng vận hành thật (mất tín hiệu tạm thời), cần cảnh báo để theo dõi chứ không nên dừng pipeline. Thí nghiệm `break-gate`: nới `max_speed_mps` từ 70 lên 1000, `dbt test` báo **PASS=5 WARN=1 ERROR=1** — test `in_range_silver_telemetry_speed_mps__70__0` bắt được **6 dòng**. Khôi phục luật gốc: **PASS=6 WARN=1 ERROR=0**. Điều này cho thấy cổng chất lượng (`error`) thực sự chặn dữ liệu xấu đi tiếp: khi test fail, các task downstream (gold, warehouse) không chạy — đúng thiết kế "bad data stops the pipeline".

## Bước 3 · Silver frames

### Câu 4
Từ `idempotency.json`: trước **1246 dòng**, hai lần chạy lại cùng partition `trip-00003` vẫn **1246 dòng**, dấu vân tay `6c7480dfde7e` **không đổi** (Δ rows=0). Ngược lại, ghi kiểu `append` sai: 1 trip có 60 khung → sau hai lần chạy thành **120 dòng** (nhân đôi 2x). Delta `overwrite` theo predicate `trip_id` an toàn hơn xoá-rồi-vì-ghi-lại vì: (1) Delta là transactional — nếu crash giữa chừng, commit trước đó vẫn nguyên vẹn, bảng không bao giờ ở trạng thái "nửa vời"; (2) không cần bước xoá riêng, tránh được cửa sổ lỗi giữa xoá và ghi; (3) time travel giữ lại lịch sử, đối chiếu được.

### Câu 5
Khung **đen** (`is_black`) là ảnh gần hoàn toàn tối — tín hiệu hỏng (che ống kính, mất frame), bị **loại khỏi gold**. Khung **tối** (`is_dark`, đường hầm/bóng râm) vẫn chứa nội dung cảnh có nghĩa, chỉ **gắn cờ nhưng giữ lại** (`toi_giu_lai`). Số liệu: drive_a có 6 đen / 4 tối-giữ; drive_b có 4 đen / **61 tối-giữ** (nhiều đoạn tối hơn). Tôi đồng ý: loại đen là đúng (dữ liệu rác), giữ tối là đúng (huấn luyện trên ánh sáng kém giúp model robust).

| dHash khác tối đa | số khung trùng, drive A | số khung trùng, drive B |
|---|---|---|
| 0 | 61 | 8 |
| 2 | 149 | 53 |
| 6 | 363 | 244 |

Tôi chọn ngưỡng **2** (ngưỡng pipeline đang dùng). Ngưỡng 0 quá chặt (bỏ sót khung gần-trùng), ngưỡng 6 quá lỏng (loại cả khung khác thật). Ngưỡng phụ thuộc tốc độ: xe chậm thì khung liền nhau gần như giống hệt (dHash khác 0 bit vẫn nhiều), xe nhanh thì khung đổi nhanh — nên ngưỡng cố định luôn là sự đánh đổi; cách lý tưởng là ngưỡng thích nghi theo tốc độ (ví dụ `threshold = f(speed)`).

## Bước 4 · Gold

### Câu 6
Từ `leakage.json`: chia **theo khung hình** (ngẫu nhiên 70/15/15) → **26 trip bị chia cắt**, và **26 trip có khung ở cả train lẫn test** (100%). Chia **theo trip** (gold): **0 trip** bị chia cắt. Khung liền nhau trong cùng trip gần như giống hệt (camera đứng hình, xe chậm). Nếu model thấy 1 khung của trip X ở train và khung X+1 ở test, nó "đã thấy đề thi" — điểm test đẹp **giả tạo**, không phản ánh khả năng khái quát sang trip/cảnh mới. Chia theo trip强迫 model học khái quát thật.

### Câu 7
`dataset_version` là **băm nội dung** (`sha256(frame_id|split)` cắt 12 ký tự) chứ không phải ngày giờ/số đếm vì: nội dung đổi thì version đổi, nội dung giữ thì version giữ — bất biến thời gian và môi trường, đối chiếu được giữa máy khác nhau. Hai lần chạy liên tiếp cho **cùng version** `79425da8f28e` (không phụ thuộc giờ chạy). `dataset_version` của tôi khác bạn bè vì MSSV được **trộn vào cách xếp trip**: `row_number() over (order by md5(trip_id || LAB_STUDENT_ID))` — đổi `LAB_STUDENT_ID` → thứ tự trip đổi → phân bổ split đổi → nội dung dataset đổi → version đổi. Cùng dữ liệu gốc, mỗi người một split hợp lệ riêng.

### Câu 8
Phần `lineage` trong `manifest.json` của tôi:
```
bronze.raw_telemetry_a: v0, bronze.raw_telemetry_b: v0, bronze.trips_raw: v0, bronze.video_files: v1
silver.frames: v25, silver.telemetry: v0, silver.frames_flagged: v0, silver.frame_telemetry: v0
input_video_sha256: drive_a=636ba1a9..., drive_b=bfa62703...
```
Dataset này được tạo từ: bảng bronze telemetry A/B (version 0), bảng trips (v0), bảng video_files (v1 — có sha256), và các bảng silver (frames ở version 25, các bảng khác version 0). Video đầu vào được xác định bằng sha256. Nếu người hỏi 3 tháng sau: họ cần (1) time-travel đến đúng version của từng bảng Delta (`deltalake` cho phép đọc version cũ), (2) đúng file video theo sha256, (3) `dataset_version` `79425da8f28e` để đối chiếu — mọi thứ cần để tái tạo đều nằm trong manifest.

## Bước 5 · Điều phối và phục vụ

### Câu 9
Trip của tôi (`trip-02086`, tính từ `md5("2A202602788") % 26 = 3` → trips[3]) được đặt vào `LAB_FAIL_ONCE`. Khi trigger DAG: đúng **1 task** `silver_frames` (map_index=3) chuyển **đỏ** (log: `simulated crash while extracting trip-02086`), và **7 task** chuyển `upstream_failed` (dbt_run_silver, dbt_test_silver, dbt_run_gold, dbt_test_gold, publish_lake, export_dataset, publish_warehouse). Tôi clear **chỉ task đỏ đó** (kèm downstream chạy lại), DAG chuyển xanh trong ~1 phút. Dữ liệu **không nhân đôi** vì `extract` ghi Delta `overwrite` theo partition trip. `dataset_version` **không đổi**: `79425da8f28e`. Bằng chứng: log task đỏ lưu tại `report/evidence/failed_task_log.txt` (thấy trip-02086), và `scripts/lab.sh verify` vẫn **27/27** sau khi chạy lại.

### Câu 10
Nâng lên 500 xe/ngày, ba thành phần vỡ trước:
1. **Airflow LocalExecutor + `max_active_tis_per_dagrun=1`** (slide 26): một DAG run xử lý tuần tự từng trip — 500 xe × nhiều trip sẽ không chạy kịp. Thay bằng **KubernetesExecutor / CeleryExecutor** với worker scale theo số partition, hoặc chuyển sang Spark/Ray cho xử lý video song song hàng nghìn partition.
2. **DuckDB local file + dbt đơn luồng** (slide 22): một file `.duckdb` trên một máy không phục vụ được 500 luồng ghi đồng thời. Thay bằng warehouse thực sự (BigQuery/Snowflake/ClickHouse) hoặc Lakehouse query engine (Trino/Databricks SQL).
3. **Decode FFmpeg từng trip** (slide 24): nút cổ chai CPU-bound. Thay bằng worker pool chuyên biệt (GPU decode, hoặc sample khung server-side ngay khi ingest thay vì decode lại mỗi lần).

## Câu hỏi riêng của bạn trên Metabase

Câu SQL tôi thêm (card 47):
```sql
select t.trip_id, t.drive_id, t.frames, t.frames_kept, t.lighting, t.conditions,
       round(100.0 * (t.frames - t.frames_kept) / t.frames, 1) as drop_pct
from marts.mart_trip_summary t order by drop_pct desc limit 10
```
Kết quả top 5: trip-04622 (56.7%), trip-03904 (50.0%), **trip-02086 (46.7%)** — chính là trip của tôi, trip-08888 (40.0%), trip-07774 (38.2%). Điều câu hỏi cho biết: các trip bị loại khung nhiều nhất đều thuộc **drive_a**, và chủ yếu do **khung trùng (near_dup)** — drive_a có camera đứng hình 6 giây và xe chạy chậm nên nhiều khung gần giống nhau. Trip có tỷ lệ loại cao nhất (trip-04622, 34/60 khung bị loại) nên được xem lại chất lượng camera/ghi hình.

## Nhìn lại

Điều bất ngờ nhất: pipeline dựng sẵn chạy trơn tru, nhưng **môi trường Windows gây rắc rối thật** — script shell (.sh) và entrypoint bị CRLF line endings khiến Docker container Linux không chạy được (`exec /airflow-entrypoint.sh: no such file or directory`); phải convert toàn bộ sang LF. Điều còn chưa rõ: vì sao `max_gap_ms` p50 của drive_b (81 ms) lớn gấp 4 lần drive_a (18 ms) — có thể do đồng hồ B vẫn còn jitter sau khi trừ offset trung bình. Lỗi dữ liệu pipeline **chưa bắt được**: frame có `sync_gap_ms` lên tới 2884–3112 ms nhưng vẫn `sync_ok=true` — nếu ngưỡng sync quá lỏng, khung có thể nối nhầm telemetry của giây khác; nên chốt một ngưỡng sync_gap tối đa cứng (error) thay vì chỉ cảnh báo.
