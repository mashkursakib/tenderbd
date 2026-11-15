"""Parser tests against real e-GP HTML captured 2026-11-14.

Fixtures:
- search_rows.html: 10 live rows from TenderDetailsServlet
  (publish window 10–15 Nov 2026, page 1 of 125).
- notice_1361116.html: ViewTender.jsp for tender 1361116 (BADC
  irrigation canal works, Brahmanbaria). The contact-details block
  was removed from the fixture; parsers do not use it.
"""

from pathlib import Path

from tenderbd_scraper.parsers import (parse_egp_datetime, parse_money_bdt,
                                      parse_notice, parse_search_rows)

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_egp_datetime():
    dt = parse_egp_datetime("15-Nov-2026 01:00")
    assert (dt.year, dt.month, dt.day, dt.hour) == (2026, 11, 15, 1)
    d = parse_egp_datetime("19-Apr-2027")
    assert (d.year, d.month, d.day) == (2027, 4, 19)
    assert parse_egp_datetime("not a date") is None
    assert parse_egp_datetime("") is None


def test_parse_money_bdt():
    assert parse_money_bdt("5000") == 5000
    assert parse_money_bdt("3,470,000") == 3470000
    assert parse_money_bdt("") is None


def test_parse_search_rows():
    html = (FIXTURES / "search_rows.html").read_text()
    page = parse_search_rows(html)
    assert page["rows_on_page"] == 10
    assert page["total_pages"] == 125
    rows = page["tenders"]
    first = rows[0]
    assert first["tender_id"] == 1363322
    assert first["ref_no"] == "FMD-LSD/2026-27/SD-03"
    assert first["status"] == "Live"
    assert first["proc_nature"] == "Services"
    assert first["title"] == "Deployment of Individual Consultants"
    assert first["ministry"] == "Ministry of Fisheries & Livestock"
    assert first["department"] == "Department of Livestock Services (DLS)"
    assert first["procuring_entity"] == "FMD-LSD Project"
    assert first["proc_type"] == "NCT"
    assert first["method"] == "IC"
    assert first["publish_dt"].strftime("%Y-%m-%d %H:%M") == "2026-11-15 01:00"
    assert first["close_dt"].strftime("%Y-%m-%d %H:%M") == "2026-12-21 14:00"
    # Every row has an id, a title and a closing date.
    assert all(r["tender_id"] and r["title"] and r["close_dt"] for r in rows)
    # Ids are unique on the page.
    assert len({r["tender_id"] for r in rows}) == 10


def test_parse_notice():
    html = (FIXTURES / "notice_1361116.html").read_text()
    notice = parse_notice(html, tender_id=1361116)
    assert notice["tender_id"] == 1361116
    assert notice["ministry"] == "Ministry of Agriculture"
    assert notice["organisation"] == (
        "Bangladesh Agricultural Development Corporation (BADC)")
    assert notice["procuring_entity"] == (
        "Project Director Office Ashuganj-Palash Green Project")
    assert notice["district"] == "Brahmanbaria"
    assert notice["proc_nature"] == "Works"
    assert notice["proc_type"] == "NCT"
    assert notice["event_type"] == "TENDER"
    assert notice["ref_no"] == "e-GP/APGP/2026-27/W-26/Lot-13/T-79"
    assert notice["app_id"] == 230673
    assert notice["method"] == "Open Tendering Method (OTM)"
    assert notice["budget_type"] == "Development"
    assert notice["source_of_funds"] == "Government"
    assert notice["project_code"] == "224423400"
    assert notice["project_name"] == "Ashuganj-Palash Green Project"
    assert notice["package_no"] == "e-GP/APGP/2026-27/W-26/Lot-13"
    assert "RCC Main Irrigation Canal" in notice["package_description"]
    assert "Construction work" in notice["category"]
    assert notice["publish_dt"].strftime("%Y-%m-%d %H:%M") == "2026-10-29 12:00"
    assert notice["close_dt"].strftime("%Y-%m-%d %H:%M") == "2026-11-22 17:00"
    assert notice["opening_dt"].strftime("%Y-%m-%d %H:%M") == "2026-11-22 17:00"
    assert notice["document_price_bdt"] == 5000
    assert notice["payment_mode"] == "Payment through Bank"
    assert notice["emd_bdt"] == 3470000
    assert "5 (Five) years" in notice["eligibility_text"]
    assert "Liquid asset" in notice["eligibility_text"]
    assert notice["evaluation_type"] == "Lot wise"
    lots = notice["lots"]
    assert len(lots) == 1
    assert lots[0]["lot_no"] == "Lot-13"
    assert lots[0]["security_bdt"] == 3470000
    assert lots[0]["location"].startswith("Ashuganj-Sarail")
    assert lots[0]["start_date"] == "2026-12-01"
    assert lots[0]["completion_date"] == "2028-12-31"
