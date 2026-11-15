"""Extractive notice summary (SPEC.md section 8).

Deterministic, no LLM. Uses ONLY facts in the notice text (title,
ministry, procuring entity, district, nature/method, dates, document
price, EMD, description and eligibility text, each sliced to 4000
chars). Never invents figures, dates, or requirements. Summaries are
generated per request and never stored.

lang "en": full English. lang "bn": Bangla section labels and Bangla
connective text, with facts (names, IDs, figures, dates) as printed.
"""

from __future__ import annotations

import re

MIN_TEXT_CHARS = 80
MAX_TEXT_CHARS = 4000
MAX_POINTS = 6
MAX_POINT_CHARS = 300

TOO_LITTLE_TEXT_ERROR = (
    "This notice publishes too little text on the public page to "
    "summarize.")

# Sentences containing one of these words are requirement-like.
REQUIREMENT_WORDS = [
    "turnover", "experience", "similar work", "liquid", "security",
    "licence", "license", "registration", "registered", "vat", "tin",
    "trade licence", "solvency", "credit line", "joint venture",
    "personnel", "equipment", "certificate", "eligible", "eligibility",
    "qualification", "requirement", "minimum", "audited",
]

# Bangla labels / connective text for the composed (non-extracted)
# sentences. Extracted notice sentences stay as published (English).
BN = {
    "invited_by": "আহ্বানকারী",
    "district": "জেলা",
    "method": "পদ্ধতি",
    "nature": "ধরন",
    "emd": "টেন্ডার সিকিউরিটি (EMD)",
    "doc_price": "দলিলের মূল্য",
    "close": "জমা দেওয়ার শেষ তারিখ",
    "doc_last_selling": "দলিল বিক্রির শেষ তারিখ",
    "opening": "খোলার তারিখ",
    "pre_tender": "প্রি-টেন্ডার সভা",
    "check_notice": "বিস্তারিত জানতে e-GP-তে অফিসিয়াল নোটিশ দেখুন।",
}

EN = {
    "invited_by": "Invited by",
    "district": "District",
    "method": "Method",
    "nature": "Nature",
    "emd": "Tender security (EMD)",
    "doc_price": "Document price",
    "close": "Submission closes",
    "doc_last_selling": "Documents stop selling",
    "opening": "Opening",
    "pre_tender": "Pre-tender meeting",
    "check_notice": "Check the official notice on e-GP for full details.",
}


def _clean(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def _split_sentences(text: str) -> list[str]:
    """Split notice text into clean sentences / bullet points."""
    if not text:
        return []
    parts: list[str] = []
    for line in str(text).splitlines():
        line = line.strip().lstrip("•-*#0123456789. ").strip()
        if not line:
            continue
        for piece in re.split(r"(?<=[.!?])\s+", line):
            piece = _clean(piece)
            if len(piece) >= 12:
                parts.append(piece[:MAX_POINT_CHARS])
    return parts


def _fmt_bdt(amount) -> str | None:
    if amount is None:
        return None
    try:
        return f"BDT {int(amount):,}"
    except (TypeError, ValueError):
        return None


def _fmt_date(value) -> str | None:
    """Keep the stored date readable; never invent a format."""
    if not value:
        return None
    text = _clean(str(value))
    if not text:
        return None
    # ISO datetimes from the store: "2026-11-20T15:00:00+06:00".
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})", text)
    if match:
        year, month, day, hour, minute = match.groups()
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul",
                  "Aug", "Sep", "Oct", "Nov", "Dec"]
        return (f"{int(day)} {months[int(month) - 1]} {year}, "
                f"{hour}:{minute}")
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})", text)
    if match:
        year, month, day = match.groups()
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul",
                  "Aug", "Sep", "Oct", "Nov", "Dec"]
        return f"{int(day)} {months[int(month) - 1]} {year}"
    return text[:60]


def _compose_facts(tender: dict, labels: dict) -> list[str]:
    """One-line facts from the notice's structured fields."""
    facts = []
    entity = _clean(tender.get("procuring_entity"))
    if entity:
        facts.append(f"{labels['invited_by']}: {entity}")
    district = _clean(tender.get("district"))
    if district:
        facts.append(f"{labels['district']}: {district}")
    method = _clean(tender.get("method"))
    if method:
        facts.append(f"{labels['method']}: {method}")
    nature = _clean(tender.get("proc_nature"))
    if nature:
        facts.append(f"{labels['nature']}: {nature}")
    emd = _fmt_bdt(tender.get("emd_bdt"))
    if emd:
        facts.append(f"{labels['emd']}: {emd}")
    price = _fmt_bdt(tender.get("document_price_bdt"))
    if price:
        facts.append(f"{labels['doc_price']}: {price}")
    return facts


def _compose_watch_outs(tender: dict, labels: dict) -> list[str]:
    watch = []
    close = _fmt_date(tender.get("close_dt"))
    if close:
        watch.append(f"{labels['close']}: {close}")
    selling = _fmt_date(tender.get("doc_last_selling_dt"))
    if selling:
        watch.append(f"{labels['doc_last_selling']}: {selling}")
    opening = _fmt_date(tender.get("opening_dt"))
    if opening:
        watch.append(f"{labels['opening']}: {opening}")
    meeting = _fmt_date(tender.get("pre_tender_meeting_start"))
    if meeting:
        watch.append(f"{labels['pre_tender']}: {meeting}")
    emd = _fmt_bdt(tender.get("emd_bdt"))
    if emd:
        watch.append(f"{labels['emd']}: {emd}")
    watch.append(labels["check_notice"])
    return watch[:MAX_POINTS]


def summarize(tender: dict, lang: str = "en") -> dict:
    """Build the extractive summary for one stored tender row."""
    labels = BN if lang == "bn" else EN
    description = _clean(tender.get("description"))[:MAX_TEXT_CHARS]
    eligibility = _clean(tender.get("eligibility_text"))[:MAX_TEXT_CHARS]

    headline = _clean(tender.get("title")) or "Untitled notice"
    headline = headline[:200]

    desc_sentences = _split_sentences(description)
    elig_sentences = _split_sentences(eligibility)

    # Scope: the first description sentences, else the structured facts.
    scope_parts = desc_sentences[:2]
    if not scope_parts:
        scope_parts = _compose_facts(tender, labels)
    scope = " ".join(scope_parts)

    # Eligibility points: from the eligibility text; fall back to
    # eligibility-like sentences in the description.
    eligibility_points = elig_sentences[:MAX_POINTS]
    if not eligibility_points:
        eligibility_points = [
            s for s in desc_sentences
            if any(w in s.lower() for w in ("eligib", "qualif",
                                            "requirement"))
        ][:MAX_POINTS]

    # Key requirements: requirement-like sentences from both texts,
    # de-duplicated against the eligibility points.
    seen = set(eligibility_points)
    key_requirements = []
    for sentence in elig_sentences + desc_sentences:
        if sentence in seen:
            continue
        if any(w in sentence.lower() for w in REQUIREMENT_WORDS):
            key_requirements.append(sentence)
            seen.add(sentence)
        if len(key_requirements) >= MAX_POINTS:
            break

    watch_outs = _compose_watch_outs(tender, labels)

    return {
        "headline": headline,
        "scope": scope,
        "eligibility_points": eligibility_points,
        "key_requirements": key_requirements,
        "watch_outs": watch_outs,
    }


def has_enough_text(tender: dict) -> bool:
    """Guard: description + eligibility under 80 chars is too little."""
    description = _clean(tender.get("description"))
    eligibility = _clean(tender.get("eligibility_text"))
    return len(description) + len(eligibility) >= MIN_TEXT_CHARS
