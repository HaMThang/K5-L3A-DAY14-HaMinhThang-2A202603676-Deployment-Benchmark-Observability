# Benchmark & Observability Report — Day 14

**Tên:** Not supplied  
**Ngày chạy:** 2026-11-25  
**Môi trường:** Windows workspace with Docker Desktop/WSL2; local develop agent used Python 3.14.4, production observability stack used Docker Compose. Agent answers use the repository's mock LLM. The reproducible numeric outputs are under `reports/` and `benchmark-results/`.

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---:|---|
| p95 latency `/ask` | < 500 ms | Mục tiêu lab để phần lớn request trả lời trong nửa giây; các request tail chậm vẫn được theo dõi bằng p99/traces. |
| Error rate `/ask` | < 2% | Cho phép lỗi mock ngẫu nhiên hiếm gặp nhưng phát hiện được sự cố upstream rõ rệt. |
| Accuracy trên golden dataset | ≥ 80% | Quality gate được đặt trong `run_eval.py`; v1 được giữ làm baseline dù không đạt gate. |

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

Mỗi phép đo gửi 200 request; kết quả đầy đủ nằm trong các JSON được liên kết.

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---:|---:|---:|---:|---:|---:|---|
| 1 | 3.90 | 192.6 | 224.1 | 1699.6 | 1.50% | PASS |
| 10 | 40.88 | 189.3 | 221.3 | 1666.9 | 0.00% | PASS |
| 50 | 83.58 | 198.9 | 255.5 | 1714.7 | 1.50% | PASS |
| 100 | 79.84 | 329.6 | 969.7 | 1743.6 | 0.00% | FAIL (p95) |

**Nhận xét:** Throughput tăng từ concurrency 1 tới 50 nhưng không tăng tuyến tính; ở 100 nó giảm nhẹ trong lần đo này. Độ trễ mock LLM và tail khoảng 1.7 giây chiếm phần lớn thời gian, nên tăng số client đồng thời không làm upstream xử lý nhanh hơn. Ở concurrency 100, p95 vượt SLO 500 ms dù không có lỗi HTTP.

Evidence: [load_v2_c1.json](reports/load_v2_c1.json), [load_v2_c10.json](reports/load_v2_c10.json), [load_v2_c50.json](reports/load_v2_c50.json), [load_v2_c100.json](reports/load_v2_c100.json).

### 2.2 Tail latency

Mỗi cấu hình có 200 request, concurrency 20. `MOCK_SLOW_RATE` là biến duy nhất được thay đổi.

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---:|---:|---:|---:|
| 0 | 188.7 | 222.1 | 235.5 |
| 0.03 (mặc định) | 243.0 | 221.4 | 1703.6 |
| 0.1 | 332.0 | 1690.2 | 1705.5 |

**Nhận xét:** p95/p99 nhạy với request chậm hơn average. Ở rate 0.03, p95 vẫn thấp nhưng p99 đã lên 1.7 giây; ở rate 0.1, p95 cũng vượt SLO. Average có thể che khuất nhóm request chậm mà người dùng vẫn trải nghiệm, vì vậy không nên đặt SLO chỉ theo average.

Evidence: [tail_slow_0.json](reports/tail_slow_0.json), [tail_slow_003.json](reports/tail_slow_003.json), [tail_slow_01.json](reports/tail_slow_01.json).

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 sau khi sửa KB |
|---|---:|---:|---:|
| Accuracy | 4.35% (1/23) | 91.30% (21/23) | 100% (23/23) |
| Avg tokens / câu | 56.0 | 109.3 | 114.0 |
| Tổng cost (USD) | $0.000389 | $0.000764 | $0.000793 |
| Cost / câu đúng (USD) | $0.00038895 | $0.00003639 | $0.00003449 |
| Quality gate (accuracy ≥80%, không regression) | FAIL | PASS | PASS |

**Những câu v2 trả lời sai ban đầu và cách sửa:**

| ID | Keyword bị thiếu | Đã sửa |
|---|---|---|
| `security-02` | `token`, hết hạn, chữ ký | Bổ sung mục JWT giải thích token có chữ ký, claim `exp`, và phân biệt với API key trong `develop/utils/mock_llm.py`. |
| `scaling-03` | CPU, memory, custom metrics | Bổ sung mục Kubernetes HPA nêu CPU, memory, request/giây và queue length. |

**Trade-off:** v2 dùng gần gấp đôi token và có tổng cost cao hơn v1 vì trả lời đúng nhiều câu hơn. Nhưng chi phí trên mỗi câu đúng giảm khoảng 10.7 lần so với v1. Bản KB sửa tăng cost tổng khoảng 3.8% so với v2, đổi lại accuracy tăng từ 91.3% lên 100%; p95 eval tăng nhẹ từ 216.4 lên 225.0 ms.

Evidence: [eval_v1.json](reports/eval_v1.json), [eval_v2.json](reports/eval_v2.json), [eval_v2_fixed.json](reports/eval_v2_fixed.json).

## 4. Observability stack (production)

Docker Compose stack đã chạy local; `/health` của agent trả HTTP 200. Có thể xem Grafana tại `http://localhost:3000`, Jaeger tại `http://localhost:16686`, Prometheus tại `http://localhost:9090` và Locust tại `http://localhost:8089` khi stack còn chạy.

### 4.1 Screenshot và evidence

- [ ] Dashboard Grafana khi đang có tải (Golden Signals): chưa có ảnh xác thực. Headless capture tạo ảnh trống nên đã loại khỏi repo.
- [ ] Trace chậm trong Jaeger: dữ liệu trace thật đã lưu dạng JSON ở [jaeger_trace_summary.json](reports/jaeger_trace_summary.json); chưa có screenshot UI.
- [ ] Trace lỗi trong Jaeger với exception: có trace thật và exception trong JSON summary; chưa có screenshot UI.
- [ ] Trang Alerts Prometheus với alert firing: API snapshot từng ghi nhận alert cost `LLMCostBurnRateHigh` firing, nhưng trạng thái lần truy vấn sau là không có alert. Không có screenshot trang Alerts.

Snapshot alert đã quan sát: `LLMCostBurnRateHigh`, severity `warning`, value `$2.456278/hour`, `activeAt=2026-11-25T10:32:32.571501534Z`. Đây là alert chi phí, không phải bằng chứng alert lỗi A firing. Snapshot API kế tiếp trả danh sách alert rỗng. Xem [prometheus_alerts_firing_observed.json](reports/prometheus_alerts_firing_observed.json) và [prometheus_alerts.json](reports/prometheus_alerts.json).

### 4.2 Thí nghiệm “phá hệ thống”

| # | Thay đổi | Kết quả/alert thực tế | Thời gian tới firing | Panel phản ánh |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | Locust thu được 315 lỗi HTTP 503 trong 1,663 request `/ask` (18.94%). Không xác nhận được `AgentHighErrorRate` ở trạng thái firing; snapshot alert liên quan lỗi chưa được lưu khi injection đang chạy. | Chưa đo được | Chưa xác nhận |
| B | `MOCK_SLOW_RATE=0.3` | Chưa chạy thử nghiệm alert production này. | Chưa đo | Chưa xác nhận |
| C | `LLM_MODEL=mock-llm-large` | Chưa chạy thử nghiệm alert production này. | Chưa đo | Chưa xác nhận |
| D | `docker pause` một instance | Chưa chạy | Chưa đo | Chưa xác nhận |
| E | `AGENT_VERSION=v1` | Chưa chạy trong production stack | — | — |

Locust evidence cho A: [fault_error_stats.csv](benchmark-results/fault_error_stats.csv). Các phép Locust có lỗi trả exit code 1 vì nhận HTTP 503; đó là kết quả test, không phải lỗi khởi chạy Locust.

Thử nghiệm E nếu chạy cần được phát hiện bằng quality evaluation/canary so sánh accuracy và regression theo version; health/error/latency có thể vẫn bình thường nên chỉ dựa vào hạ tầng alert không đủ.

### 4.3 Debug bằng trace

Trace chậm nhất trong 100 trace trả về ở cửa sổ truy vấn `2026-11-25T10:20Z–10:45Z`:

- `trace_id`: `4dfaabb6c6d23580d8fa806d24df09f8`
- Tổng thời gian: 1720.43 ms
- Span lớn nhất: `chat mock-llm-small`, 1692.22 ms (~98.4% tổng thời gian)
- Log JSON tương ứng:

```json
{"ts":"2026-11-25T10:38:26.160098+00:00","level":"INFO","service":"observable-agent","instance":"479e3cd3d088","event":"llm_call","trace_id":"4dfaabb6c6d23580d8fa806d24df09f8","span_id":"edffe8ba8179dccc","request_id":"44dc84b91a5e","model":"mock-llm-small","agent_version":"v2","input_tokens":74,"output_tokens":37,"cost_usd":0.000033,"llm_ms":1692.4,"retrieved":true}
```

Trace lỗi có event `exception`: `c39840761302fa0188c175f6e1f691be`, tổng 118.49 ms; span `chat mock-llm-small` có exception và status code 2. Log cùng trace ghi `Upstream LLM error: 503 Service Unavailable (mock)`. Các trace/log đã truy vấn thật; JSON tóm tắt nằm tại [jaeger_trace_summary.json](reports/jaeger_trace_summary.json).

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

Các số sau lấy từ CSV Locust; p95/p99 là phần trăm của hàng `/ask`, failure rate tính trên request `/ask`.

| Số instance | RPS `/ask` | p50 (ms) | p95 (ms) | p99 (ms) | Failures `/ask` |
|---:|---:|---:|---:|---:|---:|
| 1 | 59.59 | 190 | 230 | 1700 | 74/7093 (1.04%) |
| 3 | 60.02 | 190 | 220 | 1700 | 85/7136 (1.19%) |

**Giải thích:** Scale từ 1 lên 3 instance chỉ cải thiện p95 khoảng 10 ms trong lần chạy này; RPS và p99 gần như không đổi. Với mock upstream có latency tail cố định khoảng 1.7 giây, nút thắt nằm ở upstream/độ trễ xử lý request hơn là số worker agent. Các lượt có một số lỗi mock 503, nên so sánh throughput giữa hai lượt cũng chịu ảnh hưởng của tính ngẫu nhiên.

Evidence: [scale_1_stats.csv](benchmark-results/scale_1_stats.csv), [scale_3_stats.csv](benchmark-results/scale_3_stats.csv).

## 6. Kết luận

1. Theo dõi p95/p99 giúp thấy tail latency mà average che khuất; concurrency 100 và `MOCK_SLOW_RATE=0.1` đã vi phạm SLO p95.
2. Retrieval/KB cải thiện quality gate rõ rệt: eval tăng từ 21/23 lên 23/23 sau khi bổ sung thông tin JWT và HPA.
3. Ba instance không giải quyết được latency tail do mock LLM; cần trace và metric theo dependency để tìm đúng bottleneck.

Nếu đưa agent lên production thật, nên bổ sung alert cho error budget burn, latency theo route/dependency, tỷ lệ timeout/retry, Redis health/latency, saturation CPU/memory, và canary accuracy/cost theo model/version.

## 7. Trạng thái triển khai và giới hạn evidence

Không có Railway/Render/Cloud Run public deployment trong phiên này; xem [DEPLOYMENT.md](DEPLOYMENT.md). Vì vậy không tồn tại URL public, dashboard deploy hay ảnh deployment thật. Các ảnh Grafana/Jaeger/Prometheus cũng chưa được chụp do công cụ capture UI trong môi trường này không khả dụng; report chỉ đính kèm số đo JSON/CSV và API evidence thực sự thu được.
