# Benchmark & Observability Report — Day 14

**Họ tên:** Chưa cung cấp
**Ngày chạy:** 2026-11-25
**Môi trường:** Windows với Docker Desktop/WSL2; Docker Compose project `k5-day14-observability`; agent dùng mock LLM. Các phép đo và snapshot được giữ trong `reports/` và `benchmark-results/`.

## 1. SLO của agent

| SLI | SLO | Lý do |
|---|---:|---|
| p95 latency `/ask` | < 500 ms | Mục tiêu lab để phần lớn request trả lời dưới nửa giây; tail latency được theo dõi thêm qua p99 và trace. |
| Error rate `/ask` | < 2% | Cho phép lỗi mock hiếm gặp nhưng vẫn phát hiện được lỗi tăng bất thường. |
| Accuracy golden dataset | ≥ 80% | Quality gate tối thiểu để tránh deploy agent trả lời sai nhiều. |

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2, 300 request mỗi lượt)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---:|---:|---:|---:|---:|---:|---|
| 1 | 3.84 | 194.3 | 225.3 | 1699.3 | 1.67% | PASS |
| 10 | 36.73 | 192.2 | 226.9 | 1692.3 | 1.33% | PASS |
| 50 | 109.08 | 205.4 | 305.3 | 1707.4 | 1.00% | PASS |
| 100 | 62.41 | 356.4 | 2739.2 | 3043.2 | 0.33% | FAIL (p95) |

**Nhận xét:** throughput không tăng tuyến tính. Ở concurrency 50 có throughput cao nhất trong lượt đo; tại 100, queueing và tail latency làm RPS giảm và p95 vượt SLO. p99 quanh 1.7 giây ở các mức thấp hơn do mock LLM có một nhóm request chậm.

Evidence: [c1](reports/load_v2_c1.json), [c10](reports/load_v2_c10.json), [c50](reports/load_v2_c50.json), [c100](reports/load_v2_c100.json).

### 2.2 Tail latency (300 request mỗi lượt)

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) | Error rate |
|---:|---:|---:|---:|---:|
| 0 | 190.2 | 217.6 | 221.4 | 0% |
| 0.03 (mặc định) | 226.4 | 222.4 | 1678.0 | 0.67% |
| 0.1 | 335.4 | 1695.9 | 1718.3 | 1.00% |

Ở rate 0.03, p99 nhạy với nhóm request chậm dù p95 còn thấp. Ở rate 0.1, p95 cũng tăng mạnh. Average có thể che khuất trải nghiệm của nhóm request chậm nên không đủ để đặt SLO.

Evidence: [slow 0](reports/load_v2_slow_0.json), [slow 0.03](reports/load_v2_slow_0.03.json), [slow 0.1](reports/load_v2_slow_0.1.json).

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 sau khi sửa KB |
|---|---:|---:|---:|
| Accuracy | 4.35% (1/23) | 91.30% (21/23) | 100% (23/23) |
| Avg tokens / câu | 56.0 | 109.3 | 114.0 |
| Tổng cost (USD) | $0.000389 | $0.000764 | $0.000793 |
| Cost / câu đúng (USD) | $0.00038895 | $0.00003639 | $0.00003449 |
| Quality gate (≥80%) | FAIL | PASS | PASS |

Hai lỗi của v2 là `security-02` (JWT, claim `exp`/chữ ký) và `scaling-03` (CPU, memory, custom metrics cho HPA). Nội dung kiến thức tương ứng được bổ sung trong `develop/utils/mock_llm.py`. V2 dùng nhiều token hơn nhưng chi phí trên câu trả lời đúng thấp hơn nhờ accuracy tăng; KB sửa tăng tổng cost khoảng 3.8% so với v2 và đạt 23/23.

Evidence: [eval v1](reports/eval_v1.json), [eval v2](reports/eval_v2.json), [eval sau sửa KB](reports/eval_v2_fixed.json). Workflow [agent-quality.yml](.github/workflows/agent-quality.yml) chạy eval trong CI với `--min-accuracy 1.0` và baseline v2; exit code khác 0 làm job/PR thất bại, chặn merge.

## 4. Observability stack (production)

Stack Docker Compose chạy với project `k5-day14-observability`: agent, Nginx, Prometheus, Grafana, Jaeger và Locust. UI: Grafana `http://localhost:3000`, Prometheus `:9090`, Jaeger `:16686`, Locust `:8089`.

### 4.1 Screenshot và evidence

- [x] [Grafana dashboard trong lúc có tải](screenshots/grafana-dashboard.png) — panel Traffic ghi nhận 17.9 req/s và Error rate chuyển đỏ.
- [x] [Trace chậm trên Jaeger](screenshots/jaeger-slow-trace.png).
- [x] [Trace lỗi trên Jaeger](screenshots/jaeger-error-trace.png), có lỗi upstream.
- [x] [Prometheus Alerts có ít nhất hai alert firing](screenshots/prometheus-alert-firing.png) — ảnh cho thấy `LLMCostBurnRateHigh`, `AgentHighErrorRate`, `AgentInstanceDown` firing.

Snapshot API tương ứng: [A+D alerts](reports/prometheus_alerts_cp8.json), [B alerts](reports/prometheus_alerts_B.json), [C alerts](reports/prometheus_alerts_C.json), [E alerts](reports/prometheus_alerts_E.json). Alert rule unit tests chạy bằng Docker `promtool test rules` và trả `SUCCESS`: [output](reports/promtool_test_rules.txt).

Tóm tắt cấu hình, trạng thái alert, kết quả Locust và các giới hạn quy kết dạng máy đọc được: [chaos_experiments.json](reports/chaos_experiments.json).

### 4.2 Thí nghiệm fault injection (CP8)

| # | Thay đổi và kết quả Locust | Alert đã quan sát | Thời gian tới firing / ghi chú |
|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2`; lượt chạy ghép với D có 3,017 POST `/ask`, 649 lỗi (21.51%). | `AgentHighErrorRate` firing; snapshot ghi value 19.35% khi được lấy. | Rule `for: 1m`; Prometheus snapshot cho biết điều kiện bắt đầu pending tại 15:01:17Z, sau đó trạng thái firing đã xuất hiện trong ảnh Alerts. Lượt chạy ghép D nên failure tổng không thể quy riêng cho A. |
| B | `MOCK_SLOW_RATE=0.3`; 2,638 POST `/ask`, 29 lỗi; p95/p99 1,700 ms. | `AgentHighLatencyP95` firing, value khoảng 1.918 s. | `activeAt=15:06:57Z`, rule `for: 2m`; snapshot firing được lấy sau ngưỡng này. |
| C | `LLM_MODEL=mock-llm-large`; 1,875 POST `/ask`, 14 lỗi; median 440 ms, p95 510 ms, khoảng 15.71 req/s. | `LLMCostBurnRateHigh` firing, giá trị đo $16.05/giờ. | Alert đã có `activeAt=15:13:42Z`, sớm hơn lúc bắt đầu lượt C (15:17:47Z), nên lượt này xác nhận mức cost cao trong lúc dùng model large nhưng **không chứng minh riêng C đã kích hoạt alert**. |
| D | Pause một agent trong lượt chạy ghép A+D; Nginx có request timeout đến 60 giây. | `AgentInstanceDown` firing cho instance `172.18.0.8:8000`. | Điều kiện pending bắt đầu 15:02:07Z; rule `for: 30s`; ảnh Alerts ghi nhận firing. Lượt ghép làm phát sinh cả 503/504 nên không tách được failure rate riêng cho D. |
| E | `AGENT_VERSION=v1`, `MOCK_ERROR_RATE=0`, `MOCK_SLOW_RATE=0`; sau health check, 759 POST `/ask`, 0 lỗi, p95 190 ms. | Không có alert mới cho error, latency hoặc instance down. Alert cost từ lượt trước vẫn còn firing trong snapshot E. | Hạ tầng khỏe không phát hiện quality regression: eval v1 chỉ đúng 1/23 (4.35%), trong khi v2 đúng 21/23. Dùng golden-set eval/canary theo version để bắt lỗi loại này. |

CSV thực tế: [A+D](benchmark-results/chaos_A_D_stats.csv), [B](benchmark-results/chaos_B_stats.csv), [C](benchmark-results/chaos_C_stats.csv), [E sau warm-up](benchmark-results/chaos_E_clean_stats.csv). Lượt E thử đầu tiên bị 502 trong khoảng lúc recreate container; không dùng lượt đó làm kết luận chất lượng, thay bằng lượt clean có health check trước khi load.

### 4.3 Debug bằng trace

Trace chậm nhất trong tập 100 trace truy vấn từ Jaeger:

- `trace_id`: `a378833fd9a83526fc832472850b8b12`
- Tổng thời gian: 1,717.12 ms.
- Span lớn nhất: `chat mock-llm-small`, 1,691.09 ms (98.5% tổng thời gian).
- Log JSON cùng `trace_id` nằm trong [trace_logs_cp8.json](reports/trace_logs_cp8.json); event `llm_call`, `llm_ms=1691.9`, request 1,718.5 ms, HTTP 200.

Trace lỗi đã chụp: `2c0dc0977f1976a7c4c5ec9682fea8c6`; span `chat mock-llm-small` phát sinh exception do mock upstream trả 503. Log cùng trace và response 503 nằm trong [trace_logs_cp8.json](reports/trace_logs_cp8.json); chi tiết trace ở [jaeger_trace_summary.json](reports/jaeger_trace_summary.json).

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS `/ask` | p50 (ms) | p95 (ms) | p99 (ms) | Failures `/ask` |
|---:|---:|---:|---:|---:|---:|
| 1 | 60.34 | 190 | 240 | 1700 | 79/7206 (1.10%) |
| 3 | 60.16 | 190 | 220 | 1700 | 76/7184 (1.06%) |

Tăng từ 1 lên 3 instance cải thiện p95 khoảng 20 ms trong lượt chạy này nhưng không tăng throughput; mock upstream và nhóm request tail quanh 1.7 giây là giới hạn chính. Các lỗi 503 phù hợp với `MOCK_ERROR_RATE=0.01` mặc định.

Evidence: [scale 1 CSV](benchmark-results/scale_1_stats.csv), [scale 3 CSV](benchmark-results/scale_3_stats.csv). Hai lệnh chạy bằng project đúng `k5-day14-observability` và tạo lần lượt 7,206/7,184 request `/ask`.

## 6. Kết luận

1. p95/p99 cho thấy tail latency bị average che khuất; concurrency 100 và slow rate 0.1 vi phạm SLO p95.
2. Retrieval/KB cải thiện accuracy từ 21/23 lên 23/23; cần quality gate bên cạnh health/latency/error alert.
3. Ba instance chỉ cải thiện p95 nhẹ trong môi trường mock; trace chỉ ra mock LLM chiếm phần lớn thời gian request chậm.

Khi triển khai thật, nên bổ sung alert cho error budget burn, dependency timeout/retry, Redis latency/availability, CPU/memory saturation và canary accuracy/cost theo version/model.

## 7. Deployment status

Không có Railway/Render/Cloud Run public deployment trong lần làm này, vì vậy không có URL hoặc ảnh dashboard deploy thật. [DEPLOYMENT.md](DEPLOYMENT.md) ghi trạng thái này và các bước/biến cần có khi triển khai; không sử dụng URL mẫu như thể đã deploy.
