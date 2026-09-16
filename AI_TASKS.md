
## AI Task 1 — Generate API Test Cases from a Collection

### 1. My Prompt
> "Here's an API spec: POST /users, takes name/email/status, returns 201 with an id
> on success. Possible responses are 201, 400 (missing/invalid field), 409 (duplicate
> email), 415 (unsupported content type), 500 (server error). Give me a complete set
> of test cases — functional, positive, negative, boundary, and regression — for this
> endpoint."

### 2. AI Response
The AI came back with a reasonably long list, roughly grouped like this:

- Positive: valid create returns 201 with correct body; response includes an `id`.
- Negative: missing `name`; missing `email`; missing `status`; invalid email format;
  empty request body; wrong data types (e.g. `name` as a number).
- Duplicate: creating the same email twice returns 409.
- Content-type: sending `text/plain` or no `Content-Type` header returns 415.
- Server error: simulate a 500 (it suggested mocking a DB failure).
- Boundary: extremely long `name` (255+ chars), empty string `name`, email at the
  edge of valid format (e.g. `a@b.co`), unicode characters in `name`.
- Regression: re-run the positive case after any schema change to confirm `id`,
  `name`, `email`, `status` are still all present and typed correctly.

It gave about 18 cases total, each as a one-line description, not actual code.

### 3. My Review
Mostly solid as a checklist, but a few real problems:

- **It listed "invalid status value" as a boundary case, which is wrong — that's a
  negative/validation case, not a boundary one.** Boundary is about edges of valid
  input ranges (length limits, numeric limits), not about an entirely invalid
  category value. I moved it.
- **It never mentioned what happens if `status` is omitted entirely** — does the API
  default it to `active`, or reject the request? That's actually a meaningful design
  question the test suite needs to pin down, and the AI just didn't ask or flag the
  ambiguity. I added it as its own case, and it turned out (from my own earlier
  build of this app) that the API does default it, so the test has to assert that
  specific default, not just "it works."
- **Duplicate detection needs to specify case-sensitivity.** Is `Ali@example.com` a
  duplicate of `ali@example.com`? The AI's case just said "duplicate email → 409"
  without addressing case folding, which is a classic real-world bug source. I
  added a case for it.
- **The 500 case is basically untestable as described.** "Simulate a DB failure" is
  fine as an idea but the AI gave zero suggestion for how — no mention of DB
  connection kill, mocking, or fault injection. I ended up treating this as
  out-of-scope for automated testing here and documenting it as a manual/chaos-test
  candidate instead, rather than pretending I automated something I didn't.
- Two of its "boundary" cases (long name, unicode name) were fine but duplicated
  with slightly different wording in two places in its list — I merged them.
- It missed SQL-injection-style payloads in the name field entirely, which is a
  regression case I care about a lot given what I found in earlier testing on this
  exact app — a name like `Robert'); DROP TABLE users;--` needs to be stored as
  harmless text. I added that as a dedicated regression case since it's exactly the
  kind of thing a lazy refactor could break.

### 4. Correct/Final Solution
Final test case list, cleaned up (16 cases after removing duplicates and fixing
miscategorization):

| ID | Type | Case |
|---|---|---|
| TC1 | Positive | Valid create → 201, body has id/name/email/status |
| TC2 | Negative | Missing `name` → 400 |
| TC3 | Negative | Missing `email` → 400 |
| TC4 | Negative | Invalid email format → 400 |
| TC5 | Negative | Empty JSON body → 400 |
| TC6 | Negative | Wrong type for `name` (number instead of string) → 400 |
| TC7 | Negative | Invalid `status` value (e.g. "deleted") → 400 |
| TC8 | Functional | Missing `status` field → defaults to `active`, 201 |
| TC9 | Negative | Duplicate email (exact match) → 409 |
| TC10 | Negative | Duplicate email (different case) → 409 |
| TC11 | Negative | `Content-Type: text/plain` → 415 (see evidence note) |
| TC12 | Boundary | `name` at 255 chars → 201 |
| TC13 | Boundary | Empty string `name` → 400 |
| TC14 | Boundary | Minimal valid email (a@b.co) → 201 |
| TC15 | Regression | SQL-injection-style name stored as plain text, table stays intact |
| TC16 | Regression | Re-run TC1 after any release, assert schema unchanged |

Of these, I implemented 6 as real automated pytest tests (more than the required
5) — TC1, TC2, TC4, TC8, TC9, TC15.

```python
# api-tests/test_task1_cases.py
import requests

BASE = "http://localhost:5000"

def test_TC1_create_valid_user():
    r = requests.post(f"{BASE}/users", json={
        "name": "Ali", "email": "ali.tc1@example.com", "status": "active"
    })
    assert r.status_code == 201
    body = r.json()
    assert set(body.keys()) == {"id", "name", "email", "status"}
    assert body["name"] == "Ali"

def test_TC2_missing_name():
    r = requests.post(f"{BASE}/users", json={
        "email": "notc2@example.com", "status": "active"
    })
    assert r.status_code == 400

def test_TC4_invalid_email_format():
    r = requests.post(f"{BASE}/users", json={
        "name": "Bad Email", "email": "not-an-email", "status": "active"
    })
    assert r.status_code == 400

def test_TC8_missing_status_defaults_active():
    r = requests.post(f"{BASE}/users", json={
        "name": "No Status", "email": "nostatus.tc8@example.com"
    })
    assert r.status_code == 201
    assert r.json()["status"] == "active"

def test_TC9_duplicate_email():
    email = "dup.tc9@example.com"
    requests.post(f"{BASE}/users", json={"name": "First", "email": email, "status": "active"})
    r = requests.post(f"{BASE}/users", json={"name": "Second", "email": email, "status": "active"})
    assert r.status_code == 409

def test_TC15_sql_injection_name_stored_safely():
    r = requests.post(f"{BASE}/users", json={
        "name": "Robert'); DROP TABLE users;--",
        "email": "sqltc15@example.com", "status": "active"
    })
    assert r.status_code == 201
    listing = requests.get(f"{BASE}/users")
    assert listing.status_code == 200
    assert len(listing.json()) > 0
```

### 5. Validation/Evidence
These 6 were actually run against the live Flask app built earlier in this project
(`/app/app.py`), not just written and left untested. Evidence lives in
`/evidence/ai-task1-pytest-output.txt` — all 6 passed on first real run once I
fixed one bug on my end (TC11's content-type case needed a manual header override
that `requests` doesn't send by default, so I left it out of the automated 6 and
checked it manually with curl instead — it turned out the app returns 400, not a
clean 415, for that case, meaning there's a real gap in content-type handling
worth a ticket).

### 6. My Explanation
Honestly the AI's first pass was a decent brainstorm — better than staring at a
blank page — but it read like a checklist generated from "common REST API test
patterns" rather than from actually thinking about this API's specific behavior.
The stuff it missed (the default-status ambiguity, case-sensitive duplicate
emails, SQL injection) were exactly the things that come from having actually
built and poked at this app before, not from generic API-testing knowledge.
That's the pattern across all ten tasks: the AI is a good first draft, a bad
final answer.

---

## AI Task 2 — API Collection Automation

### 1. My Prompt
> "Here's my endpoint list: GET /health, GET /users, GET /users/{id}, POST /users,
> PUT /users/{id}. Sample success responses: [pasted the JSON shapes]. Generate
> pytest assertions covering status code, schema/required fields, negative
> behavior, and response time for all of these."

### 2. AI Response
It produced a fairly complete pytest file — one test function per endpoint, each
checking status code and using `assert "field" in response.json()` for schema,
plus a response-time assertion using `response.elapsed.total_seconds() < 1`.

### 3. My Review
- The schema checks were weak — `assert "field" in response.json()` doesn't catch
  extra unexpected fields, and doesn't check types at all. If `id` came back as a
  string instead of an int, none of its assertions would catch that.
- The response-time threshold of a full second is way too generous for what are,
  in practice, simple SQLite-backed reads. That number wasn't derived from
  anything — it reads like a generic "don't fail flaky tests" default. I tightened
  it based on what I'd actually measured earlier (sub-100ms for reads under no
  load), using 500ms as a realistic-but-not-flaky ceiling.
- It didn't test the list endpoint's array-of-objects schema at all — it only
  checked the response was "a list," not that each item had the right shape. A
  broken serializer could return `[{}, {}, {}]` and this test would still pass.
- Negative cases were thin: only "get a non-existent ID → 404." It didn't test
  invalid ID format (like `/users/abc`), a different failure mode (400, not 404)
  this app actually handles as a distinct case.

### 4. Correct/Final Solution
```python
# api-tests/test_task2_endpoints.py
import re
import requests

BASE = "http://localhost:5000"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
REQUIRED_FIELDS = {"id", "name", "email", "status"}
MAX_RESPONSE_TIME = 0.5  # tightened from the AI's 1.0s default

def assert_user_schema(u):
    assert set(u.keys()) == REQUIRED_FIELDS
    assert isinstance(u["id"], int)
    assert EMAIL_RE.match(u["email"])
    assert u["status"] in {"active", "inactive", "pending"}

def test_health():
    r = requests.get(f"{BASE}/health")
    assert r.status_code == 200
    assert r.elapsed.total_seconds() < MAX_RESPONSE_TIME

def test_list_users_schema_every_item():
    r = requests.get(f"{BASE}/users")
    assert r.status_code == 200
    users = r.json()
    assert isinstance(users, list) and len(users) > 0
    for u in users:
        assert_user_schema(u)

def test_get_user_not_found():
    r = requests.get(f"{BASE}/users/999999")
    assert r.status_code == 404

def test_get_user_invalid_id_format():
    r = requests.get(f"{BASE}/users/abc")
    assert r.status_code == 400
```

### 5. Validation/Evidence
Executed against the same live app; all pass. Output saved to
`/evidence/ai-task2-pytest-output.txt`. I also sanity-checked the response-time
number wasn't wishful thinking by running each request 20 times and looking at
the max, not one lucky fast run — max was 41ms, so 500ms has real margin without
being so loose it'd hide a genuine regression.

### 6. My Explanation
The AI's code ran, which can trick you into thinking it's done. But "the test
passes" and "the test would catch a real bug" are different things, and its
version would sail through even with a badly broken list endpoint. The fix here
wasn't about syntax — it was about thinking through what could silently go wrong
that a shallow assertion wouldn't notice.

---

## AI Task 3 — Linux High CPU Investigation

### 1. My Prompt
> "One of my app servers is showing sustained high CPU. Give me a safe
> investigation plan — what to check, in what order — before I even think about
> restarting anything."

### 2. AI Response
It gave: `top`/`htop` to see which process, `uptime` for load average trend,
`ps aux --sort=-%cpu` to confirm the PID, then `strace -p <pid>` to see what
syscalls it's stuck in, then `/proc/<pid>/status` for thread count, then
application logs for the same window. It closed with "if none of that resolves
it, restart the service."

### 3. My Review
- Putting `strace -p <pid>` early, with no warning, is a real safety issue.
  `strace` adds tracing overhead to every syscall — attaching it to a process
  that's already struggling under load can make things measurably worse. It
  shouldn't be step three; it should come much later, briefly, in summary mode
  (`-c`), not as a live trace.
- It never mentioned checking whether the high CPU is one runaway thread vs. many
  threads each doing a normal amount of work — `top -H -p <pid>` gives you that,
  and it changes the whole diagnosis direction. The AI skipped straight past it.
- It never suggested checking whether load correlates with real traffic (from
  app/NGINX logs) before assuming something's broken — high CPU matching a real
  traffic spike isn't a bug, it's capacity.
- "If none of that resolves it, restart" is too casual a bar for a production
  restart — it just resets the clock on the same bug recurring.

### 4. Correct/Final Solution
1. `uptime` — confirm load average trend, not a snapshot.
2. `ps aux --sort=-%cpu | head -10` — identify the actual offending PID(s).
3. `top -H -p <pid>` — one runaway thread, or many sharing load evenly? Determines
   the whole direction of the investigation.
4. Cross-check against app/NGINX access logs for the same window — real traffic
   spike, or CPU climbing with flat traffic (the latter points to code, not
   capacity)?
5. `/proc/<pid>/status` and `vmstat 1 5` for context-switch/run-queue signals.
6. Only then, a short summary-only `strace -c -p <pid> -T` for a few seconds if
   still unclear — not a raw live trace.
7. Check recent deploys/config changes against when the trend started.

### 5. Validation/Evidence
Ran steps 1–5 for real on this project's sandbox host to confirm the commands
work and produce readable output (not against a genuinely struggling server,
since I don't have one on demand — the commands and output shape are real, not
imagined). Output saved in `/evidence/ai-task3-commands-output.txt`.

### 6. What would justify a restart
A restart is justified only with specific evidence: a single PID/thread clearly
pegged with no correlation to real traffic volume, no recent deploy explaining
it, and ideally a `strace -c` summary showing it's spinning on something rather
than doing legitimate work. Restarting without that just resets the symptom, not
the cause, and the bug will likely recur.

### My Explanation
The reordering mattered more than any individual command — the AI's list wasn't
wrong exactly, but the order would have you attaching a debugger to a struggling
process before confirming whether the load was even legitimate traffic.

---

## AI Task 4 — Linux Disk / Log Growth

### 1. My Prompt
> "A server is at 92% disk usage. How do I investigate safely — find what's using
> the space, including logs — without just deleting things blindly?"

### 2. AI Response
It suggested `df -h`, `du -sh /var/log/*` and `du -sh /* | sort -rh`, `find / -type
f -size +100M`, checking for old rotated logs — then said "if you find old logs,
you can safely run `find /var/log -name '*.log' -mtime +30 -delete` to free space
quickly."

### 3. My Review
- Everything up through the investigation commands was safe and read-only, no
  complaints there.
- The `-delete` suggestion is exactly the destructive advice this task asks me to
  catch and reject. A blind `find ... -delete` doesn't check if a log is currently
  open/being written by a running process (deleting an open file doesn't even free
  the space until the process closes it), doesn't check retention/compliance
  needs, and treats a one-time deletion as a fix when the actual root cause is
  usually that log rotation isn't configured properly.
- It never mentioned checking for a deleted-but-still-held file — the classic case
  where `df` shows full but `du` can't find where the space went because a process
  is holding a file handle open on an already-unlinked file. This is one of the
  most common real causes of "disk full but I can't find the files."

### 4. Correct/Final Solution
1. `df -h` — confirm which mount is full.
2. `du -xh --max-depth=2 / 2>/dev/null | sort -rh | head -20` — biggest
   directories (the `-x` flag matters, stops it wandering into other mounts).
3. `du -sh /var/log/* | sort -rh` — drill into logs specifically.
4. `find / -xdev -type f -size +100M 2>/dev/null` — large individual files.
5. `lsof +L1` — the step the AI's plan was missing: lists deleted-but-still-open
   files silently holding disk space. If this shows something big, the fix is
   restarting/reloading that specific process, not deleting anything.
6. Check `logrotate -d /etc/logrotate.conf` — if rotation isn't running or
   compressing, that's the actual root cause, not a symptom to patch manually.
7. Only after identifying a specific, confirmed-safe target (an already-rotated
   `.gz` log older than retention policy) do I remove anything — one file at a
   time, never a wildcard `-delete`.

### 5. Validation/Evidence
Ran the read-only commands (1–4) for real on the sandbox host to confirm sane,
readable output — saved in `/evidence/ai-task4-disk-investigation.txt`. I did not
have an actual deleted-but-open scenario to reproduce safely for `lsof +L1`, so
I'm not claiming I validated that specific detection with real output — noting
that honestly rather than faking a result.

### 6. My Explanation
This is the task where the AI gave genuinely dangerous advice wrapped in
reasonable advice, which is worse than being obviously wrong — the destructive
command came right after a bunch of correct, careful steps, in a tone that made it
sound like the natural next step. If I'd copy-pasted this into a runbook without
reading closely, that `-delete` line would have gone straight into a live
incident procedure. That's exactly the trap this assignment is warning about.

---

## AI Task 5 — NGINX 502 Troubleshooting

### 1. My Prompt
> "After a deployment, NGINX is returning 502 for all requests. The backend app is
> supposed to be listening on port 5000, and NGINX proxies to it. Give me an
> investigation plan to find the root cause."

### 2. AI Response
Check `systemctl status <app>` to see if the backend is running, check NGINX
error logs for the specific upstream error, check `nginx -t` for config validity,
verify the upstream port matches what the app listens on, check firewall/SELinux
if the app is running and the port matches but it's still failing.

### 3. My Review
This one was actually pretty close to what I'd do myself. Two things I tightened:

- It said "check NGINX error logs" without saying what to grep for — I made this
  concrete (`connect() failed` / `Connection refused` tells you wrong-port vs.
  backend-down vs. permissions, since those log differently).
- It blended "is the backend up" and "is NGINX pointed at the right port" into one
  fuzzy "check the config" step instead of two separately-testable curl commands.
  I split these, because that exact split is what let me pinpoint the root cause
  fast in a real controlled-failure exercise I'd already run on this project.

### 4. Correct/Final Solution — validated against a real controlled failure
I'd already run this exact scenario for real earlier in this project (deliberately
pointed NGINX's upstream at the wrong port and diagnosed it live), so I could
check the AI's plan against real evidence, not imagination.

1. `curl` the backend directly on port 5000 — if this fails too, it's not an
   NGINX problem at all. (Real test: succeeded, app was healthy.)
2. `curl` through NGINX — confirms the 502 reproduces at this layer.
3. Grep the NGINX config for the configured upstream port, compare against
   `ss -tuln` for what the app is actually bound to. (Real case: config pointed at
   5099, app was on 5000.)
4. Tail `error.log` for the specific line — mine showed literally
   `connect() failed (111: Connection refused) ... upstream: "http://127.0.0.1:5099/health"`.
5. `nginx -t` to confirm syntax is valid — worth stating explicitly that a wrong
   port is a runtime problem, not a syntax one, so `-t` passing doesn't mean the
   config is correct.
6. Fix the port, reload, re-verify with the same curl commands used to diagnose.

### 5. Validation/Evidence
This isn't hypothetical — the full real run (actual terminal output, actual
`error.log` lines, actual before/after curl results) is documented from this
project's earlier NGINX work, evidence saved under
`/evidence/nginx-502-diagnosis-transcript.txt`.

### 6. My Explanation
This is the one task where I could grade the AI against ground truth I'd already
lived through, and it did reasonably well — better than Tasks 3 and 4. The gaps
were precision (what exactly to grep, what to curl first), not a missing category
of investigation, which tracks with 502-through-a-proxy being a more "standard"
scenario than disk-space forensics.

---

## AI Task 6 — SQL Query Optimization

### 1. My Prompt
> "Here's a query joining users and orders, filtering by LOWER(u.email) =
> LOWER(?) and o.order_status = 'completed', on a users table with ~19 rows and an
> orders table with ~5000 rows. No index on orders.user_id. Suggest
> optimizations."

(The exact query from earlier SQL investigation work on this project.)

### 2. AI Response
Correctly identified both problems: wrapping email in `LOWER()` defeats any index
on it, and the missing index on `orders.user_id` forces a full scan of the larger
table on every join. Suggested `CREATE INDEX idx_orders_user_id ON
orders(user_id);` and rewriting the query to avoid `LOWER()`. Also suggested,
fairly reflexively, adding a second index on `orders.order_status` "for good
measure."

### 3. My Review
The core diagnosis was genuinely correct and matched what I'd independently found
using `EXPLAIN QUERY PLAN` myself. But:

- The `order_status` suggestion needs to be checked against real selectivity, not
  added for good measure. `order_status` only has 4 possible values across 5000
  rows — roughly 1,250 rows per value. An index on a column with that little
  selectivity gives the planner very little to work with while still costing real
  write overhead on every insert. I rejected this because I could quantify why,
  not on instinct.
- The `user_id` index is genuinely high-value — 19 distinct users across 5000
  orders averages ~263 rows per user, and it's the join key, which is exactly
  where an index earns its keep regardless of raw selectivity math. I kept this
  one.
- The AI never mentioned the write-cost trade-off of adding any index — it
  presented indexing as a free win, when it isn't.

### 4. Correct/Final Solution — with real before/after evidence
Implemented only the one index I could justify. Rewrote the query to drop
`LOWER()` (emails are already stored consistently lowercase at the app layer).

Before (`EXPLAIN QUERY PLAN`):
```
SCAN o
SEARCH u USING INTEGER PRIMARY KEY (rowid=?)
```
After (index added, `LOWER()` removed):
```
SEARCH u USING COVERING INDEX sqlite_autoindex_users_1 (email=?)
SEARCH o USING INDEX idx_orders_user_id (user_id=?)
```

### 5. Validation/Evidence
Benchmarked for real: 3000 repeated executions of each version against the actual
database — the indexed/rewritten version ran 5.14x faster (0.48ms/run to
0.09ms/run), with identical result sets both times (74 rows, verified equal), so
the optimization didn't silently change correctness. Also measured the write-side
cost directly: inserting 2000 rows took 3.4x longer with the index present.
Evidence in `/database/evidence_slow_query_BEFORE.txt`,
`/database/evidence_slow_query_AFTER.txt`, and `/database/benchmark_results.txt`.

### 6. My Explanation
The AI got the two real bottlenecks right, which is the hard part. Where I pushed
back was its habit of tacking on an extra "might as well" index without doing the
selectivity math. Indexing everything you can think of isn't optimization, it's
moving cost from reads to writes without checking the trade is worth it. Since I
had real database access, I didn't have to trust either of our opinions — I could
measure it.

---

## AI Task 7 — Regression Suite Design

### 1. My Prompt
> "POST /users and PUT /users/{id} changed in this release. Select and prioritize
> a regression suite — what should I definitely re-run, and in what order of
> priority?"

### 2. AI Response
Suggested re-running: create-user happy path, update-user happy path,
duplicate-email-on-create, and a smoke check that `/health` still responds — in
that priority order — calling it "a solid regression pass for a targeted change."

### 3. My Review
This was the weakest AI response of all ten tasks, honestly.

- It completely missed that `PUT /users/{id}` needs its own duplicate-email
  check, separate from the create-path one — and specifically the subtlety that
  an update needs to exclude the record's own current email from the uniqueness
  check, otherwise updating a user without changing their email would falsely
  trigger a 409 against their own existing row. The AI's list only tested
  duplicate-email on create, which would completely miss a regression in that
  update-specific logic.
- No negative/invalid-ID case for PUT at all — updating a non-existent ID is a
  very standard thing to break in a refactor and wasn't in the list.
- No integration case — nothing that creates via POST then updates the same
  record via PUT to confirm the two changed endpoints work correctly together,
  exactly the kind of bug a release touching both simultaneously is most likely
  to introduce.
- Its prioritization put the `/health` smoke check last, which doesn't make
  sense — a smoke test should run first, as a fast fail-early gate.

### 4. Correct/Final Solution
| Priority | Case | Why |
|---|---|---|
| 1 | Smoke: GET /health returns 200 | Fast fail-early gate |
| 2 | POST /users happy path | Directly touched by the release |
| 3 | PUT /users/{id} happy path | Directly touched by the release |
| 4 | POST duplicate-email → 409 | Directly touched logic |
| 5 | PUT duplicate-email against another user's email → 409 | Missing from AI's list; distinct code path |
| 6 | PUT updating a user without changing their own email → 200, not falsely 409 | The self-exclusion edge case the AI missed entirely |
| 7 | PUT on a non-existent ID → 404 | Standard negative case, absent from AI's list |
| 8 | Integration: POST then immediately PUT the same new record | Tests the two changed endpoints working together |

### 5. Validation/Evidence
Executed this final 8-case suite for real against the live app. All 8 passed,
including case 6, which I was specifically worried about — the app does
correctly exclude the current record from its own duplicate check. Evidence in
`/evidence/ai-task7-regression-run.txt`.

### 6. My Explanation
This is the clearest example across all ten tasks of the AI answering "what's a
generic regression suite for a users API" rather than reasoning about what
changed and what interaction that change creates. The self-exclusion-on-update
case is a genuinely common real bug pattern, and it's exactly the kind of thing
you only think to test if you're picturing the actual code path, not
pattern-matching to "CRUD API, so test CRUD things."

---

## AI Task 8 — JMeter Test Plan Generation

### 1. My Prompt
> "Design a JMeter load test for 200 concurrent users hitting my API through
> NGINX. I need thread group settings, ramp-up, duration/loop strategy,
> assertions, non-GUI execution command, and what metrics to capture."

### 2. AI Response
200 threads, 200-second ramp-up, infinite loop count with a 300-second duration,
a Response Assertion checking for 200 on all samplers, and `jmeter -n -t plan.jmx
-l results.jtl` for execution. Listed throughput, average response time, and
error % as the metrics to capture.

### 3. My Review
- A 200-second ramp-up on a 300-second test means two-thirds of the run is spent
  still ramping up, not at steady state — you end up mostly measuring "somewhere
  between 1 and 200 users," not "the system at 200 users." I shortened this
  significantly relative to total duration.
- A blanket "assert 200 on all samplers" is wrong the moment a test plan includes
  intentionally-negative requests, and even for pure happy-path load it's fragile.
  I scoped assertions per-sampler instead.
- Only "average response time" was mentioned, not p90/p95/p99 — for a load test
  specifically, average is close to useless on its own, it hides tail latency,
  which is usually the thing that actually matters under load.
- No mention of listener overhead — running a live GUI Aggregate Report listener
  during a real 200-user run adds real memory/CPU cost on the load generator
  itself, risking making the load generator the bottleneck instead of the system
  under test. It got the non-GUI command right, just didn't explain why that
  matters.

### 4. Correct/Final Solution — actually built and run
- 200 threads, 20-second ramp-up (not 200s), 60-second steady-state duration
  after ramp completes
- Endpoint mix: /health, /users, /users/{id}, /users?status=active, POST /users
  (unique payload per request so requests don't all collide on the same
  duplicate-email 409)
- No blanket assertion; raw `.jtl` post-processed for real percentiles
  (p50/p90/p95/p99), not just an average
- Executed non-GUI, no live listener: `java -classpath
  ".:/usr/share/jmeter/bin/ApacheJMeter.jar" ... -n -t load_test_200users.jmx -l
  results.jtl -j jmeter.log`

### 5. Validation/Evidence
Full `.jmx`, raw `.jtl`, and computed percentile breakdown are in `/jmeter/`. The
real run at 200 users showed error rate climbing specifically on POST /users
(`sqlite3.OperationalError: database is locked`) — same root cause as the
100-user version of this test run earlier, just proportionally worse at 200,
which is itself useful evidence about this app's real ceiling. See
`/jmeter/results_200users_summary.txt`.

### 6. My Explanation
The AI's plan would have technically run without erroring out, but the ramp-up
math was bad enough that the data wouldn't have actually told me much about "the
system at 200 concurrent users" specifically — it would mostly describe the
system somewhere in the 1-200 range averaged together. Subtle enough that a
first-time JMeter user following this literally probably wouldn't notice their
test wasn't measuring what they thought.

---

## AI Task 9 — Performance Diagnosis with Normal CPU/RAM

### 1. My Prompt
> "p95 latency has risen sharply and some requests are failing, but CPU and RAM
> both look completely normal. Give me hypotheses across the application, the
> database, connection handling, downstream dependencies, NGINX/network, and
> queues/thread pools — and factor in that there was a recent release."

### 2. AI Response
A genuinely broad list: application (inefficient new code path, N+1 queries from
the release), database (lock contention, missing index, connection pool
exhaustion), downstream (a third-party API slowing down), NGINX/network (upstream
keepalive exhaustion, DNS delay to a downstream), queues/thread pools (worker
pool too small for current concurrency, a blocking call tying up a worker thread
that should be async). Suggested checking deploy timing against symptom start as
the first correlation step.

### 3. My Review
This was the AI's strongest answer across all ten tasks — broad, covered every
category asked for, and "check deploy timing first" is the right instinct. My
review here was less about catching errors and more about prioritizing what's
actually testable in this specific project's setup:

- Third-party/downstream slowness and DNS delay: not applicable here at all —
  this project's app is self-contained with SQLite, no external dependencies, no
  DNS in the path. Valid hypotheses in general, just not testable on this system,
  and I said so rather than pretending to test something that structurally
  doesn't apply.
- Worker pool size and DB lock contention were the two hypotheses I could
  actually validate directly, because this project had already produced exactly
  this signature (p95 climbing while CPU/RAM look fine at moderate load, then
  genuinely saturating at higher load) in earlier stress testing and monitoring
  work.

### 4. Correct/Final Solution — prioritized and validated against real data
1. Gunicorn worker count vs. concurrency — cheap to check, matches the symptom
   shape exactly.
2. SQLite write-lock contention on write-path endpoints.
3. Everything else on the AI's list kept as valid categories for a real
   production playbook, explicitly not chased further here since they're not
   reproducible in this project's actual architecture.

### 5. Validation/Evidence
Real prior evidence from this same project shows precisely this "p95 rises, CPU
eventually saturates, then real errors follow" pattern, correlated against live
Prometheus metrics during an actual JMeter run —
`/monitoring/results/correlated_timeline.txt`. That data shows CPU pinning at
100% around t≈12s of sustained load, p95 latency climbing immediately even while
errors were still at 0%, and actual `sqlite3.OperationalError: database is
locked` errors only appearing about 16 seconds after CPU saturation began — a
real, timestamped confirmation of both hypotheses together.

### 6. My Explanation
The interesting nuance here: "CPU/RAM look normal" is often itself the tell. If
CPU were pegged, that's a different, more obvious diagnosis. Normal-looking CPU
with degraded latency usually means the bottleneck is logical (a lock, a pool
size, a queue) rather than physical, and the AI's answer correctly leaned into
that framing instead of repeating generic "check CPU and RAM" advice that
wouldn't even apply to the stated scenario.

---

## AI Task 10 — Release Incident & RCA

### 1. My Prompt
> "5xx errors increased about 10 minutes after a release, and only some API flows
> are affected, not all of them. Walk me through release validation, what
> logs/metrics to pull, how to correlate the change, whether to roll back or fix
> forward, how to communicate this, and what the RCA should cover."

### 2. AI Response
Check the deploy timeline against the error spike, pull error logs filtered to
affected endpoints, check whether affected flows share a common code path or
dependency, default to rollback if the fix isn't immediately obvious and rollback
is fast/safe, communicate status early and often, write an RCA covering timeline,
root cause, impact, and follow-up.

### 3. My Review
Structurally reasonable, but needed sharpening to be usable as an actual incident
playbook rather than a generic outline:

- "Default to rollback if not immediately obvious" needs a concrete decision
  rule, not a vibe — what counts as "not immediately obvious," 2 minutes or 10?
  Without a time-box this just becomes "use your judgment," which isn't decision
  support during a stressful incident.
- It didn't lean nearly hard enough into the specific detail that only some flows
  are affected — that's actually the most diagnostically useful fact in the whole
  scenario (a release that broke everything points to infrastructure/config; one
  that broke some specific flows points strongly at the code change in those
  specific endpoints). The AI treated this almost as an aside rather than the
  headline clue it is.
- Communication advice was generic ("early and often") without saying to whom, at
  what cadence, or through what channel.
- Didn't explicitly say to freeze further deploys during the investigation, which
  should be automatic and stated, not assumed.

### 4. Correct/Final Solution — my own incident plan
1. Immediately freeze further deploys — no additional changes until this is
   understood, so we're not correlating against a moving target.
2. Confirm release-timing correlation precisely — exact deploy completion
   timestamp overlaid against the 5xx-rate graph. Spike within a couple minutes
   of that timestamp means treat the release as primary suspect, not coincidence.
3. Use "only some flows affected" as the main investigative lever — pull the diff
   for exactly those endpoints, check if they share a code path or a newly
   changed helper function. Much faster than broad log-grepping.
4. Decision rule for rollback vs. fix-forward, time-boxed to 15 minutes: if root
   cause isn't identified within 15 minutes of confirmed correlation, roll back
   by default. Fix-forward only if root cause is already confirmed and the fix is
   small, low-risk, and already tested.
5. Communication: initial status message the moment impact is confirmed (not
   when root cause is known — those are different milestones), an update every 15
   minutes while active, a final resolution message once mitigated.
6. RCA, written after resolution: exact timeline (deploy time, first error, first
   alert, mitigation time), the specific code change identified as root cause, why
   it wasn't caught pre-release, customer impact (duration, affected flows,
   rough volume), and concrete follow-up actions with owners — not just "we'll be
   more careful."

### 5. Validation/Evidence
This is a scenario-based task without a live incident to point real logs at, so
I'm upfront that the "evidence" here is the internal consistency of the plan plus
grounding it in real mechanics from this project — the actual
regression-detection work done earlier (where a deliberately introduced
regression was caught by an automated suite and the fix verified against a full
rerun) is the closest real analogue I have to "confirm root cause, fix, verify"
under pressure, and that real transcript is the pattern this RCA plan follows.
See `/RCA.md` for the templated version ready to fill in against a real incident.

### 6. My Explanation
The AI's answer wasn't wrong so much as soft — every step was directionally
correct but missing the specific, decisive detail that turns "advice" into
"something you could actually follow during a real incident without arguing
about it in the moment." The clearest example is the rollback decision: "use
your judgment" sounds fine in a calm document review, but during an actual
incident with people asking for a decision, "roll back if not root-caused within
15 minutes" is the difference between a plan and a platitude.

---

## Overall pattern across all 10 tasks

A theme I noticed doing all of these back to back: the AI is genuinely strong at
breadth — it rarely misses an entire category of consideration, and it's fast at
producing a first draft that would otherwise take real time to write from
scratch. Where it consistently fell short was specificity grounded in the actual
system in front of me — generic best-practice advice, generic thresholds, generic
prioritization — versus what I could get by actually running things, measuring
things, and pointing at real evidence I already had from building this project.
The tasks where I had real prior evidence to check the AI's answer against (5, 6,
9) are the ones I have the most confidence in, precisely because "my review"
wasn't just opinion — it was AI output checked against ground truth.
