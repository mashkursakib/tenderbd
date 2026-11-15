"""Parsers for e-GP public pages (verified against live HTML 2026-11-14).

Two page shapes:
1. Search results — HTML <tr> rows returned by TenderDetailsServlet
   (POST funName=AllTenders), 10 rows per page plus hidden inputs
   cntTenBrief / totalPages.
2. Notice detail — ViewTender.jsp, label/value table pairs
   ("Ministry :", "Ministry of Agriculture", ...) plus a lots table.

Dates on the portal look like "15-Nov-2026 01:00" or "19-Apr-2027"
(day-monthabbr-year, English abbreviations). Money is plain digits,
sometimes with commas ("3,470,000").
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

# Month abbreviations -> number (locale-independent).
_MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}

_DATE_RE = re.compile(
    r"(\d{1,2})-([A-Za-z]{3})-(\d{4})(?:\s+(\d{1,2}):(\d{2}))?")
_MONEY_RE = re.compile(r"[\d,]+(?:\.\d+)?")


def clean_text(text: str | None) -> str:
    """Collapse whitespace, strip HTML comment artefacts ("-->")."""
    if not text:
        return ""
    text = text.replace("-->", " ").replace("<!--", " ")
    text = text.replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_egp_datetime(value: str | None) -> datetime | None:
    """Parse "15-Nov-2026 01:00" / "19-Apr-2027" to an aware datetime (UTC).

    The portal shows Bangladesh local time; we store UTC. Times without a
    clock component become midnight UTC.
    """
    if not value:
        return None
    m = _DATE_RE.search(value)
    if not m:
        return None
    day, mon, year, hour, minute = m.groups()
    month = _MONTHS.get(mon[:3].title())
    if not month:
        return None
    try:
        return datetime(int(year), month, int(day),
                        int(hour or 0), int(minute or 0),
                        tzinfo=timezone.utc)
    except ValueError:
        return None


def parse_money_bdt(value: str | None) -> int | None:
    """Parse a BDT amount like "3,470,000" or "5000" to integer taka."""
    if not value:
        return None
    m = _MONEY_RE.search(value.replace(",", ""))
    if not m:
        return None
    try:
        return int(float(m.group(0)))
    except ValueError:
        return None


def parse_int(value: str | None) -> int | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    return int(digits) if digits else None


# ---------------------------------------------------------------------------
# Search results (TenderDetailsServlet rows)
# ---------------------------------------------------------------------------

def parse_search_rows(html: str) -> dict:
    """Parse one page of search-result rows.

    Returns {"tenders": [row dicts], "total_pages": int | None,
    "rows_on_page": int}. Each row dict has the fields listed in the
    module docstring of db.py (tender_id, ref_no, status, nature, title,
    ministry, department, procuring_entity, proc_type, method,
    publish_dt, close_dt).
    """
    soup = BeautifulSoup(html, "html.parser")
    tenders: list[dict] = []
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td", recursive=False)
        if len(tds) != 6:
            continue
        serial = clean_text(tds[0].get_text())
        if not serial.isdigit():
            continue
        # Col 2: "1363322, <br/> REF-..., <br/> <label>Live</label>"
        col2_parts = [clean_text(p) for p in
                      tds[1].get_text(separator="|").split("|")]
        col2_parts = [p.rstrip(",") for p in col2_parts if p]
        tender_id = parse_int(col2_parts[0]) if col2_parts else None
        # Col 3: nature + form with hidden id + title span
        hidden = tds[2].find("input", {"name": "id"})
        if hidden and hidden.get("value", "").isdigit():
            tender_id = int(hidden["value"])  # authoritative
        title_span = tds[2].find("span", id=re.compile(r"^tenderBrief_"))
        title = clean_text(title_span.get_text()) if title_span else ""
        nature_raw = tds[2].get_text(separator="|").split("|")[0]
        nature = clean_text(nature_raw).rstrip(",")
        # Col 4: "Ministry, <br/> Department, <br/> Procuring entity"
        col4 = [clean_text(p).rstrip(",") for p in
                tds[3].get_text(separator="|").split("|")]
        col4 = [p for p in col4 if p]
        ministry = col4[0] if len(col4) > 0 else ""
        department = col4[1] if len(col4) > 1 else ""
        procuring_entity = col4[2] if len(col4) > 2 else ""
        # Col 5: "NCT, <br/> OTM"
        col5 = [clean_text(p).rstrip(",") for p in
                tds[4].get_text(separator="|").split("|")]
        col5 = [p for p in col5 if p]
        proc_type = col5[0] if len(col5) > 0 else ""
        method = col5[1] if len(col5) > 1 else ""
        # Col 6: "15-Nov-2026 01:00, <br/> 21-Dec-2026 14:00"
        col6 = [clean_text(p).rstrip(",") for p in
                tds[5].get_text(separator="|").split("|")]
        col6 = [p for p in col6 if p]
        publish_dt = parse_egp_datetime(col6[0]) if len(col6) > 0 else None
        close_dt = parse_egp_datetime(col6[1]) if len(col6) > 1 else None
        status = ""
        label = tds[1].find("label")
        if label:
            status = clean_text(label.get_text())
        if tender_id is None:
            log.warning("Skipping search row without tender id: %s",
                        clean_text(tr.get_text())[:120])
            continue
        tenders.append({
            "tender_id": tender_id,
            "ref_no": col2_parts[1] if len(col2_parts) > 1 else "",
            "status": status,
            "proc_nature": nature,
            "title": title,
            "ministry": ministry,
            "department": department,
            "procuring_entity": procuring_entity,
            "proc_type": proc_type,
            "method": method,
            "publish_dt": publish_dt,
            "close_dt": close_dt,
        })
    total_pages = None
    total_input = soup.find("input", {"id": "totalPages"})
    if total_input and total_input.get("value", "").isdigit():
        total_pages = int(total_input["value"])
    return {"tenders": tenders, "total_pages": total_pages,
            "rows_on_page": len(tenders)}


# ---------------------------------------------------------------------------
# Notice detail (ViewTender.jsp)
# ---------------------------------------------------------------------------

# Normalised label (collapsed whitespace, no trailing colon) -> field name.
_LABEL_MAP = {
    "Ministry": "ministry",
    "Division": "division",
    "Organization": "organisation",
    "Procuring Entity Name": "procuring_entity",
    "Procuring Entity Code": "procuring_entity_code",
    "Procuring Entity District": "district",
    "Procurement Nature": "proc_nature",
    "Procurement Type": "proc_type",
    "Event Type": "event_type",
    "Invitation for": "invitation_for",
    "Invitation Reference No.": "ref_no",
    "App ID": "app_id",
    "Tender/Proposal ID": "tender_id",
    "Procurement Method": "method",
    "Budget Type": "budget_type",
    "Source of Funds": "source_of_funds",
    "Project Code": "project_code",
    "Project Name": "project_name",
    "Tender/Proposal Package No. and Description": "package",
    "Category": "category",
    "Scheduled Tender/Proposal Publication Date and Time": "publish_dt",
    "Tender/Proposal Document last selling / downloading Date and Time": "doc_last_selling_dt",
    "Pre - Tender/Proposal meeting Start Date and Time": "pre_tender_meeting_start",
    "Pre - Tender/Proposal meeting End Date and Time": "pre_tender_meeting_end",
    "Tender/Proposal Closing Date and Time": "close_dt",
    "Tender/Proposal Opening Date and Time": "opening_dt",
    "Last Date and Time for Tender/Proposal Security Submission": "security_submission_dt",
    "Eligibility of Tenderer": "eligibility_text",
    "Brief Description of Works": "description",
    "Evaluation Type": "evaluation_type",
    "Document Available": "document_available",
    "Document Fees": "document_fees",
    "Tender/Proposal Document Price (In BDT)": "document_price_bdt",
    "Mode of Payment": "payment_mode",
    "Tender/Proposal Security Valid Up to": "security_valid_up_to",
    "Tender/Proposal Valid Up to": "tender_valid_up_to",
}

_DATETIME_FIELDS = {
    "publish_dt", "doc_last_selling_dt", "pre_tender_meeting_start",
    "pre_tender_meeting_end", "close_dt", "opening_dt",
    "security_submission_dt", "security_valid_up_to", "tender_valid_up_to",
}


def _normalise_label(text: str) -> str:
    text = clean_text(text)
    return text[:-1].strip() if text.endswith(":") else text


def _label_value_pairs(soup: BeautifulSoup) -> dict[str, str]:
    """Walk every table, pairing label cells with the following value cell."""
    pairs: dict[str, str] = {}
    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            tds = tr.find_all("td", recursive=False)
            if len(tds) < 2:
                continue
            for i in range(len(tds) - 1):
                label = _normalise_label(tds[i].get_text(separator=" "))
                if label in _LABEL_MAP and label not in pairs:
                    value = clean_text(tds[i + 1].get_text(separator=" "))
                    pairs[label] = value
    return pairs


def _parse_lots(soup: BeautifulSoup) -> list[dict]:
    """Parse the lots table (header contains 'Identification of Lot')."""
    lots: list[dict] = []
    for table in soup.find_all("table"):
        header = clean_text(table.get_text(separator=" "))
        if "Identification of Lot" not in header:
            continue
        for tr in table.find_all("tr"):
            tds = tr.find_all("td", recursive=False)
            if len(tds) < 6:
                continue
            lot_no = clean_text(tds[0].get_text())
            if not lot_no or lot_no.lower().startswith("lot no"):
                continue
            lots.append({
                "lot_no": lot_no,
                "identification": clean_text(tds[1].get_text()),
                "location": clean_text(tds[2].get_text()),
                "security_bdt": parse_money_bdt(tds[3].get_text()),
                "start_date": _date_only(tds[4].get_text()),
                "completion_date": _date_only(tds[5].get_text()),
            })
    return lots


def _date_only(value: str) -> str | None:
    dt = parse_egp_datetime(value)
    return dt.date().isoformat() if dt else None


def parse_notice(html: str, tender_id: int | None = None) -> dict:
    """Parse a ViewTender.jsp notice page into a tender dict.

    Returns all notice fields (see _LABEL_MAP) plus lots, emd_bdt
    (security amount of the first lot, i.e. the tender security / EMD),
    and the title derived from the package description.
    """
    soup = BeautifulSoup(html, "html.parser")
    pairs = _label_value_pairs(soup)
    out: dict = {"tender_id": tender_id, "lots": _parse_lots(soup)}
    for label, raw in pairs.items():
        field = _LABEL_MAP[label]
        if field in _DATETIME_FIELDS:
            out[field] = parse_egp_datetime(raw)
        elif field == "document_price_bdt":
            out[field] = parse_money_bdt(raw)
        elif field == "tender_id":
            out[field] = parse_int(raw) or tender_id
        elif field == "package":
            # "PKG-REF Description text..." — the package number is a
            # single whitespace-free code; the rest is the description.
            parts = raw.split(None, 1)
            out["package_no"] = parts[0] if parts else ""
            out["package_description"] = parts[1] if len(parts) > 1 else ""
        elif field == "app_id":
            out[field] = parse_int(raw)
        else:
            out[field] = raw or None
    # Title: prefer the brief description, else the package description.
    title = out.get("description") or out.get("package_description") or ""
    out["title"] = title
    # EMD = tender security of the first lot (portal shows it per lot).
    if out["lots"]:
        out["emd_bdt"] = out["lots"][0].get("security_bdt")
    # Corrigendum section: capture only if it has substantive text.
    corr = _parse_corrigendum(soup)
    if corr:
        out["corrigendum_text"] = corr
    return out


def _parse_corrigendum(soup: BeautifulSoup) -> str | None:
    for el in soup.find_all(string=re.compile(r"Amendment\s*/\s*Corrigendum", re.I)):
        table = el.find_parent("table")
        if not table:
            continue
        text = clean_text(table.get_text(separator=" "))
        text = re.sub(r"Amendment\s*/\s*Corrigendum Detail", "", text,
                      flags=re.I).strip()
        if len(text) > 20:
            return text[:2000]
    return None
