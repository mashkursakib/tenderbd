"""Eligibility scoring (SPEC.md section 7).

Four checks, max 100 points. Estimated contract value = EMD x 40
(EMD assumed ~2.5% of value; labelled an estimate). Check detail
strings are in English only. The note is verbatim from the spec.
"""

from __future__ import annotations

NOTE = ("Estimate from the public notice fields plus your declared "
        "profile. Full eligibility criteria live inside the tender "
        "document on e-GP, which needs a bidder login, check the "
        "official notice before bidding.")

ESTIMATE_MULTIPLIER = 40


def _split_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in str(value).split(",") if part.strip()]


def _fmt_bdt(amount: int | float | None) -> str:
    if amount is None:
        return "not published"
    return f"BDT {int(amount):,}"


def _substring_match(a: str, b: str) -> bool:
    a, b = a.strip().lower(), b.strip().lower()
    if not a or not b:
        return False
    return a in b or b in a


def _check_category(tender: dict, categories: list[str]) -> dict:
    nature = (tender.get("proc_nature") or "").strip()
    if not nature:
        return {"key": "category", "status": "unknown", "points": 15,
                "max_points": 30,
                "detail": "The notice does not state a procurement "
                          "nature, so category fit cannot be checked."}
    if not categories:
        return {"key": "category", "status": "unknown", "points": 0,
                "max_points": 30,
                "detail": "No categories are declared in your profile, "
                          "so category fit cannot be checked."}
    if any(_substring_match(cat, nature) for cat in categories):
        return {"key": "category", "status": "pass", "points": 30,
                "max_points": 30,
                "detail": f"Your declared categories match this "
                          f"tender's nature ({nature})."}
    return {"key": "category", "status": "fail", "points": 0,
            "max_points": 30,
            "detail": f"Your declared categories do not match this "
                      f"tender's nature ({nature})."}


def _check_turnover(tender: dict, turnover, estimate) -> dict:
    if estimate is None:
        return {"key": "turnover", "status": "unknown", "points": 12,
                "max_points": 25,
                "detail": "The notice does not publish tender security, "
                          "so the tender scale cannot be estimated."}
    if turnover is None:
        return {"key": "turnover", "status": "unknown", "points": 0,
                "max_points": 25,
                "detail": "No annual turnover is declared in your "
                          "profile, so scale fit cannot be checked."}
    if turnover >= estimate:
        return {"key": "turnover", "status": "pass", "points": 25,
                "max_points": 25,
                "detail": f"Your annual turnover ({_fmt_bdt(turnover)}) "
                          f"covers the estimated contract value "
                          f"({_fmt_bdt(estimate)})."}
    if turnover >= estimate / 2:
        return {"key": "turnover", "status": "partial", "points": 12,
                "max_points": 25,
                "detail": f"Your annual turnover ({_fmt_bdt(turnover)}) "
                          f"is at least half of the estimated contract "
                          f"value ({_fmt_bdt(estimate)})."}
    return {"key": "turnover", "status": "fail", "points": 0,
            "max_points": 25,
            "detail": f"Your annual turnover ({_fmt_bdt(turnover)}) is "
                      f"below half of the estimated contract value "
                      f"({_fmt_bdt(estimate)})."}


def _check_liquidity(tender: dict, liquid) -> dict:
    emd = tender.get("emd_bdt")
    if emd is None:
        return {"key": "liquidity", "status": "unknown", "points": 10,
                "max_points": 20,
                "detail": "The notice does not publish tender security, "
                          "so liquidity cannot be checked."}
    if liquid is None:
        return {"key": "liquidity", "status": "unknown", "points": 0,
                "max_points": 20,
                "detail": "No liquid assets are declared in your "
                          "profile, so liquidity cannot be checked."}
    if liquid >= emd:
        return {"key": "liquidity", "status": "pass", "points": 20,
                "max_points": 20,
                "detail": f"Your liquid assets ({_fmt_bdt(liquid)}) "
                          f"cover the tender security "
                          f"({_fmt_bdt(emd)})."}
    return {"key": "liquidity", "status": "fail", "points": 0,
            "max_points": 20,
            "detail": f"Your liquid assets ({_fmt_bdt(liquid)}) are "
                      f"below the tender security ({_fmt_bdt(emd)})."}


def _work_is_relevant(work: dict, nature: str) -> bool:
    category = (work.get("category") or "").strip()
    if not category:
        return True
    if not nature:
        return True
    return _substring_match(category, nature)


def _check_experience(tender: dict, works: list[dict], estimate) -> dict:
    if not works:
        return {"key": "experience", "status": "unknown", "points": 0,
                "max_points": 25,
                "detail": "No similar works are declared in your "
                          "profile, so experience cannot be checked."}
    if estimate is None:
        return {"key": "experience", "status": "partial", "points": 12,
                "max_points": 25,
                "detail": "Similar works are declared, but the notice "
                          "does not publish tender security, so the "
                          "scale of experience cannot be compared."}
    nature = (tender.get("proc_nature") or "").strip()
    relevant = [w for w in works if _work_is_relevant(w, nature)]
    if not relevant:
        return {"key": "experience", "status": "fail", "points": 0,
                "max_points": 25,
                "detail": "None of your declared similar works match "
                          "this tender's category."}
    largest = max((w.get("value_bdt") or 0) for w in relevant)
    if largest >= estimate / 2:
        return {"key": "experience", "status": "pass", "points": 25,
                "max_points": 25,
                "detail": f"Your largest relevant similar work "
                          f"({_fmt_bdt(largest)}) is at least half of "
                          f"the estimated contract value "
                          f"({_fmt_bdt(estimate)})."}
    return {"key": "experience", "status": "partial", "points": 12,
            "max_points": 25,
            "detail": f"Relevant similar works are declared, but the "
                      f"largest ({_fmt_bdt(largest)}) is below half of "
                      f"the estimated contract value "
                      f"({_fmt_bdt(estimate)})."}


def verdict_for(score: int) -> str:
    if score >= 70:
        return "Eligible"
    if score >= 40:
        return "Eligible with a JV partner"
    return "Not yet eligible"


def evaluate(tender: dict, profile: dict | None) -> dict:
    """Score one tender against a company profile (or None)."""
    if profile is None:
        return {"has_profile": False, "score": None, "verdict": None,
                "checks": [], "note": NOTE}
    emd = tender.get("emd_bdt")
    estimate = (emd * ESTIMATE_MULTIPLIER) if emd is not None else None
    categories = _split_list(profile.get("categories"))
    works = profile.get("similar_works") or []
    checks = [
        _check_category(tender, categories),
        _check_turnover(tender, profile.get("annual_turnover_bdt"),
                        estimate),
        _check_liquidity(tender, profile.get("liquid_assets_bdt")),
        _check_experience(tender, works, estimate),
    ]
    score = sum(c["points"] for c in checks)
    return {"has_profile": True, "score": score,
            "verdict": verdict_for(score), "checks": checks, "note": NOTE}
