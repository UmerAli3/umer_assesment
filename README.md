🛠 Tasks Summary & Evidence
Task 1: Linux Operations & Health Diagnostics
Artifact: 
Health.sh
Description: Bash diagnostic script reporting CPU load averages, memory saturation, disk allocation, system service states (nginx, docker), and active socket bindings (ss -lntp).



Task 2: Containerized REST API
Artifacts: app/app.py, app/Dockerfile, app/docker-compose.yml
Description: Flask CRUD user management service (GET/health, GET /users, GET /users/<id>, POST /users, PUT /users/<id>). Backed by SQLite, built on lightweight Python slim base image with a Docker native HEALTHCHECK.

Task 3: NGINX Reverse Proxy & Controlled 502 Failure
Artifacts: nginx/nginx.conf.WORKING, nginx/nginx.conf.BROKEN, logs-evidence/
Description: Configured reverse proxy on port 8080 passing requests to backend port 5000 with standard forward headers (Host, X-Real-IP, X-Forwarded-For, X-Forwarded-Proto).
Controlled Incident: Swapped upstream to non-listening port 5099. Captured resulting 502 Bad Gateway, identified 111: Connection refused in error.log, isolated using direct backend curl, and restored service safely via nginx -t and reload.


Task 4: CI/CD Quality Gate
Artifacts: ci/Jenkinsfile, .github/workflows/api-regression.yml
Pipeline Flow: Checkout 
→
→ Build 
→
→ Automated Tests 
→
→ Docker Build 
→
→ Deploy 
→
→ Smoke Test.
Quality Gate: Automated tests act as a hard deployment gate; a single test failure halts the pipeline before image build/deployment.


Task 5: Database Investigation & SQL Optimization
Artifact: database/schema.sql
Description: Relational schema implementing users and orders with foreign keys and index strategies. Demonstrates lookup, aggregations (COUNT, SUM), GROUP BY / HAVING, duplicate identification, and query plan optimization via EXPLAIN QUERY PLAN.


Task 6: Manual QA Test Design
Artifact: qa-manual/QA_Test_Cases.xlsx
Description: 20 comprehensive test cases spanning functional, positive, negative, boundary, integration, and security checks across all CRUD endpoints.


Task 7: Automated API Regression Suite
Artifact: tests/test_regression.py
Description: 18 automated test assertions verifying HTTP status codes, schema validation, mandatory payload fields, boundary inputs, and response latency constraints (
<
500
 ms
<500 ms).



Task 8: Apache JMeter Load Benchmarking
Artifacts: jmeter/load_test_100users.jmx, jmeter/results/
Parameters: 100 concurrent threads, 10s ramp-up, non-GUI execution.
Results: Processed 14,792 samples across NGINX with sub-second response times and zero connection dropped errors. Raw evidence stored in results.jtl and results_summary.txt.



Task 9: Capacity & Stress Testing
Artifacts: performance/load_test.py, capacity_analysis.md
Execution: Progressive user load stepped through 50 
→
→ 100 
→
→ 200 
→
→ 300 
→
→ 500 concurrent connections on a single-core, ~3.9 GB RAM host.
Findings: Identified inflection point where latency degrades as worker threads become saturated. Explains why average latency alone is insufficient and why p95/p99 latency reflects the real user bottleneck.



Task 10: Reliability Monitoring & Observability
Artifacts: monitoring/docker-compose.yml, monitoring/prometheus/prometheus.yml, monitoring/grafana/, RCA.md
Description: Production monitoring stack incorporating Prometheus, Node Exporter, Blackbox HTTP probes, and Grafana dashboards. Features real-time host saturation metrics, continuous end-to-end NGINX availability checks, and a comprehensive Root Cause Analysis (RCA) report documenting post-release failure isolation and recovery.
