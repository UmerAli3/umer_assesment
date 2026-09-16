import os
import re
import time
import requests
import pytest
 
BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:5000")
MAX_RESPONSE_TIME = 0.5  # seconds
REQUIRED_USER_FIELDS = {"id", "name", "email", "status"}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
 
 
def _assert_json_content_type(resp):
    assert "application/json" in resp.headers.get("Content-Type", ""), \
        f"Expected JSON content-type, got: {resp.headers.get('Content-Type')}"
 
 
def _assert_fast(resp, limit=MAX_RESPONSE_TIME):
    assert resp.elapsed.total_seconds() < limit, \
        f"Response took {resp.elapsed.total_seconds():.3f}s, exceeds {limit}s limit"
 
 
def _assert_user_schema(user_dict):
    assert set(user_dict.keys()) == REQUIRED_USER_FIELDS, \
        f"User object missing/extra fields. Got keys: {set(user_dict.keys())}"
    assert isinstance(user_dict["id"], int)
    assert isinstance(user_dict["name"], str) and user_dict["name"]
    assert EMAIL_RE.match(user_dict["email"]), f"Invalid email format: {user_dict['email']}"
    assert user_dict["status"] in {"active", "inactive", "pending"}
 
 
# ============================================================
# 1. HEALTH / SMOKE
# ============================================================
 
def test_01_health_status_code():
    resp = requests.get(f"{BASE_URL}/health")
    assert resp.status_code == 200
 
 
def test_02_health_content_type():
    resp = requests.get(f"{BASE_URL}/health")
    _assert_json_content_type(resp)
 
 
def test_03_health_body_schema():
    resp = requests.get(f"{BASE_URL}/health")
    body = resp.json()
    assert "status" in body and "db" in body
    assert body["status"] == "ok"
 
 
def test_04_health_response_time():
    resp = requests.get(f"{BASE_URL}/health")
    _assert_fast(resp)
 
 
# ============================================================
# 2. GET /users - LIST
# ============================================================
 
def test_05_list_users_status_and_type():
    resp = requests.get(f"{BASE_URL}/users")
    assert resp.status_code == 200
    _assert_json_content_type(resp)
 
 
def test_06_list_users_schema_each_row():
    resp = requests.get(f"{BASE_URL}/users")
    users = resp.json()
    assert isinstance(users, list) and len(users) > 0
    for u in users:
        _assert_user_schema(u)
 
 
def test_07_list_users_filter_by_status():
    resp = requests.get(f"{BASE_URL}/users", params={"status": "active"})
    assert resp.status_code == 200
    for u in resp.json():
        assert u["status"] == "active"
 
 
# ============================================================
# 3. GET /users/<id>
# ============================================================
 
def test_08_get_user_positive():
    resp = requests.get(f"{BASE_URL}/users/1")
    assert resp.status_code == 200
    _assert_user_schema(resp.json())
    assert resp.json()["id"] == 1
 
 
def test_09_get_user_not_found():
    resp = requests.get(f"{BASE_URL}/users/999999")
    assert resp.status_code == 404
    assert "error" in resp.json()
 
 
def test_10_get_user_invalid_id_format():
    resp = requests.get(f"{BASE_URL}/users/not-a-number")
    assert resp.status_code == 400
 
 
# ============================================================
# 4. POST /users - CREATE
# ============================================================
 
def test_11_create_user_positive():
    resp = requests.post(f"{BASE_URL}/users", json={
        "name": "Regression Test User",
        "email": f"regression.{int(time.time()*1000)}@example.com",
        "status": "active"
    })
    assert resp.status_code == 201
    _assert_user_schema(resp.json())
    _assert_fast(resp)
 
 
def test_12_create_user_missing_name():
    resp = requests.post(f"{BASE_URL}/users", json={
        "email": f"noname.{int(time.time()*1000)}@example.com",
        "status": "active"
    })
    assert resp.status_code == 400
    assert "error" in resp.json()
 
 
def test_13_create_user_invalid_email():
    resp = requests.post(f"{BASE_URL}/users", json={
        "name": "Bad Email",
        "email": "not-an-email",
        "status": "active"
    })
    assert resp.status_code == 400
 
 
def test_14_create_user_duplicate_email():
    email = f"dupcheck.{int(time.time()*1000)}@example.com"
    r1 = requests.post(f"{BASE_URL}/users", json={"name": "First", "email": email, "status": "active"})
    assert r1.status_code == 201
    r2 = requests.post(f"{BASE_URL}/users", json={"name": "Second", "email": email, "status": "active"})
    assert r2.status_code == 409
 
 
# ============================================================
# 5. PUT /users/<id> - UPDATE
# ============================================================
 
def test_15_update_user_positive():
    resp = requests.put(f"{BASE_URL}/users/2", json={"status": "inactive"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "inactive"
    # put it back for test independence
    requests.put(f"{BASE_URL}/users/2", json={"status": "active"})
 
 
def test_16_update_user_not_found():
    resp = requests.put(f"{BASE_URL}/users/999999", json={"status": "active"})
    assert resp.status_code == 404
 
 
# ============================================================
# 6. Unsupported methods / integration checks
# ============================================================
 
def test_17_delete_method_not_allowed():
    resp = requests.delete(f"{BASE_URL}/users/1")
    assert resp.status_code == 405
 
 
def test_18_integration_create_then_get():
    email = f"integration.{int(time.time()*1000)}@example.com"
    created = requests.post(f"{BASE_URL}/users", json={
        "name": "Integration Check", "email": email, "status": "active"
    }).json()
    fetched = requests.get(f"{BASE_URL}/users/{created['id']}").json()
    assert fetched == created
