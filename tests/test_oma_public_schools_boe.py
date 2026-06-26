from datetime import datetime
from os.path import dirname, join

import pytest
from city_scrapers_core.constants import BOARD
from city_scrapers_core.items import Meeting
from city_scrapers_core.utils import file_response
from freezegun import freeze_time

from city_scrapers.spiders.oma_public_schools_boe import OmaPublicSchoolsBoeSpider


@pytest.fixture(scope="module")
def parsed_upcoming_items():
    spider = OmaPublicSchoolsBoeSpider()
    response = file_response(
        join(
            dirname(__file__), "files", "oma_public_schools_boe_upcoming_meetings.html"
        ),
        url="https://www.ops.org/board/upcoming-meetings-and-livestream",
    )
    with freeze_time("2026-05-26"):
        return [item for item in spider.parse(response) if isinstance(item, Meeting)]


@pytest.fixture(scope="module")
def parsed_past_items():
    spider = OmaPublicSchoolsBoeSpider()
    response = file_response(
        join(dirname(__file__), "files", "oma_public_schools_boe_past_meetings.html"),
        url="https://meeting.sparqdata.com/Public/Organization/120",
    )
    with freeze_time("2026-05-26"):
        return [
            item
            for item in spider.parse_past_meetings(response)
            if isinstance(item, Meeting)
        ]


def test_count(parsed_upcoming_items):
    assert len(parsed_upcoming_items) == 5


def test_title(parsed_upcoming_items):
    assert parsed_upcoming_items[0]["title"] == "Board Meeting"
    assert parsed_upcoming_items[2]["title"] == "Board Workshop"


def test_description(parsed_upcoming_items):
    assert parsed_upcoming_items[0]["description"] == ""


def test_start(parsed_upcoming_items):
    assert parsed_upcoming_items[0]["start"] == datetime(2026, 6, 1, 18, 0)


def test_end(parsed_upcoming_items):
    assert parsed_upcoming_items[0]["end"] == datetime(2026, 6, 1, 19, 0)


def test_time_notes(parsed_upcoming_items):
    assert parsed_upcoming_items[0]["time_notes"] == ""


def test_status(parsed_upcoming_items):
    assert parsed_upcoming_items[0]["status"] == "tentative"


def test_location(parsed_upcoming_items):
    assert parsed_upcoming_items[0]["location"] == {
        "name": "TAC Building - Teaching and Learning Center",
        "address": "3215 Cuming St, Omaha, NE 68131",
    }


def test_source(parsed_upcoming_items):
    assert (
        parsed_upcoming_items[0]["source"]
        == "https://www.ops.org/board/upcoming-meetings-and-livestream"
    )


def test_links(parsed_upcoming_items):
    assert parsed_upcoming_items[0]["links"] == []


def test_classification(parsed_upcoming_items):
    assert parsed_upcoming_items[0]["classification"] == BOARD


def test_all_day(parsed_upcoming_items):
    for item in parsed_upcoming_items:
        assert item["all_day"] is False


# Past meetings (SparqData)


def test_sparq_count(parsed_past_items):
    assert len(parsed_past_items) == 183


def test_sparq_title(parsed_past_items):
    assert (
        parsed_past_items[0]["title"]
        == "Omaha Public Schools Board of Education and Educational Service Unit 19 Board Meeting"  # noqa
    )
    assert parsed_past_items[3]["title"] == "Board of Education Workshop"


def test_sparq_description(parsed_past_items):
    assert parsed_past_items[0]["description"] == ""


def test_sparq_start(parsed_past_items):
    assert parsed_past_items[0]["start"] == datetime(2026, 5, 18, 18, 0)
    assert parsed_past_items[3]["start"] == datetime(2026, 4, 13, 18, 0)


def test_sparq_end(parsed_past_items):
    assert parsed_past_items[0]["end"] is None


def test_sparq_time_notes(parsed_past_items):
    assert parsed_past_items[0]["time_notes"] == ""


def test_sparq_status(parsed_past_items):
    assert parsed_past_items[0]["status"] == "passed"


def test_sparq_location(parsed_past_items):
    assert parsed_past_items[0]["location"] == {
        "name": "Teacher Administrative Center",
        "address": "3215 Cuming Street, Omaha, NE 68131-2000",
    }


def test_sparq_links(parsed_past_items):
    assert parsed_past_items[0]["links"] == [
        {
            "href": "https://meeting.sparqdata.com/Public/Agenda/120?meeting=744429",
            "title": "Agenda",
        },
        {
            "href": "https://meeting.sparqdata.com/Public/Minutes/120?meeting=744429",
            "title": "Minutes",
        },
        {
            "href": "https://www.youtube.com/playlist?list=PLznBr7jR8aKWxFFAXV3aeXG45JzJ9Iboy",  # noqa
            "title": "YouTube Playlist",
        },
    ]


def test_sparq_classification(parsed_past_items):
    assert parsed_past_items[0]["classification"] == BOARD


def test_sparq_source(parsed_past_items):
    assert (
        parsed_past_items[0]["source"]
        == "https://meeting.sparqdata.com/Public/Organization/120"
    )


def test_sparq_all_day(parsed_past_items):
    for item in parsed_past_items:
        assert item["all_day"] is False
