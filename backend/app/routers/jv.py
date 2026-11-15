"""JV room (SPEC.md section 4).

Browsing posts is public. Creating posts, expressing interest, opening
rooms, and listing/sending messages are Pro only. Rooms have no
membership check and interests have no list/read surface, exactly as
in the prototype (known gaps, preserved deliberately).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import auth, config
from ..db import AppStore, get_store, now_utc

router = APIRouter(prefix="/jv", tags=["jv"])


class PostBody(BaseModel):
    title: str = Field(min_length=4, max_length=200)
    need_description: str = Field(min_length=4, max_length=2000)
    looking_for: str | None = Field(default=None, max_length=500)
    share_offered: str | None = Field(default=None, max_length=200)
    tender_id: int | None = None


class InterestBody(BaseModel):
    message: str = Field(min_length=2, max_length=1000)


class MessageBody(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


def _poster(store: AppStore, user_id: int) -> dict:
    user = auth.get_user_by_id(store, user_id) or {}
    company = store.fetchone(
        "SELECT company_name, categories, annual_turnover_bdt "
        "FROM companies WHERE user_id = %(user_id)s",
        {"user_id": user_id})
    return {
        "name": user.get("name"),
        "company_name": (company or {}).get("company_name"),
        "categories": (company or {}).get("categories"),
        "turnover": (company or {}).get("annual_turnover_bdt"),
    }


def _serialize_post(store: AppStore, post: dict) -> dict:
    count = store.fetchone(
        "SELECT COUNT(*) AS n FROM jv_interests WHERE post_id = %(post_id)s",
        {"post_id": post["id"]})
    room = store.fetchone(
        "SELECT id FROM jv_rooms WHERE post_id = %(post_id)s",
        {"post_id": post["id"]})
    out = dict(post)
    out["poster"] = _poster(store, post["user_id"])
    out["interest_count"] = count["n"]
    out["room_id"] = room["id"] if room else None
    return out


def _get_post_or_404(store: AppStore, post_id: int) -> dict:
    post = store.fetchone("SELECT * FROM jv_posts WHERE id = %(id)s",
                          {"id": post_id})
    if post is None:
        raise HTTPException(status_code=404, detail="JV post not found.")
    return post


def _get_room_or_404(store: AppStore, room_id: int) -> dict:
    room = store.fetchone("SELECT * FROM jv_rooms WHERE id = %(id)s",
                          {"id": room_id})
    if room is None:
        raise HTTPException(status_code=404, detail="JV room not found.")
    return room


@router.get("/posts")
def list_posts(store: AppStore = Depends(get_store)):
    rows = store.fetchall(
        "SELECT * FROM jv_posts ORDER BY created_at DESC, id DESC LIMIT 100")
    return [_serialize_post(store, row) for row in rows]


@router.post("/posts")
def create_post(body: PostBody,
                user: dict = Depends(auth.get_current_user),
                store: AppStore = Depends(get_store)):
    auth.require_plan(store, user, "Pro")
    tender_title = None
    if body.tender_id is not None:
        tender = store.get_tender(body.tender_id)
        if tender is None:
            raise HTTPException(status_code=404, detail="Tender not found.")
        tender_title = tender.get("title")
    post_id = store.insert(
        "INSERT INTO jv_posts (user_id, tender_id, tender_title, title, "
        "need_description, looking_for, share_offered, status, "
        "created_at) VALUES (%(user_id)s, %(tender_id)s, "
        "%(tender_title)s, %(title)s, %(need_description)s, "
        "%(looking_for)s, %(share_offered)s, 'Open', %(created_at)s)",
        {"user_id": user["id"], "tender_id": body.tender_id,
         "tender_title": tender_title, "title": body.title.strip(),
         "need_description": body.need_description.strip(),
         "looking_for": body.looking_for,
         "share_offered": body.share_offered,
         "created_at": store.dt(now_utc())})
    post = store.fetchone("SELECT * FROM jv_posts WHERE id = %(id)s",
                          {"id": post_id})
    return _serialize_post(store, post)


@router.post("/posts/{post_id}/interest")
def express_interest(post_id: int, body: InterestBody,
                     user: dict = Depends(auth.get_current_user),
                     store: AppStore = Depends(get_store)):
    auth.require_plan(store, user, "Pro")
    post = _get_post_or_404(store, post_id)
    if post["user_id"] == user["id"]:
        raise HTTPException(status_code=400, detail="This is your own post.")
    store.insert(
        "INSERT INTO jv_interests (post_id, user_id, message, created_at) "
        "VALUES (%(post_id)s, %(user_id)s, %(message)s, %(created_at)s)",
        {"post_id": post_id, "user_id": user["id"],
         "message": body.message.strip(),
         "created_at": store.dt(now_utc())})
    return {}


@router.post("/posts/{post_id}/room")
def open_room(post_id: int,
              user: dict = Depends(auth.get_current_user),
              store: AppStore = Depends(get_store)):
    auth.require_plan(store, user, "Pro")
    post = _get_post_or_404(store, post_id)
    room = store.fetchone(
        "SELECT * FROM jv_rooms WHERE post_id = %(post_id)s",
        {"post_id": post_id})
    if room is not None:
        return room
    room_id = store.insert(
        "INSERT INTO jv_rooms (post_id, title, created_at) "
        "VALUES (%(post_id)s, %(title)s, %(created_at)s)",
        {"post_id": post_id, "title": post["title"],
         "created_at": store.dt(now_utc())})
    return store.fetchone("SELECT * FROM jv_rooms WHERE id = %(id)s",
                          {"id": room_id})


@router.get("/rooms/{room_id}/messages")
def list_messages(room_id: int,
                  user: dict | None = Depends(auth.get_optional_user),
                  store: AppStore = Depends(get_store)):
    if user is None:
        return {"locked": True, "messages": []}
    plan = auth.get_plan(store, user["id"])
    if config.PLAN_RANK.get(plan, 0) < config.PLAN_RANK["Pro"]:
        return {"locked": True, "messages": []}
    _get_room_or_404(store, room_id)
    rows = store.fetchall(
        "SELECT * FROM jv_messages WHERE room_id = %(room_id)s "
        "ORDER BY created_at ASC, id ASC LIMIT 200",
        {"room_id": room_id})
    return {"messages": rows}


@router.post("/rooms/{room_id}/messages")
def send_message(room_id: int, body: MessageBody,
                 user: dict = Depends(auth.get_current_user),
                 store: AppStore = Depends(get_store)):
    auth.require_plan(store, user, "Pro")
    _get_room_or_404(store, room_id)
    message_id = store.insert(
        "INSERT INTO jv_messages (room_id, user_id, sender_name, body, "
        "created_at) VALUES (%(room_id)s, %(user_id)s, %(sender_name)s, "
        "%(body)s, %(created_at)s)",
        {"room_id": room_id, "user_id": user["id"],
         "sender_name": user["name"], "body": body.body.strip(),
         "created_at": store.dt(now_utc())})
    return store.fetchone("SELECT * FROM jv_messages WHERE id = %(id)s",
                          {"id": message_id})
