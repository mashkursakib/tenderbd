"""Document vault tests: upload (Premium+), 6 MB cap, download,
delete, owner-only access."""

from backend.tests.helpers import (auth_headers, make_premium_user, make_user)


def _upload(client, token, content=b"fake-pdf-bytes", name="licence.pdf",
            doc_type="Trade licence"):
    return client.post("/api/v1/documents",
                       files={"file": (name, content,
                                       "application/pdf")},
                       data={"doc_type": doc_type},
                       headers=auth_headers(token))


def test_upload_and_list(client, store):
    _, token = make_premium_user(client, store, "doc@example.com")
    resp = _upload(client, token)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["doc_type"] == "Trade licence"
    assert body["file_name"] == "licence.pdf"
    assert body["size_bytes"] == len(b"fake-pdf-bytes")
    assert body["status"] == "Declared"
    assert "data" not in body
    docs = client.get("/api/v1/documents",
                      headers=auth_headers(token)).json()
    assert len(docs) == 1
    assert docs[0]["id"] == body["id"]


def test_upload_requires_premium(client, store):
    _, token = make_user(client, "docfree@example.com")
    resp = _upload(client, token)
    assert resp.status_code == 403
    assert "Premium feature" in resp.json()["detail"]


def test_upload_invalid_doc_type(client, store):
    _, token = make_premium_user(client, store, "docbad@example.com")
    resp = _upload(client, token, doc_type="Passport")
    assert resp.status_code == 400


def test_upload_6mb_cap(client, store):
    _, token = make_premium_user(client, store, "docbig@example.com")
    big = b"x" * (6 * 1024 * 1024 + 1)
    resp = _upload(client, token, content=big, name="big.pdf")
    assert resp.status_code == 400
    assert "6 MB" in resp.json()["detail"]
    # Exactly 6 MB is allowed.
    exact = b"x" * (6 * 1024 * 1024)
    resp = _upload(client, token, content=exact, name="exact.pdf")
    assert resp.status_code == 200, resp.text


def test_download_round_trip(client, store):
    _, token = make_premium_user(client, store, "docdl@example.com")
    doc = _upload(client, token, content=b"hello-bytes").json()
    resp = client.get(f"/api/v1/documents/{doc['id']}/download",
                      headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.content == b"hello-bytes"
    assert resp.headers["content-type"] == "application/pdf"


def test_download_owner_only(client, store):
    _, token1 = make_premium_user(client, store, "docown1@example.com")
    _, token2 = make_premium_user(client, store, "docown2@example.com")
    doc = _upload(client, token1).json()
    resp = client.get(f"/api/v1/documents/{doc['id']}/download",
                      headers=auth_headers(token2))
    assert resp.status_code == 404
    resp = client.delete(f"/api/v1/documents/{doc['id']}",
                         headers=auth_headers(token2))
    assert resp.status_code == 404
    # Owner can still see it.
    assert client.get("/api/v1/documents",
                      headers=auth_headers(token1)).json() != []


def test_delete_document(client, store):
    _, token = make_premium_user(client, store, "docdel@example.com")
    doc = _upload(client, token).json()
    resp = client.delete(f"/api/v1/documents/{doc['id']}",
                         headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json() == {}
    assert client.get("/api/v1/documents",
                      headers=auth_headers(token)).json() == []
    assert client.get(f"/api/v1/documents/{doc['id']}/download",
                      headers=auth_headers(token)).status_code == 404


def test_documents_list_not_plan_gated(client, store):
    # Free users can list/download/delete (upload is the gated part).
    _, token = make_user(client, "docfree2@example.com")
    assert client.get("/api/v1/documents",
                      headers=auth_headers(token)).status_code == 200
