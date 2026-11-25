# Day 14 Lab - Mission Answers

> Bài làm cá nhân. Thay các mục `[Điền ...]` bằng kết quả đo/chạy thực tế của bạn.
> Không đưa API key, JWT token, mật khẩu hoặc secret vào file này.

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found

Đọc `01-localhost-vs-production/develop/app.py`. Các vấn đề tìm được:

1. `OPENAI_API_KEY` được hardcode trong source code. Nếu commit/push code, secret có thể bị lộ; đổi môi trường cũng phải sửa code.
2. `DATABASE_URL` được hardcode, gắn ứng dụng với một cấu hình máy/môi trường cụ thể.
3. `DEBUG = True` và `MAX_TOKENS` được đặt trực tiếp trong code, không linh hoạt giữa local và production.
4. Dùng `print()` thay vì structured logging, khó lọc/tìm kiếm log tập trung.
5. In API key ra log, có thể làm lộ secret trong terminal hoặc hệ thống thu thập log.
6. Không có health endpoint để nền tảng kiểm tra ứng dụng còn hoạt động hay không.
7. Port `8000` bị cố định, không đọc biến môi trường `PORT` do nền tảng cloud cung cấp.
8. Bind vào `localhost`, khiến ứng dụng không nhận kết nối từ bên ngoài container.
9. Bật `reload=True`, phù hợp phát triển nhưng không phù hợp production.

### Exercise 1.2: Kết quả chạy develop

- Lệnh chạy: `python app.py`
- Lệnh kiểm tra: `curl -i -X POST "http://localhost:8000/ask?question=Hello"`
- Kết quả HTTP/body thực tế: **{"message":"Hello! Agent is running on my machine :)"}**

### Exercise 1.3: Comparison table

| Feature | Develop | Production | Why Important? |
|---|---|---|---|
| Config | Hardcoded values | Environment variables/config | Thay đổi theo môi trường mà không sửa source; tránh commit secrets |
| Secrets | Key hardcode và bị in ra log | Không ghi secret vào source/log | Giảm nguy cơ lộ thông tin xác thực |
| Bind/port | `localhost`, port cố định 8000 | `0.0.0.0`, port từ `PORT` | Nhận traffic từ container/cloud và dùng được port nền tảng cấp |
| Health check | Không có | `GET /health` | Nền tảng kiểm tra process còn hoạt động |
| Readiness | Không có | `GET /ready` | Load balancer biết khi nào ứng dụng sẵn sàng nhận traffic |
| Logging | `print()` | Structured JSON logs | Dễ parse, tìm kiếm và phân tích tập trung |
| Shutdown | Không quản lý vòng đời rõ ràng | Lifespan xử lý shutdown có kiểm soát | Giảm nguy cơ cắt ngang request khi dừng ứng dụng |
| Reload | `reload=True` | Tắt reload trong production | Tránh chế độ phát triển trên môi trường phục vụ thật |

- Kết quả gọi `GET /health`: **{"status":"ok","uptime_seconds":72.3,"version":"1.0.0","environment":"development","timestamp":"2026-11-25T08:35:50.578358+00:00"}**
- Kết quả gọi `GET /ready`: **{"ready":true}**

## Part 2: Docker

### Exercise 2.1: Dockerfile questions

1. Base image: `python:3.11`.
2. Working directory: `/app`.
3. Copy `requirements.txt` trước source để cache dependency layer khi chỉ source code thay đổi.
4. `CMD` là lệnh/đối số mặc định khi chạy container và thường có thể override. `ENTRYPOINT` định nghĩa executable chính.

### Exercise 2.2: Image develop

- Lệnh build: `docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .`
- Kiểm tra: `docker images my-agent:develop`
- Kích thước đo được: **DISK USAGE: 1.15GB/CONTENT SIZE: 0B**
- Lệnh gọi container: `curl -i -X POST "http://localhost:8000/ask?question=What%20is%20Docker%3F"`
- Kết quả HTTP/body: **{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}**

### Exercise 2.3: Image size comparison

- Stage `builder`: cài build dependencies và Python packages.
- Stage `runtime`: chỉ lấy Python slim, packages đã cài và source cần thiết để chạy app.
- Image runtime nhỏ hơn vì không mang theo compiler/build tools không cần khi chạy.

- Develop: **1.15 GB** (`my-agent:develop`, disk usage được ghi nhận).
- Production/advanced: **163 MB** (`my-agent:advanced`).
- Difference: **86,16%** giảm theo phép tính đã ghi nhận: `(1.15 GB - 163 MB) / 1.15 GB × 100`.

Image production dùng multi-stage build: stage `builder` cài dependencies; stage `runtime` chỉ chứa Python slim, packages và source cần để chạy app.

### Exercise 2.4: Compose stack

Sơ đồ luồng:

```text
Client → Nginx (cổng 80) → Agent (port 8000)
                              ├─ Redis (cache/state)
                              └─ Qdrant (vector database)
```

- Project Compose sử dụng: `k5-day14-docker`
- Kết quả `docker compose ps`: **healthy**
- `GET http://localhost/health`: **{"status":"ok","uptime_seconds":149.8,"version":"2.0.0","timestamp":"2026-11-25T09:02:49.640984"}**
- `POST http://localhost/ask` qua Nginx: **{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}**
- Sau khi kiểm tra, đã dọn stack bằng `docker compose -p k5-day14-docker down`: **Đã Removed**

## Part 3: Cloud Deployment

### Exercise 3.1: Railway deployment

- URL: **Chưa deploy; chưa có public URL thực tế để ghi.**
- Screenshot: **Chưa có ảnh chụp deployment.**

### Exercise 3.3: Cloud Run CI/CD (chỉ đọc, không deploy)

Cloud Build trước tiên cài dependencies và chạy tests. Nếu tests thành công, pipeline build Docker image, gắn tag theo commit và `latest`, rồi push image lên Container Registry. Cuối cùng, pipeline deploy image lên Cloud Run tại `asia-southeast1` với giới hạn tài nguyên và số instance. Cấu hình service khai báo health probes và lấy secrets từ Secret Manager thay vì hardcode vào source.

## Part 4: API Security

### Exercise 4.1-4.3: Test results

- Header dùng để xác thực: `X-API-Key`.
- Khi thiếu key, endpoint trả **401**. http trả về: {"detail":"Missing API key. Include header: X-API-Key: <your-key>"}
- Khi key hợp lệ, endpoint xử lý request; kết quả thực tế: **{"question":"Hello","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}**.
- Trong bản develop, key sai trả **403** theo code hiện tại; không ghi key thật vào báo cáo. {"detail":"Invalid API key."}
- Có thể rotate key bằng cách thay giá trị `AGENT_API_KEY` ở cấu hình/environment, sau đó cập nhật client được cấp quyền.

#### JWT và rate limit

- Token được lấy từ `POST /auth/token` bằng tài khoản lab `student` / `demo123`.
- Không đưa token vào báo cáo; chỉ ghi mã HTTP và nội dung đã che thông tin nhạy cảm.
- Tài khoản `student` bị giới hạn 10 requests/phút; rate limiter dùng sliding window trong memory ở demo này.

| Trường hợp kiểm tra | Kết quả thực tế | Ghi chú |
|---|---|---|
| Thiếu API key | `401` — `{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}` | Không ghi key thật |
| API key hợp lệ | `200` — request trả câu trả lời mock | Không ghi key thật |
| API key sai (bản develop) | `403` — `{"detail":"Invalid API key."}` | Kết quả theo code develop được ghi nhận |
| Không gửi JWT | `401` — yêu cầu `Authorization: Bearer <token>` | Không ghi token |
| JWT hợp lệ | `200` | Nội dung response đã lược token và trường usage lỗi định dạng |
| Vượt rate limit | `429` từ request thứ 10 trở đi | Demo rate limit theo memory |

Rate limit hạn chế số request trong một khoảng thời gian nhằm bảo vệ dịch vụ khỏi lạm dụng/tải đột biến. Cost guard theo dõi chi phí sử dụng và từ chối khi vượt ngân sách. Vì vậy rate limit bảo vệ tốc độ/tải, còn cost guard bảo vệ ngân sách.

### Exercise 4.4: Cost guard implementation

Code demo kiểm tra ngân sách theo ngày trước khi gọi mock LLM, tính chi phí dựa trên số input/output tokens và ghi nhận usage. Budget mặc định trong `04-api-gateway/production/cost_guard.py` là `$1/ngày/user`, cảnh báo từ 80%, và `$10/ngày` toàn cục. Bản demo lưu dữ liệu trong memory; đây không phải Redis-backed persistent storage.

- Kết quả kiểm thử cost guard: **Rate limit giới hạn tốc độ/số lượng request trong một khoảng thời gian.
Cost guard giới hạn chi phí tích lũy, giúp chặn khi gần hoặc vượt ngân sách.
Bản demo lưu usage trong memory; budget mặc định là $1/ngày mỗi user và $10/ngày toàn cục.**

## Part 5: Scaling & Reliability

### Exercise 5.1-5.5: Implementation notes

#### Health/readiness và shutdown

- `/health` là liveness: process còn chạy hay không. Nền tảng có thể dùng để phát hiện và khởi động lại process bị lỗi.
- `/ready` là readiness: ứng dụng/phụ thuộc cần thiết đã sẵn sàng nhận traffic chưa. Nếu Redis không sẵn sàng, endpoint production trong demo trả 503.
- Graceful shutdown: khi nhận SIGTERM, server ngừng nhận request mới và chờ request đang chạy hoàn tất trước khi thoát.

| Kiểm tra | Kết quả thực tế |
|---|---|
| `GET /health` | **{"status":"ok","uptime_seconds":8.7,"version":"1.0.0","environment":"development","timestamp":"2026-11-25T09:34:47.719970+00:00","checks":{"memory":{"status":"ok","used_percent":8.5}}}** |
| `GET /ready` | **{"ready":true,"in_flight_requests":1}** |
| Request đang chạy hoàn tất khi shutdown | **{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}** |

#### Stateless và load balancing

Trong thiết kế stateful, mỗi instance giữ history trong RAM riêng nên request tiếp theo đến instance khác có thể không tìm thấy session. Bản production lưu conversation history trong Redis; vì vậy các instance có thể dùng chung session state.

- Compose project: `k5-day14-scaling`
- Cổng public: `8080`
- Endpoint chat: `POST /chat`
- Kết quả `docker compose -p k5-day14-scaling ps`: **5 services đang chạy: 3 agent healthy, Redis healthy, Nginx up.**
- Kết quả chạy `python3 test_stateless.py`:
  - Instances quan sát được (`served_by`): **3** (`instance-fcca63`, `instance-011ddf`, `instance-bf8d51`).
  - Số messages đọc lại trong history: **10** (5 câu hỏi và 5 câu trả lời).
  - Session history được bảo toàn: **Có**. Script xác nhận history còn nguyên khi các request được phục vụ bởi nhiều instance; dữ liệu dùng Redis.
- Đã dọn stack bằng `docker compose -p k5-day14-scaling down`: **Có**

## Part 6: Final Project — Production-ready AI Agent

### Exercise 6.1–6.12: Checklist Deliverable

Kết quả dưới đây là lượt chạy đầy đủ trong Ubuntu/WSL bằng Linux Python và Docker CLI; `check_production_ready.py` được giữ nguyên. Docker image build được, kích thước 183 MB. SIGTERM lúc đang có request được kiểm tra thật: request vẫn trả 200, process thoát exit code 0; `docker stop` cũng đạt trong 0.7 giây.

- ✅ Dockerfile multi-stage, dưới 500 MB
- ✅ Compose agent + Redis
- ✅ `.dockerignore`
- ✅ `/health`
- ✅ `/ready`
- ✅ API key authentication
- ✅ Redis-backed rate limiting
- ✅ Cost guard
- ✅ Config từ environment variables, không hard-code secret
- ✅ Structured JSON logging
- ✅ Graceful shutdown: SIGTERM giữ request đang chạy trả 200, process thoát exit code 0; Docker stop exit code 0 trong 0.7 giây
- ✅ Railway config và health check path

**Kết quả checker:** `12/12 tiêu chí đạt · 41/41 checks passed` — `PASS 12/12 — PRODUCTION READY!`. Output đầy đủ: [check_production_ready_wsl.txt](reports/check_production_ready_wsl.txt). Lượt chạy PowerShell trước đó là 11/12 vì checker bỏ qua SIGTERM trên Windows; dùng output WSL này làm bằng chứng đạt.

## Part 7: Benchmark & Observability

### Exercise 7.1–7.7: Benchmark, observability và kết quả CP8

- Báo cáo hoàn chỉnh: [BENCHMARK_REPORT.md](BENCHMARK_REPORT.md).
- Load test concurrency và tail latency: 7 JSON thật trong [`reports/`](reports/) (300 request mỗi file).
- Evaluation: `eval_v1.json` đạt 1/23, `eval_v2.json` đạt 21/23, `eval_v2_fixed.json` đạt 23/23. CI quality gate: [.github/workflows/agent-quality.yml](.github/workflows/agent-quality.yml); exit code khác 0 làm job thất bại và chặn merge. Alert rule unit tests: [`promtool_test_rules.txt`](reports/promtool_test_rules.txt) — `SUCCESS`.
- Locust headless 100 users/2 phút với project `k5-day14-observability`: [`scale_1_stats.csv`](benchmark-results/scale_1_stats.csv), [`scale_3_stats.csv`](benchmark-results/scale_3_stats.csv). `/ask` đạt lần lượt 7,206 và 7,184 request.
- Fault injection A–E có CSV, alert snapshots, thời gian và các giới hạn quy kết được ghi trong báo cáo. A/D được chạy cùng lượt nên lỗi của hai thay đổi không thể phân tách chính xác. Ở C, alert cost đã firing trước khi đổi model; snapshot ghi $16.05/giờ trong thời gian model large chạy. E chạy v1 healthy, 759 request không lỗi; snapshot còn alert cost cũ nhưng không xuất hiện alert mới về error/latency/down. Eval golden-set bắt regression v1.
- Tóm tắt số liệu fault injection có cấu trúc: [`chaos_experiments.json`](reports/chaos_experiments.json).
- Ảnh bằng chứng thật: [`grafana-dashboard.png`](screenshots/grafana-dashboard.png), [`jaeger-slow-trace.png`](screenshots/jaeger-slow-trace.png), [`jaeger-error-trace.png`](screenshots/jaeger-error-trace.png), [`prometheus-alert-firing.png`](screenshots/prometheus-alert-firing.png). Ảnh Prometheus cho thấy đồng thời 3 alert firing: cost, error rate, instance down.
- Trace/log cùng ID: [`jaeger_trace_summary.json`](reports/jaeger_trace_summary.json) và [`trace_logs_cp8.json`](reports/trace_logs_cp8.json).
- **Chưa deploy public** lên Railway/Render/Cloud Run nên không có URL public hoặc ảnh dashboard deploy. Không điền URL mẫu; trạng thái ghi trong [DEPLOYMENT.md](DEPLOYMENT.md).
