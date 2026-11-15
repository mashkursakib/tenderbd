"""Document vault (SPEC.md section 4).

Upload is Premium+; list/download/delete are NOT plan-gated.
File bytes are stored in the DB (BYTEA / BLOB), 6 MB cap, status
'Declared'.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from .. import auth, config
from ..db import AppStore, get_store, now_utc

router = APIRouter(prefix="/documents", tags=["documents"])


def _public_doc(row: dict) -> dict:
    return {key: value for key, value in row.items() if key != "data"}


def _get_owned_doc(store: AppStore, doc_id: int, user_id: int) -> dict:
    row = store.fetchone(
        "SELECT * FROM documents WHERE id = %(id)s", {"id": doc_id})
    if row is None or row["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Document not found.")
    return row


@router.get("")
def list_documents(user: dict = Depends(auth.get_current_user),
                   store: AppStore = Depends(get_store)):
    rows = store.fetchall(
        "SELECT id, user_id, doc_type, file_name, mime_type, size_bytes, "
        "status, uploaded_at FROM documents WHERE user_id = %(user_id)s "
        "ORDER BY uploaded_at DESC, id DESC",
        {"user_id": user["id"]})
    return rows


@router.post("")
async def upload_document(
        file: UploadFile = File(...),
        doc_type: str = Form(...),
        user: dict = Depends(auth.get_current_user),
        store: AppStore = Depends(get_store)):
    auth.require_plan(store, user, "Premium")
    if doc_type not in config.DOC_TYPES:
        raise HTTPException(status_code=400, detail="Invalid document type.")
    data = await file.read()
    if len(data) > config.MAX_DOCUMENT_BYTES:
        raise HTTPException(
            status_code=400,
            detail="File is too large. The maximum size is 6 MB.")
    doc_id = store.insert(
        "INSERT INTO documents (user_id, doc_type, file_name, mime_type, "
        "size_bytes, data, status, uploaded_at) "
        "VALUES (%(user_id)s, %(doc_type)s, %(file_name)s, %(mime_type)s, "
        "%(size_bytes)s, %(data)s, 'Declared', %(uploaded_at)s)",
        {"user_id": user["id"], "doc_type": doc_type,
         "file_name": file.filename or "upload",
         "mime_type": file.content_type or "application/octet-stream",
         "size_bytes": len(data), "data": data,
         "uploaded_at": store.dt(now_utc())})
    row = store.fetchone(
        "SELECT id, user_id, doc_type, file_name, mime_type, size_bytes, "
        "status, uploaded_at FROM documents WHERE id = %(id)s",
        {"id": doc_id})
    return row


@router.get("/{doc_id}/download")
def download_document(doc_id: int,
                      user: dict = Depends(auth.get_current_user),
                      store: AppStore = Depends(get_store)):
    row = _get_owned_doc(store, doc_id, user["id"])
    return Response(
        content=bytes(row["data"]),
        media_type=row.get("mime_type") or "application/octet-stream",
        headers={"Content-Disposition":
                 f'attachment; filename="{row["file_name"]}"'})


@router.delete("/{doc_id}")
def delete_document(doc_id: int,
                    user: dict = Depends(auth.get_current_user),
                    store: AppStore = Depends(get_store)):
    _get_owned_doc(store, doc_id, user["id"])
    store.execute("DELETE FROM documents WHERE id = %(id)s",
                  {"id": doc_id})
    return {}
