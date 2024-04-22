from datetime import datetime
from os.path import dirname, join

import pytest
from city_scrapers_core.constants import NOT_CLASSIFIED, PASSED
from city_scrapers_core.utils import file_response
from freezegun import freeze_time

from city_scrapers.spiders.oma_mud import OmahaMudSpider

test_response = file_response(
    join(dirname(__file__), "files", "oma_mud.html"),
    url="https://www.mudomaha.com/about-us/board-meetings/",
)
spider = OmahaMudSpider()

freezer = freeze_time("2024-04-22")
freezer.start()

parsed_items = [item for item in spider.parse(test_response)]
parsed_item = parsed_items[0]
freezer.stop()


def test_title():
    assert parsed_item["title"] == "Committee and Board meetings"


def test_description():
    assert (
        parsed_item["description"].strip()
        == "Committee meetings 8:15 a.m. Board meeting 9:00 a.m."
    )


def test_start():
    assert parsed_item["start"] == datetime(2024, 4, 3, 8, 15)


def test_end():
    assert parsed_item["end"] is False


def test_time_notes():
    assert parsed_item["time_notes"] == ""


def test_id():
    assert (
        parsed_item["id"] == "oma_mud/202404030815/x/committee_and_board_meetings"
    )  # noqa


def test_status():
    assert parsed_item["status"] == PASSED


def test_location():
    expected_location = {
        "address": "7350 World Communications Drive",
        "name": "Metropolitan Utilities District",
    }
    assert parsed_item["location"] == expected_location


def test_source():
    assert parsed_item["source"] == "https://www.mudomaha.com/about-us/board-meetings/"


def test_links():
    expected_links = [
        {
            "href": "https://www.mudomaha.com/wp-content/uploads/2024/04/April-Documents-for-Website_Draft-2.pdf",  # noqa
            "title": "Documents",
        },
        {
            "href": "https://www.youtube.com/watch?v=9W6tryNGKDw",
            "title": "Video",
        },
    ]
    assert parsed_item["links"] == expected_links


def test_classification():
    assert parsed_item["classification"] == NOT_CLASSIFIED


@pytest.mark.parametrize("item", parsed_items)
def test_all_day(item):
    assert not item["all_day"]
