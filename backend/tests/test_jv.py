"""JV room tests: posts, interest, rooms, messages, locked responses."""

from backend.tests.helpers import (auth_headers, make_premium_user, make_pro_user,
                      make_user, save_profile)


def _post_body(**overrides):
    body = {"title": "Need a JV partner for school project",
            "need_description": "We need a partner with road and "
                                "building experience.",
            "looking_for": "A firm with similar works",
            "share_offered": "40%"}
    body.update(overrides)
    return body


def _create_post(client, token, **overrides):
    resp = client.post("/api/v1/jv/posts", json=_post_body(**overrides),
                       headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_list_posts_public(client, store):
    _, token = make_pro_user(client, store, "poster@example.com")
    save_profile(client, token)
    post = _create_post(client, token, tender_id=1001)
    assert post["tender_title"] == "Construction of school building"
    assert post["status"] == "Open"
    assert post["interest_count"] == 0
    assert post["room_id"] is None
    assert post["poster"]["company_name"] == "Test Builders Ltd"
    assert post["poster"]["turnover"] == 5000000
    body = client.get("/api/v1/jv/posts").json()
    assert len(body) == 1
    assert body[0]["id"] == post["id"]


def test_create_post_validation(client, store):
    _, token = make_pro_user(client, store, "valid@example.com")
    resp = client.post("/api/v1/jv/posts",
                       json={"title": "No", "need_description": "Too "
                             "short a title."},
                       headers=auth_headers(token))
    assert resp.status_code == 422
    resp = client.post("/api/v1/jv/posts",
                       json=_post_body(tender_id=9999999),
                       headers=auth_headers(token))
    assert resp.status_code == 404


def test_interest_flow_and_count(client, store):
    _, poster_token = make_pro_user(client, store, "poster2@example.com")
    _, other_token = make_pro_user(client, store, "other@example.com")
    post = _create_post(client, poster_token)
    resp = client.post(f"/api/v1/jv/posts/{post['id']}/interest",
                       json={"message": "We are interested."},
                       headers=auth_headers(other_token))
    assert resp.status_code == 200
    assert resp.json() == {}
    # No duplicate check in the prototype: a second interest is allowed.
    resp = client.post(f"/api/v1/jv/posts/{post['id']}/interest",
                       json={"message": "Following up."},
                       headers=auth_headers(other_token))
    assert resp.status_code == 200
    body = client.get("/api/v1/jv/posts").json()
    assert body[0]["interest_count"] == 2


def test_interest_own_post_rejected(client, store):
    _, token = make_pro_user(client, store, "ownpost@example.com")
    post = _create_post(client, token)
    resp = client.post(f"/api/v1/jv/posts/{post['id']}/interest",
                       json={"message": "Me too."},
                       headers=auth_headers(token))
    assert resp.status_code == 400
    assert resp.json()["detail"] == "This is your own post."


def test_interest_requires_pro(client, store):
    _, poster_token = make_pro_user(client, store, "poster3@example.com")
    _, free_token = make_user(client, "freeposter@example.com")
    post = _create_post(client, poster_token)
    resp = client.post(f"/api/v1/jv/posts/{post['id']}/interest",
                       json={"message": "Interested."},
                       headers=auth_headers(free_token))
    assert resp.status_code == 403
    assert "Pro feature" in resp.json()["detail"]


def test_room_one_per_post(client, store):
    _, poster_token = make_pro_user(client, store, "poster4@example.com")
    _, other_token = make_pro_user(client, store, "other4@example.com")
    post = _create_post(client, poster_token)
    room1 = client.post(f"/api/v1/jv/posts/{post['id']}/room",
                        headers=auth_headers(poster_token)).json()
    room2 = client.post(f"/api/v1/jv/posts/{post['id']}/room",
                        headers=auth_headers(other_token)).json()
    assert room1["id"] == room2["id"]
    assert room1["post_id"] == post["id"]
    assert room1["title"] == post["title"]
    body = client.get("/api/v1/jv/posts").json()
    assert body[0]["room_id"] == room1["id"]


def test_messages_locked_for_unsigned_and_non_pro(client, store):
    _, poster_token = make_pro_user(client, store, "poster5@example.com")
    _, free_token = make_user(client, "free5@example.com")
    _, prem_token = make_premium_user(client, store, "prem5@example.com")
    post = _create_post(client, poster_token)
    room = client.post(f"/api/v1/jv/posts/{post['id']}/room",
                       headers=auth_headers(poster_token)).json()
    client.post(f"/api/v1/jv/rooms/{room['id']}/messages",
                json={"body": "Hello partner."},
                headers=auth_headers(poster_token))
    # Unsigned: 200 with locked:true.
    resp = client.get(f"/api/v1/jv/rooms/{room['id']}/messages")
    assert resp.status_code == 200
    assert resp.json() == {"locked": True, "messages": []}
    # Free and Premium: same locked response.
    for token in (free_token, prem_token):
        resp = client.get(f"/api/v1/jv/rooms/{room['id']}/messages",
                          headers=auth_headers(token))
        assert resp.json() == {"locked": True, "messages": []}
    # Pro sees the messages.
    resp = client.get(f"/api/v1/jv/rooms/{room['id']}/messages",
                      headers=auth_headers(poster_token))
    assert resp.status_code == 200
    assert "locked" not in resp.json()
    assert len(resp.json()["messages"]) == 1
    assert resp.json()["messages"][0]["body"] == "Hello partner."
    assert resp.json()["messages"][0]["sender_name"] == "Test User"


def test_send_message_requires_pro_and_room(client, store):
    _, poster_token = make_pro_user(client, store, "poster6@example.com")
    _, free_token = make_user(client, "free6@example.com")
    post = _create_post(client, poster_token)
    room = client.post(f"/api/v1/jv/posts/{post['id']}/room",
                       headers=auth_headers(poster_token)).json()
    resp = client.post(f"/api/v1/jv/rooms/{room['id']}/messages",
                       json={"body": "Hi."},
                       headers=auth_headers(free_token))
    assert resp.status_code == 403
    resp = client.post("/api/v1/jv/rooms/999999/messages",
                       json={"body": "Hi."},
                       headers=auth_headers(poster_token))
    assert resp.status_code == 404
    resp = client.post(f"/api/v1/jv/rooms/{room['id']}/messages",
                       json={"body": "First message."},
                       headers=auth_headers(poster_token))
    assert resp.status_code == 200
    assert resp.json()["sender_name"] == "Test User"
    assert resp.json()["room_id"] == room["id"]


def test_messages_oldest_first(client, store):
    _, token = make_pro_user(client, store, "order@example.com")
    post = _create_post(client, token)
    room = client.post(f"/api/v1/jv/posts/{post['id']}/room",
                       headers=auth_headers(token)).json()
    for text in ("one", "two", "three"):
        client.post(f"/api/v1/jv/rooms/{room['id']}/messages",
                    json={"body": text}, headers=auth_headers(token))
    body = client.get(f"/api/v1/jv/rooms/{room['id']}/messages",
                      headers=auth_headers(token)).json()
    assert [m["body"] for m in body["messages"]] == ["one", "two", "three"]
