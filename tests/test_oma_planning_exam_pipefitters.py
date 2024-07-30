from datetime import datetime
from os.path import dirname, join

import pytest
from city_scrapers_core.constants import NOT_CLASSIFIED, PASSED
from city_scrapers_core.utils import file_response
from freezegun import freeze_time

from city_scrapers.spiders.oma_planning_exam_pipefitters import (
    OmahaPlanningExaminersEngineersSpider,
)

test_response = file_response(
    join(dirname(__file__), "files", "oma_planning_exam_pipefitters.html"),
    url="https://planning.cityofomaha.org/boards/board-of-examiners-for-engineers",
)
spider = OmahaPlanningExaminersEngineersSpider()

freezer = freeze_time(datetime(2024, 7, 30, 11, 38))
freezer.start()

parsed_items = [item for item in spider.parse(test_response)]
parsed_item = parsed_items[0]
freezer.stop()


def test_title():
    assert parsed_item["title"] == "Steamfitters/Pipefitters Board meeting"


def test_description():
    assert parsed_item["description"] == ""


def test_start():
    assert parsed_item["start"] == datetime(2024, 1, 9, 13, 0)


def test_end():
    assert parsed_item["end"] is None


def test_time_notes():
    assert parsed_item["time_notes"] == ""


def test_id():
    assert (
        parsed_item["id"]
        == "oma_planning_exam_pipefitters/202401091300/x/steamfitters_pipefitters_board_meeting"  # noqa
    )


def test_status():
    assert parsed_item["status"] == PASSED


def test_location():
    assert parsed_item["location"] == {
        "name": "",
        "address": "11th Floor - Central Conference Room, Omaha-Douglas Civic Center, 1819 Farnam Street",  # noqa
    }


def test_source():
    assert (
        parsed_item["source"]
        == "https://planning.cityofomaha.org/boards/board-of-examiners-for-engineers"
    )


def test_links():
    assert parsed_item["links"] == []


def test_classification():
    assert parsed_item["classification"] == NOT_CLASSIFIED


@pytest.mark.parametrize("item", parsed_items)
def test_all_day(item):
    assert item["all_day"] is False
