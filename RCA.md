# Root Cause Analysis (RCA) — Production Incident Report

| Incident ID | INC-2026-0915-01 |
| :--- | :--- |
| **Severity Level** | **P1 (Critical Outage)** |
| **Affected Service** | `UserAPI` / Public Reverse Proxy (`nginx-proxy`) |
| **Incident Title** | 502 Bad Gateway Outage Following Deployment Configuration Change |
| **Date & Time** | 2026-09-15 14:15:00 UTC |
| **Incident Commander** | Muhammad Umer Ali (DevOps Engineer) |
| **Duration of Outage**| 11 Minutes (14:15:00 UTC – 14:26:00 UTC) |

---

## 1. Executive Summary

At 14:15 UTC following a configuration release, the NGINX reverse proxy began serving `502 Bad Gateway` errors for all incoming client traffic targeting `http://<host>:8081/*`. Direct health checks through the proxy failed immediately. L2 investigation identified that the upstream backend port in `nginx.conf` had been misconfigured from `5000` to non-listening port `5099`. The configuration was corrected, verified via `nginx -t`, and reloaded safely at 14:24 UTC. Full automated regression suites passed at 14:26 UTC confirming complete service restoration.

---

## 2. Customer & Business Impact

- **External Impact:** 100% of public API calls through the NGINX gateway failed with HTTP 502.
- **Affected Endpoints:** All public API routes (`/health`, `/users`, `/users/<id>`).
- **Internal State:** The backend Flask/Gunicorn container (`userapi`) and database remained 100% healthy; outage was isolated strictly to proxy routing.
- **Total Downtime:** 11 minutes of degraded/unusable service.

---

## 3. Incident Timeline

| Timestamp (UTC) | Event Description |
| :--- | :--- |
| **14:15:00** | Deployment of updated proxy configuration initiated. |
| **14:15:45** | Automated post-deployment smoke test fails: `curl -sf http://localhost:8081/health` returns `502 Bad Gateway`. |
| **14:16:30** | Prometheus Blackbox probe alert triggers: `probe_success{job="nginx-http-probe"} == 0`. |
| **14:17:00** | Incident declared P1. Deployment freeze enacted. |
| **14:18:15** | Direct backend probe executed: `curl -i http://localhost:5000/health` returns `HTTP 200 OK`. Isolates failure to the NGINX upstream layer. |
| **14:19:40** | NGINX error logs inspected (`/var/log/nginx/error.log`). Error signature isolated: `connect() failed (111: Connection refused) while connecting to upstream: "http://userapi:5099/health"`. |
| **14:21:00** | Active socket inspection inside backend container confirms Flask is listening on port `5000`, not `5099`. |
| **14:23:00** | Upstream port restored from `5099` back to `5000` in `nginx.conf.WORKING`. |
| **14:23:45** | Configuration validated: `nginx -t` confirms syntax is valid. |
| **14:24:10** | Safe configuration reload executed: `nginx -s reload` (zero-downtime worker swap). |
| **14:24:30** | Smoke test passes: `curl -i http://localhost:8081/health` returns `HTTP 200 OK`. |
| **14:26:00** | Full 18-test automated regression suite (`pytest regres_test/test_regression.py`) executed; all pass. Incident resolved. |

---

## 4. Detection

- **Detection Mechanism:** Blackbox HTTP probe alert and post-release smoke test.
- **Time to Detect (TTD):** 45 seconds after container startup.
- **Why Monitoring Succeeded:** End-to-end HTTP probe through the ingress path caught the failure even though container resource metrics (CPU and Memory) were completely normal.

---

## 5. Investigation Sequence (Evidence-Based L2 Diagnostics)

1. **Verify Symptom:**
   ```bash
   curl -i http://localhost:8081/health
   # Result: HTTP/1.1 502 Bad Gateway
   ```
2. **Isolate Proxy vs Backend (Direct vs Proxy Curl):**
   ```bash
   curl -i http://localhost:5000/health
   # Result: HTTP/1.1 200 OK (Backend is alive and responding)
   ```
3. **Inspect Gateway Error Logs:**
   ```bash
   docker logs nginx-proxy --tail 20
   # Log line:
   # 2026/09/15 14:19:40 [error] 29#29: *1 connect() failed (111: Connection refused) 
   # while connecting to upstream, client: 172.18.0.1, server: _, 
   # request: "GET /health HTTP/1.1", upstream: "http://userapi:5099/health"
   ```
4. **Identify Configuration Divergence:**
   Inspecting `upstream backend_app` showed `server userapi:5099;` instead of expected `server userapi:5000;`.

---

## 6. Root Cause

A typo during configuration refactoring changed the upstream definition in `nginx.conf` to port `5099`. Because NGINX was able to resolve the DNS name `userapi`, the configuration syntax test (`nginx -t`) succeeded during container build. However, at runtime, TCP connection attempts from NGINX to `userapi:5099` received immediate TCP RST packets (Connection Refused), triggering NGINX's default 502 Bad Gateway response.

---

## 7. Resolution & Recovery

- **Immediate Fix:** Replaced faulty port `5099` with correct port `5000` in the upstream configuration block.
- **Validation:** 
  1. Ran `nginx -t` to ensure configuration syntax validity.
  2. Reloaded NGINX master process using `nginx -s reload` without tearing down active connections.
  3. Validated end-to-end connectivity via curl and Prometheus probe recovery.

---

## 8. Preventive Actions & Controls

### A. Implemented Controls (Already active in repo)
1. **Automated CI/CD Quality Gate:** Smoke test stage in `Jenkinsfile` and `.github/workflows/api-regression.yml` executes `curl -sf http://localhost:${APP_PORT}/health`. Any 5xx response immediately halts deployment and prevents release promotion.
2. **Pre-commit Syntax Checks:** Strict requirement to execute `nginx -t` before any reload or container commit.
3. **Separated Environment Artifacts:** Retention of verified `nginx.conf.WORKING` alongside test failure artifacts.

### B. Proposed Controls (Scheduled for implementation)
1. **Dynamic Environment Variable Substitution:** Use `envsubst` or Docker Compose environment variables for upstream ports (`proxy_pass http://userapi:${BACKEND_PORT}`) to eliminate hardcoded configuration mismatches.
2. **Container Synthetic Health Probe in CI:** Enforce automated integration smoke tests in an ephemeral staging container network prior to production traffic cutover.
3. **Automated Rollback Policy:** Incorporate a 15-minute time-boxed automatic rollback trigger if post-deployment 5xx error rate exceeds 1%.

---

## 9. Escalation & Stakeholder Communication Log

| Time (UTC) | Channel | Message Content |
| :--- | :--- | :--- |
| **14:17** | Slack `#ops-incidents` | *Alert: P1 Incident declared. Public API returning 502 errors. Investigation underway by DevOps. Deployment freeze in effect.* |
| **14:22** | Slack `#ops-incidents` | *Update: Root cause isolated to upstream proxy routing. Fix applied and undergoing validation.* |
| **14:27** | Slack `#ops-incidents` | *Resolved: Upstream configuration restored. Automated regression suite 100% green. Service restored to normal.* |
