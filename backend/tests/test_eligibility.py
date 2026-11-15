"""Eligibility scoring tests: all four checks, verdict thresholds,
no-profile case (SPEC.md section 7)."""

from backend.app.services.eligibility import NOTE, evaluate, verdict_for
from backend.tests.helpers import (auth_headers, make_premium_user, save_profile)


def _tender(**overrides):
    tender = {"tender_id": 1, "proc_nature": "Works", "emd_bdt": 100000}
    tender.update(overrides)
    return tender


def _profile(**overrides):
    profile = {
        "categories": "Works, Construction",
        "annual_turnover_bdt": 5000000,
        "liquid_assets_bdt": 200000,
        "similar_works": [{"title": "School building",
                           "value_bdt": 3000000, "category": "Works"}],
    }
    profile.update(overrides)
    return profile


def _points(result):
    return {c["key"]: (c["status"], c["points"]) for c in result["checks"]}


def test_no_profile():
    result = evaluate(_tender(), None)
    assert result == {"has_profile": False, "score": None,
                      "verdict": None, "checks": [], "note": NOTE}


def test_full_pass_scores_100():
    result = evaluate(_tender(), _profile())
    assert result["has_profile"] is True
    assert result["score"] == 100
    assert result["verdict"] == "Eligible"
    assert _points(result) == {
        "category": ("pass", 30), "turnover": ("pass", 25),
        "liquidity": ("pass", 20), "experience": ("pass", 25)}
    assert result["note"] == NOTE


def test_category_no_nature_unknown_15():
    result = evaluate(_tender(proc_nature=None), _profile())
    assert _points(result)["category"] == ("unknown", 15)


def test_category_no_profile_categories_unknown_0():
    result = evaluate(_tender(), _profile(categories=None))
    assert _points(result)["category"] == ("unknown", 0)


def test_category_mismatch_fail_0():
    result = evaluate(_tender(), _profile(categories="IT Services"))
    assert _points(result)["category"] == ("fail", 0)


def test_category_substring_either_way():
    # Profile category "Road Construction" vs nature "Works": no match.
    result = evaluate(_tender(proc_nature="Road Works"),
                      _profile(categories="Road"))
    assert _points(result)["category"] == ("pass", 30)
    result = evaluate(_tender(proc_nature="Works"),
                      _profile(categories="Civil Works"))
    assert _points(result)["category"] == ("pass", 30)


def test_turnover_partial_and_fail():
    # Estimate is EMD x 40 = 4,000,000; half is 2,000,000.
    result = evaluate(_tender(), _profile(annual_turnover_bdt=2500000))
    assert _points(result)["turnover"] == ("partial", 12)
    result = evaluate(_tender(), _profile(annual_turnover_bdt=1000000))
    assert _points(result)["turnover"] == ("fail", 0)
    result = evaluate(_tender(), _profile(annual_turnover_bdt=None))
    assert _points(result)["turnover"] == ("unknown", 0)


def test_turnover_emd_unknown():
    result = evaluate(_tender(emd_bdt=None), _profile())
    assert _points(result)["turnover"] == ("unknown", 12)


def test_liquidity_pass_fail_unknown():
    result = evaluate(_tender(), _profile(liquid_assets_bdt=99999))
    assert _points(result)["liquidity"] == ("fail", 0)
    result = evaluate(_tender(), _profile(liquid_assets_bdt=None))
    assert _points(result)["liquidity"] == ("unknown", 0)
    result = evaluate(_tender(emd_bdt=None), _profile())
    assert _points(result)["liquidity"] == ("unknown", 10)


def test_experience_no_works_unknown_0():
    result = evaluate(_tender(), _profile(similar_works=[]))
    assert _points(result)["experience"] == ("unknown", 0)


def test_experience_partial_small_relevant():
    result = evaluate(_tender(), _profile(similar_works=[
        {"title": "Small shed", "value_bdt": 100000,
         "category": "Works"}]))
    assert _points(result)["experience"] == ("partial", 12)


def test_experience_no_relevant_fail():
    result = evaluate(_tender(), _profile(similar_works=[
        {"title": "Software", "value_bdt": 9000000,
         "category": "IT Services"}]))
    assert _points(result)["experience"] == ("fail", 0)


def test_experience_empty_category_counts_relevant():
    result = evaluate(_tender(), _profile(similar_works=[
        {"title": "Unlabelled job", "value_bdt": 3000000,
         "category": ""}]))
    assert _points(result)["experience"] == ("pass", 25)


def test_experience_no_emd_partial():
    result = evaluate(_tender(emd_bdt=None), _profile())
    assert _points(result)["experience"] == ("partial", 12)


def test_emd_unknown_total():
    # category pass 30 + turnover unknown 12 + liquidity unknown 10
    # + experience partial 12 = 64.
    result = evaluate(_tender(emd_bdt=None), _profile())
    assert result["score"] == 64
    assert result["verdict"] == "Eligible with a JV partner"


def test_verdict_thresholds():
    assert verdict_for(100) == "Eligible"
    assert verdict_for(70) == "Eligible"
    assert verdict_for(69) == "Eligible with a JV partner"
    assert verdict_for(40) == "Eligible with a JV partner"
    assert verdict_for(39) == "Not yet eligible"
    assert verdict_for(0) == "Not yet eligible"


def test_evaluate_api_no_profile(client, store):
    _, token = make_premium_user(client, store, "noprof@example.com")
    resp = client.post("/api/v1/tenders/1001/evaluate",
                       headers=auth_headers(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_profile"] is False
    assert body["score"] is None
    assert body["verdict"] is None


def test_evaluate_api_full_pass(client, store):
    _, token = make_premium_user(client, store, "fullpass@example.com")
    save_profile(client, token)
    resp = client.post("/api/v1/tenders/1001/evaluate",
                       headers=auth_headers(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["score"] == 100
    assert body["verdict"] == "Eligible"
    assert len(body["checks"]) == 4
    assert body["note"] == NOTE


def test_evaluate_api_jv_verdict(client, store):
    _, token = make_premium_user(client, store, "jvverdict@example.com")
    save_profile(client, token, annual_turnover_bdt=1000000,
                 similar_works=[{"title": "Small shed",
                                 "value_bdt": 100000,
                                 "category": "Works"}])
    resp = client.post("/api/v1/tenders/1001/evaluate",
                       headers=auth_headers(token))
    body = resp.json()
    # category 30 + turnover 0 + liquidity 20 + experience 12 = 62.
    assert body["score"] == 62
    assert body["verdict"] == "Eligible with a JV partner"


def test_evaluate_api_not_yet_eligible(client, store):
    _, token = make_premium_user(client, store, "notyet@example.com")
    save_profile(client, token, categories="IT Services",
                 annual_turnover_bdt=100000, liquid_assets_bdt=1000,
                 similar_works=[])
    resp = client.post("/api/v1/tenders/1001/evaluate",
                       headers=auth_headers(token))
    body = resp.json()
    assert body["score"] == 0
    assert body["verdict"] == "Not yet eligible"


def test_evaluate_api_missing_tender(client, store):
    _, token = make_premium_user(client, store, "missing@example.com")
    resp = client.post("/api/v1/tenders/9999999/evaluate",
                       headers=auth_headers(token))
    assert resp.status_code == 404
