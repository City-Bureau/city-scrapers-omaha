from datetime import datetime
from os.path import dirname, join

from city_scrapers_core.utils import file_response
from freezegun import freeze_time

from city_scrapers.spiders.oma_examining import OmahaPlanningExaminersPipefitters

test_response = file_response(
    join(dirname(__file__), "files", "steamfitters-examining-board.html"),
    url="https://planning.cityofomaha.org/boards/steamfitters-examining-board",
)
spider = OmahaPlanningExaminersPipefitters()

freezer = freeze_time("2022-09-11")
freezer.start()

parsed_items = [item for item in spider.parse(test_response)]

freezer.stop()


def test_title():
    assert parsed_items[0]["title"] == "February 4, 2022"


def test_start():
    assert parsed_items[0]["start"] == datetime(2022, 2, 4, 13, 0)


def test_location():
    assert parsed_items[0]["location"] == {
        "address": "11th Floor - Central Conference Room; Omaha-Douglas Civic Center, 1819 Farnam Street",  # noqa
        "name": "",
    }


def test_links():
    assert parsed_items[0]["links"] == [
        {
            "href": "https://planning.cityofomaha.org/images/2021_SteamfitterPipefitter_Board/4-1-22_SP_Minutes.pdf",  # noqa
            "title": "Minutes",
        },
    ]
