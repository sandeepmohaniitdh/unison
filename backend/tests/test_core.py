"""Health check, error format, pagination, time handling and file checks."""

import io
from datetime import datetime

import pytest

from app.core.errors import AppError
from app.core.storage import LocalStorage
from app.core.time import IST, to_ist, to_utc
from tests.conftest import as_user
from tests.factories import PDF_BYTES, make_user


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "ok", "version": "1.0.0"}
    assert r.headers["X-Request-ID"]


def test_unknown_route_uses_standard_error_body(client):
    r = client.get("/api/v1/nope", headers={"X-Request-ID": "abc123"})
    assert r.status_code == 404
    assert r.json() == {"error": {"code": "NOT_FOUND", "message": "Not Found", "details": None, "request_id": "abc123"}}


def test_validation_error_lists_fields(client):
    r = client.post("/api/v1/auth/login", json={"email": "not-an-email"})
    assert r.status_code == 422
    body = r.json()["error"]
    assert body["code"] == "VALIDATION_ERROR"
    fields = {d["field"] for d in body["details"]}
    assert {"email", "password"} <= fields


def test_protected_route_needs_login(client):
    r = client.get("/api/v1/users/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "NOT_AUTHENTICATED"


def test_demo_header_with_unknown_email(client):
    r = client.get("/api/v1/users/me", headers=as_user("nobody@example.com"))
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "DEMO_USER_UNKNOWN"


def test_pagination_shape_and_limits(client, db):
    admin = make_user(db, "admin")
    for i in range(3):
        make_user(db, "student", name=f"Paged Person {i}")
    r = client.get("/api/v1/admin/users?q=Paged&page=1&size=2", headers=as_user(admin))
    assert r.status_code == 200
    body = r.json()
    assert (body["page"], body["size"], body["total"], len(body["items"])) == (1, 2, 3, 2)
    assert client.get("/api/v1/admin/users?size=101", headers=as_user(admin)).status_code == 422
    assert client.get("/api/v1/admin/users?page=0", headers=as_user(admin)).status_code == 422


def test_time_conversion_ist():
    naive_ist = datetime(2026, 11, 5, 23, 59, 59)
    utc = to_utc(naive_ist)
    assert utc == datetime(2026, 11, 5, 18, 29, 59)
    assert to_ist(utc).isoformat() == "2026-11-05T23:59:59+05:30"
    assert to_utc(datetime(2026, 11, 5, 18, 29, 59, tzinfo=IST)) == datetime(2026, 11, 5, 12, 59, 59)


def test_storage_checks_extension_signature_and_size(tmp_path):
    store = LocalStorage(str(tmp_path))
    ok = store.save(io.BytesIO(PDF_BYTES), "Report final.pdf", {".pdf"}, 1024)
    assert ok.mime_type == "application/pdf" and ok.size_bytes == len(PDF_BYTES) and len(ok.key) == 32
    assert store.path(ok.key).read_bytes() == PDF_BYTES

    with pytest.raises(AppError) as e:
        store.save(io.BytesIO(b"<html>"), "page.html", {".pdf"}, 1024)
    assert e.value.code == "FILE_TYPE_NOT_ALLOWED"
    with pytest.raises(AppError) as e:
        store.save(io.BytesIO(b"MZ fake exe"), "report.pdf", {".pdf"}, 1024)
    assert e.value.code == "FILE_TYPE_MISMATCH"
    with pytest.raises(AppError) as e:
        store.save(io.BytesIO(b"%PDF-" + b"x" * 2000), "big.pdf", {".pdf"}, 1024)
    assert e.value.status == 413
    with pytest.raises(AppError) as e:
        store.save(io.BytesIO(b""), "empty.pdf", {".pdf"}, 1024)
    assert e.value.code == "FILE_EMPTY"
    assert len([p for p in tmp_path.rglob("*") if p.is_file()]) == 1  # rejected files are removed


def test_openapi_has_every_module(client):
    spec = client.get("/api/v1/openapi.json").json()
    tags = {tag for path in spec["paths"].values() for op in path.values() for tag in op.get("tags", [])}
    assert {
        "auth",
        "users",
        "courses",
        "invitations",
        "resources",
        "assignments",
        "teams",
        "submissions",
        "reviews",
        "ai",
        "notifications",
        "admin",
        "health",
    } <= tags
    # Every error response of every operation uses the standard error body.
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            assert "422" in op["responses"], (method, path)
            for code, response in op["responses"].items():
                if code.startswith(("4", "5")):
                    ref = response["content"]["application/json"]["schema"]["$ref"]
                    assert ref.endswith("/ErrorBody"), (method, path, code)
    assert "HTTPValidationError" not in spec["components"]["schemas"]
    ids = [op["operationId"] for ops in spec["paths"].values() for op in ops.values()]
    assert len(ids) == len(set(ids))


VERBS = {
    "get",
    "create",
    "add",
    "delete",
    "remove",
    "update",
    "edit",
    "publish",
    "archive",
    "extend",
    "leave",
    "move",
    "accept",
    "decline",
    "approve",
    "reject",
    "release",
    "read",
    "download",
    "export",
    "restore",
    "suspend",
    "reinstate",
    "resend",
    "submit",
    "upload",
    "cancel",
    "verify",
    "start",
    "make-primary",
}
# Logging in and out are the usual exceptions (as in the course's example API).
AUTH_ACTIONS = {"/api/v1/auth/register", "/api/v1/auth/login", "/api/v1/auth/logout"}


def test_paths_are_nouns_and_every_list_is_paginated(client):
    spec = client.get("/api/v1/openapi.json").json()
    for path, ops in spec["paths"].items():
        if path not in AUTH_ACTIONS:
            words = {w for segment in path.split("/") for w in [segment, *segment.split("-")]}
            assert not words & VERBS, path
        get = ops.get("get")
        if get:
            schema = get["responses"].get("200", {}).get("content", {}).get("application/json", {}).get("schema", {})
            assert schema.get("type") != "array", f"{path} returns a bare list; use Page"
            if schema.get("$ref", "").split("/")[-1].startswith("Page_"):
                names = {p["name"] for p in get.get("parameters", [])}
                assert {"page", "size"} <= names, path
