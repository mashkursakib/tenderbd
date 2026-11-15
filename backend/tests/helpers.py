"""Shared test helpers (fixtures live in conftest.py)."""

from datetime import datetime, timedelta, timezone

from backend.app.db import AppStore

ADMIN_EMAIL = "admin@example.com"
REFRESH_TOKEN = "test-refresh-token"


def _dt(days: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=days)


LONG_DESCRIPTION = (
    "Construction of a two-storey school building at Dhaka. "
    "The work includes earthwork, brickwork, RCC framing, plastering, "
    "painting and sanitary installation. The contractor shall provide "
    "all materials, labour and equipment. The site is located in "
    "Dhaka district. Completion time is 12 months from the date of "
    "signing the contract."
)

LONG_ELIGIBILITY = (
    "The tenderer must have a valid trade licence and TIN certificate. "
    "The tenderer must have completed at least one similar work worth "
    "BDT 2,000,000 in the last five years. Minimum average annual "
    "turnover of BDT 5,000,000 in the last three years. Liquid assets "
    "or credit line of at least BDT 500,000."
)


def seed_tenders(store: AppStore) -> None:
    """Five tenders covering the explorer's classification axes."""
    store.upsert_tender({
        "tender_id": 1001, "title": "Construction of school building",
        "ref_no": "LGED/2026/001", "status": "Live",
        "proc_nature": "Works", "method": "OTM",
        "ministry": "Ministry of Local Government, Rural Development "
                    "and Co-operatives",
        "department": "Local Government Engineering Department (LGED)",
        "organisation": "LGED", "procuring_entity": "LGED, Dhaka",
        "district": "Dhaka",
        "description": LONG_DESCRIPTION,
        "eligibility_text": LONG_ELIGIBILITY,
        "document_price_bdt": 2000, "emd_bdt": 100000,
        "publish_dt": _dt(-2), "close_dt": _dt(30),
        "doc_last_selling_dt": _dt(28),
    }, detail_fetched=True)
    store.upsert_tender({
        "tender_id": 1002, "title": "Supply of road marking paint",
        "ref_no": "RHD/2026/042", "status": "Live",
        "proc_nature": "Goods", "method": "RFQ",
        "ministry": "Ministry of Road Transport and Bridges",
        "department": "Roads and Highways Department (RHD)",
        "organisation": "RHD", "procuring_entity": "RHD, Chattogram",
        "district": "Chittagong",
        "description": "Supply and delivery of thermoplastic road "
                       "marking paint to the RHD store at Chattogram.",
        "eligibility_text": "Suppliers must be registered with RHD.",
        "document_price_bdt": 1000, "emd_bdt": 50000,
        "publish_dt": _dt(-1), "close_dt": _dt(3),
    }, detail_fetched=True)
    store.upsert_tender({
        "tender_id": 1003, "title": "Cleaning services for office complex",
        "ref_no": "PWD/2026/017", "status": "Live",
        "proc_nature": "Services", "method": "OTM",
        "ministry": "Ministry of Housing and Public Works",
        "department": "Public Works Department (PWD)",
        "organisation": "PWD", "procuring_entity": "PWD, Khulna",
        "district": "Khulna",
        "description": "Annual cleaning services for the PWD office "
                       "complex at Khulna.",
        "publish_dt": _dt(-10), "close_dt": _dt(-2),
    }, detail_fetched=True)
    store.upsert_tender({
        "tender_id": 1004, "title": "Design consultancy for flood embankment",
        "ref_no": "BWDB/2026/009", "status": "Live",
        "proc_nature": "Consultancy Services", "method": "QCBS",
        "ministry": "Ministry of Water Resources",
        "department": "Bangladesh Water Development Board (BWDB)",
        "organisation": "BWDB", "procuring_entity": "BWDB, Sylhet",
        "district": "Sylhet",
        "description": "Consultancy services for the detailed design "
                       "of a flood protection embankment.",
        "eligibility_text": "Firms must have completed similar design "
                            "consultancy assignments.",
        "document_price_bdt": 5000, "emd_bdt": 200000,
        "publish_dt": _dt(-5), "close_dt": _dt(60),
    }, detail_fetched=True)
    # Not yet enriched: detail_fetched_at stays NULL (enrich tests).
    store.upsert_tender({
        "tender_id": 1005, "title": "Supply of electric poles",
        "ref_no": "BREB/2026/003", "status": "Live",
        "proc_nature": "Works", "method": "OTM",
        "ministry": "Ministry of Power, Energy and Mineral Resources",
        "department": "Bangladesh Rural Electrification Board (BREB)",
        "organisation": "BREB", "procuring_entity": "BREB, Rajshahi",
        "district": "Rajshahi",
        "description": "Poles.",
        "document_price_bdt": 1500, "emd_bdt": 10000,
        "publish_dt": _dt(-1), "close_dt": _dt(2),
    })


def signup(client, email, password="password123", name="Test User"):
    resp = client.post("/api/v1/auth/signup", json={
        "name": name, "email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def make_user(client, email, password="password123", name="Test User"):
    data = signup(client, email, password, name)
    return data["user"], data["token"]


def set_plan(store, user_id: int, plan: str) -> None:
    store.execute(
        "INSERT INTO subscriptions (user_id, plan, payment_method, "
        "status, updated_at) VALUES (%(user_id)s, %(plan)s, 'Test', "
        "'Active', %(now)s) "
        "ON CONFLICT (user_id) DO UPDATE SET plan = EXCLUDED.plan",
        {"user_id": user_id, "plan": plan,
         "now": store.dt(datetime.now(timezone.utc))})


def make_premium_user(client, store, email):
    user, token = make_user(client, email)
    set_plan(store, user["id"], "Premium")
    return user, token


def make_pro_user(client, store, email):
    user, token = make_user(client, email)
    set_plan(store, user["id"], "Pro")
    return user, token


def make_admin(client, store, email=ADMIN_EMAIL):
    user, token = make_user(client, email, name="Admin User")
    assert user["is_admin"] is True
    return user, token


def save_profile(client, token, **overrides):
    body = {
        "company_name": "Test Builders Ltd",
        "categories": "Works, Construction",
        "annual_turnover_bdt": 5000000,
        "liquid_assets_bdt": 200000,
        "similar_works": [
            {"title": "School building", "value_bdt": 3000000,
             "category": "Works"},
        ],
    }
    body.update(overrides)
    resp = client.put("/api/v1/profile/company", json=body,
                      headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    return resp.json()
