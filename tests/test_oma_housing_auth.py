from datetime import datetime
from os.path import dirname, join

import pytest
from city_scrapers_core.constants import BOARD
from city_scrapers_core.utils import file_response
from freezegun import freeze_time

from city_scrapers.spiders.oma_housing_auth import OmaHousingAuthSpider


@pytest.fixture(scope="module")
def parsed_items():
    spider = OmaHousingAuthSpider()
    primary_response = file_response(
        join(dirname(__file__), "files", "oma_housing_auth.html"),
        url="https://meeting.sparqdata.com/Public/Organization/201",
    )
    secondary_response = file_response(
        join(dirname(__file__), "files", "oma_housing_auth_secondary.html"),
        url="https://ohauthority.org/about-oha/board-of-commissioners/board-meetings/",
    )
    with freeze_time("2026-06-07"):
        list(spider.parse(primary_response))
        return list(spider._links_and_tentative_meetings_page(secondary_response))


@pytest.fixture(scope="module")
def primary_items(parsed_items):
    return [i for i in parsed_items if "sparqdata" in i["source"]]


@pytest.fixture(scope="module")
def secondary_items(parsed_items):
    return [i for i in parsed_items if "ohauthority" in i["source"]]


def test_count(parsed_items):
    assert len(parsed_items) == 41


def test_primary_items_exist(primary_items):
    assert len(primary_items) == 32


def test_secondary_items_exist(secondary_items):
    assert len(secondary_items) == 9


def test_primary_items(primary_items):
    assert len(primary_items) > 0
    item = primary_items[0]

    assert item["title"] != ""
    assert item["classification"] == BOARD
    assert item["description"] == ""
    assert item["start"] == datetime(2026, 6, 4, 8, 30)
    assert item["end"] is None
    assert item["all_day"] is False
    assert item["location"] == {
        "name": "First Floor Boardroom",
        "address": "1823 Harney Street, Omaha, NE 68102",
    }
    assert item["links"] == [
        {
            "href": "https://ohauthority.org/wp-content/uploads/2026/06/June-4-2026-OHA-Board-Mtg-Agenda.pdf",  # noqa
            "title": "Agenda 06.04.2026",
        }
    ]
    assert item["status"] == "passed"
    assert (
        item["id"]
        == "oma_housing_auth/202606040830/x/oha_regular_meeting_of_the_board_of_commissioners"  # noqa
    )

    for item in primary_items:
        assert item["source"] == "https://meeting.sparqdata.com/Public/Organization/201"
        assert item["time_notes"] == ""


def test_secondary_items(secondary_items):
    assert len(secondary_items) > 0

    cancelled = [i for i in secondary_items if i["status"] == "cancelled"]
    assert len(cancelled) > 0

    for item in secondary_items:
        assert item["title"] == "Board of Commissioners"
        assert item["classification"] == BOARD
        assert item["location"] == {"name": "", "address": ""}
        assert (
            item["source"]
            == "https://ohauthority.org/about-oha/board-of-commissioners/board-meetings/"  # noqa
        )
        assert item["time_notes"] == (
            "Please refer to the meeting attachments for more accurate meeting time and location."  # noqa
        )


def test_links(parsed_items):
    for item in parsed_items:
        assert isinstance(item["links"], list)

    items_with_links = [i for i in parsed_items if i["links"]]
    assert len(items_with_links) > 0
    for item in items_with_links:
        for link in item["links"]:
            assert "href" in link
            assert "title" in link
            assert link["href"].startswith("http")
            assert link["title"] != ""


def test_all_items(parsed_items):
    cutoff = 2026 - 2
    for item in parsed_items:
        assert isinstance(item["start"], datetime)
        assert item["start"].year >= cutoff
        assert item["id"] != ""
        assert item["status"] != ""

    for item in parsed_items[:10]:
        assert item["all_day"] is False
