import os
import sys
import tempfile
import pytest
 
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
 
 
@pytest.fixture()
def client():
    """Fresh app + fresh temp SQLite DB for every test."""
    db_fd, db_path = tempfile.mkstemp()
    os.environ["DATABASE_PATH"] = db_path
 
    import importlib
    import app as app_module
    importlib.reload(app_module)  # re-init with the fresh DB path
    app_module.init_db()
 
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c
 
    os.close(db_fd)
    os.unlink(db_path)
 
 
def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"
 
 
def test_list_users_returns_seeded_data(client):
    resp = client.get("/users")
    assert resp.status_code == 200
    users = resp.get_json()
    assert len(users) >= 8  # seed data has 10 rows
 
 
def test_get_single_user_positive(client):
    resp = client.get("/users/1")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["id"] == 1
    assert "email" in body
 
 
def test_get_user_not_found(client):
    resp = client.get("/users/99999")
    assert resp.status_code == 404
 
 
def test_get_user_invalid_id_format(client):
    resp = client.get("/users/not-a-number")
    assert resp.status_code == 400
 
 
def test_create_user_positive(client):
    resp = client.post("/users", json={
        "name": "Test User",
        "email": "test.user@example.com",
        "status": "active"
    })
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["name"] == "Test User"
 
 
def test_create_user_invalid_email(client):
    resp = client.post("/users", json={
        "name": "Bad Email",
        "email": "not-an-email",
        "status": "active"
    })
    assert resp.status_code == 400
 
 
def test_create_user_duplicate_email(client):
    client.post("/users", json={
        "name": "First", "email": "dup@example.com", "status": "active"
    })
    resp = client.post("/users", json={
        "name": "Second", "email": "dup@example.com", "status": "active"
    })
    assert resp.status_code == 409
 
 
def test_update_user_positive(client):
    resp = client.put("/users/2", json={"status": "inactive"})
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "inactive"
 
 
def test_update_user_not_found(client):
    resp = client.put("/users/99999", json={"status": "active"})
    assert resp.status_code == 404
 
 
def test_health_status_code_is_correct(client):
    """FIXED: corrected assertion to match the real, correct behavior
    (200 OK), resolving the deliberate failure introduced earlier to
    demonstrate the CI quality gate."""
    resp = client.get("/health")
    assert resp.status_code == 200
 
 
def test_sql_injection_style_name_is_stored_safely(client):
    """A name containing SQL syntax should be stored as harmless text,
    not executed, and must not break the table."""
    resp = client.post("/users", json={
        "name": "Robert'); DROP TABLE users;--",
        "email": "sqltest@example.com",
        "status": "active"
    })
    assert resp.status_code == 201
    # table must still be queryable and intact
    listing = client.get("/users")
    assert listing.status_code == 200
    assert len(listing.get_json()) > 0
