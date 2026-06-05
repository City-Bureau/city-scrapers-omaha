from datetime import datetime
from os.path import dirname, join

import pytest
import scrapy
from city_scrapers_core.constants import (
    BOARD,
    CANCELLED,
    COMMISSION,
    COMMITTEE,
    NOT_CLASSIFIED,
    PASSED,
)
from city_scrapers_core.utils import file_response
from freezegun import freeze_time

from city_scrapers.spiders.oma_sarpy_boc import (
    OmaSarpyBocBoardMeetings,
    OmaSarpyBocBoardOfAdjustment,
    OmaSarpyBocBoardOfCorrections,
    OmaSarpyBocBoardOfEqualization,
    OmaSarpyBocLeasingCorporation,
    OmaSarpyBocPersonnelPolicyBoard,
    OmaSarpyBocPlanningCommission,
    OmaSarpyBocTriCountyRetreat,
    OmaSarpyBocVeteransServiceCommittee,
    OmaSarpyBocWastewaterAgency,
)

MEETINGS_URL = (
    "https://sarpy.civicweb.net/Services/MeetingsService.svc/meetings"
    "?from=2024-01-01&to=2027-12-31&_=1234567890"
)
DOCS_URL = (
    "https://sarpy.civicweb.net/Services/MeetingsService.svc/meetings"
    "/4927/meetingDocuments?_=1234567890"
)
VIDEO_URL = "https://sarpy.civicweb.net/api/geteventwithindexpoints/4927?_=1234567890"


@pytest.fixture(scope="module")
def meetings_response():
    return file_response(
        join(dirname(__file__), "files", "oma_sarpy_boc.json"),
        url=MEETINGS_URL,
    )


@pytest.fixture(scope="module")
def docs_response():
    return file_response(
        join(dirname(__file__), "files", "oma_sarpy_boc_docs.json"),
        url=DOCS_URL,
    )


@pytest.fixture(scope="module")
def video_response():
    return file_response(
        join(dirname(__file__), "files", "oma_sarpy_boc_video.json"),
        url=VIDEO_URL,
    )


def parse_items(spider, meetings_response):
    """Return all meeting dicts from parse(), including directly yielded items."""
    with freeze_time("2026-05-29"):
        results = list(spider.parse(meetings_response))
        items = []
        for result in results:
            if isinstance(result, scrapy.http.Request):
                items.append(result.cb_kwargs["meeting"])
            else:
                items.append(result)
        return items


def parse_final_items(
    spider, meetings_response, docs_response, video_response, meeting_id
):
    """Chain parse -> parse_meeting_documents -> parse_video_link for one meeting."""
    with freeze_time("2026-05-29"):
        results = list(spider.parse(meetings_response))
        final_items = []
        for req in results:
            if not isinstance(req, scrapy.http.Request):
                continue
            if req.cb_kwargs.get("meeting_id") != meeting_id:
                continue
            doc_results = list(req.callback(docs_response, **req.cb_kwargs))
            for video_req in doc_results:
                items = list(video_req.callback(video_response, **video_req.cb_kwargs))
                final_items.extend(items)
        return final_items


# --- Spider filter counts ---


@pytest.mark.parametrize(
    "spider_class, expected_count",
    [
        (OmaSarpyBocBoardMeetings, 2),  # 1 regular + 1 NO MEETING
        (OmaSarpyBocBoardOfAdjustment, 1),
        (OmaSarpyBocBoardOfCorrections, 1),
        (OmaSarpyBocBoardOfEqualization, 1),
        (OmaSarpyBocLeasingCorporation, 1),
        (OmaSarpyBocPersonnelPolicyBoard, 1),
        (OmaSarpyBocPlanningCommission, 1),
        (OmaSarpyBocTriCountyRetreat, 1),
        (OmaSarpyBocVeteransServiceCommittee, 1),
        (OmaSarpyBocWastewaterAgency, 2),  # 1 regular + 1 NO MEETING at end
    ],
)
def test_spider_counts(spider_class, expected_count, meetings_response):
    items = parse_items(spider_class(), meetings_response)
    assert len(items) == expected_count


def test_board_meetings_excludes_period(meetings_response):
    items = parse_items(OmaSarpyBocBoardMeetings(), meetings_response)
    titles = [item["title"] for item in items]
    assert not any("Board Meetings." in t for t in titles)


def test_planning_commission_deduplicates(meetings_response):
    # Fixture has two entries for the same Planning Commission meeting (one
    # Published=true, one Published=false). Only one should be yielded.
    items = parse_items(OmaSarpyBocPlanningCommission(), meetings_response)
    assert len(items) == 1


# --- Board Meetings spider ---


def test_board_meetings_title(meetings_response):
    items = parse_items(OmaSarpyBocBoardMeetings(), meetings_response)
    regular = [i for i in items if "NO MEETING" not in i["title"]]
    assert regular[0]["title"] == "Board Meetings"


def test_board_meetings_classification(meetings_response):
    items = parse_items(OmaSarpyBocBoardMeetings(), meetings_response)
    for item in items:
        assert item["classification"] == BOARD


def test_board_meetings_start(meetings_response):
    items = parse_items(OmaSarpyBocBoardMeetings(), meetings_response)
    regular = [i for i in items if "NO MEETING" not in i["title"]]
    assert regular[0]["start"] == datetime(2024, 1, 9, 15, 0)


def test_board_meetings_location(meetings_response):
    items = parse_items(OmaSarpyBocBoardMeetings(), meetings_response)
    regular = [i for i in items if "NO MEETING" not in i["title"]]
    assert regular[0]["location"] == {
        "name": "County Boardroom",
        "address": "1210 Golden Gate Drive, Papillion, NE 68046",
    }


def test_board_meetings_source(meetings_response):
    items = parse_items(OmaSarpyBocBoardMeetings(), meetings_response)
    regular = [i for i in items if "NO MEETING" not in i["title"]]
    assert regular[0]["source"] == (
        "https://sarpy.civicweb.net/Portal/MeetingInformation.aspx?Org=Cal&Id=4927"
    )


def test_board_meetings_status(meetings_response, docs_response, video_response):
    items = parse_final_items(
        OmaSarpyBocBoardMeetings(),
        meetings_response,
        docs_response,
        video_response,
        4927,
    )
    assert items[0]["status"] == PASSED


# --- NO MEETING cancellation ---


def test_no_meeting_is_cancelled(meetings_response):
    items = parse_items(OmaSarpyBocBoardMeetings(), meetings_response)
    no_meeting = [i for i in items if "NO MEETING" in i["title"]]
    assert len(no_meeting) == 1
    assert no_meeting[0]["status"] == CANCELLED


def test_no_meeting_title(meetings_response):
    items = parse_items(OmaSarpyBocBoardMeetings(), meetings_response)
    no_meeting = [i for i in items if "NO MEETING" in i["title"]]
    assert no_meeting[0]["title"] == "Board Meetings - NO MEETING"


# --- Classification tests ---


def test_planning_commission_classification(meetings_response):
    items = parse_items(OmaSarpyBocPlanningCommission(), meetings_response)
    assert items[0]["classification"] == COMMISSION


def test_veterans_service_committee_classification(meetings_response):
    items = parse_items(OmaSarpyBocVeteransServiceCommittee(), meetings_response)
    assert items[0]["classification"] == COMMITTEE


def test_leasing_corporation_classification(meetings_response):
    items = parse_items(OmaSarpyBocLeasingCorporation(), meetings_response)
    assert items[0]["classification"] == NOT_CLASSIFIED


def test_tri_county_retreat_classification(meetings_response):
    items = parse_items(OmaSarpyBocTriCountyRetreat(), meetings_response)
    assert items[0]["classification"] == NOT_CLASSIFIED


def test_wastewater_agency_classification(meetings_response):
    items = parse_items(OmaSarpyBocWastewaterAgency(), meetings_response)
    assert items[0]["classification"] == NOT_CLASSIFIED


# --- Wastewater NO MEETING at end of name ---


def test_wastewater_no_meeting_cancelled(meetings_response):
    items = parse_items(OmaSarpyBocWastewaterAgency(), meetings_response)
    cancelled = [i for i in items if i.get("status") == CANCELLED]
    assert len(cancelled) == 1
    assert cancelled[0]["status"] == CANCELLED


def test_wastewater_no_meeting_title(meetings_response):
    # "Wastewater Agency - May 27 2026 - NO MEETING" should parse to clean title
    items = parse_items(OmaSarpyBocWastewaterAgency(), meetings_response)
    cancelled = [i for i in items if i.get("status") == CANCELLED]
    assert cancelled[0]["title"] == "Wastewater Agency"


# --- Location for non-standard venue ---


def test_tri_county_retreat_location(meetings_response):
    items = parse_items(OmaSarpyBocTriCountyRetreat(), meetings_response)
    assert items[0]["location"] == {"name": "TBD", "address": ""}


# --- Full document + video flow ---


def test_board_meetings_agenda_link(meetings_response, docs_response, video_response):
    items = parse_final_items(
        OmaSarpyBocBoardMeetings(),
        meetings_response,
        docs_response,
        video_response,
        4927,
    )
    assert len(items) == 1
    agenda_links = [link for link in items[0]["links"] if link["title"] == "Agenda"]
    assert len(agenda_links) == 1
    assert agenda_links[0]["href"] == (
        "https://sarpy.civicweb.net/document/321491"
        "/Board%20Meetings%20-%20Jan%2009%202024.html"
    )


def test_board_meetings_includes_all_documents(
    meetings_response, docs_response, video_response
):
    items = parse_final_items(
        OmaSarpyBocBoardMeetings(),
        meetings_response,
        docs_response,
        video_response,
        4927,
    )
    titles = [link["title"] for link in items[0]["links"]]
    assert "Minutes" in titles
    assert "Document" in titles


def test_board_meetings_video_link(meetings_response, docs_response, video_response):
    items = parse_final_items(
        OmaSarpyBocBoardMeetings(),
        meetings_response,
        docs_response,
        video_response,
        4927,
    )
    video_links = [link for link in items[0]["links"] if link["title"] == "Video"]
    assert len(video_links) == 1
    assert video_links[0]["href"] == "https://www.youtube.com/watch?v=QxgSHZ4DMAE"


def test_board_meetings_links_deduplicated(
    meetings_response, docs_response, video_response
):
    items = parse_final_items(
        OmaSarpyBocBoardMeetings(),
        meetings_response,
        docs_response,
        video_response,
        4927,
    )
    seen = set()
    for link in items[0]["links"]:
        key = (link["href"], link["title"])
        assert key not in seen
        seen.add(key)


def test_board_meetings_id(meetings_response, docs_response, video_response):
    items = parse_final_items(
        OmaSarpyBocBoardMeetings(),
        meetings_response,
        docs_response,
        video_response,
        4927,
    )
    assert items[0]["id"].startswith("oma_sarpy_boc_board_meetings/")
