from datetime import datetime
from os.path import dirname, join

from city_scrapers_core.utils import file_response
from freezegun import freeze_time

from city_scrapers.spiders.omaha_planning import OmahaPlanningAppeals

test_response = file_response(
    join(dirname(__file__), "files", "omaha_planning.html"),
    url="https://planning.cityofomaha.org/boards/administrative-board-of-appeals",
)
spider = OmahaPlanningAppeals()

freezer = freeze_time("2022-08-09")
freezer.start()

parsed_items = [item for item in spider.parse(test_response)]

freezer.stop()


def test_title():
    assert parsed_items[0]["title"] == "January 24, 2022"


def test_start():
    assert parsed_items[0]["start"] == datetime(2022, 1, 24, 13, 0)


def test_location():
    assert parsed_items[0]["location"] == {"address": "1819 Farnam Street"}


def test_links():
    assert parsed_items[0]["links"] == [
        {
            "href": "https://planning.cityofomaha.org//images/Jan_24_2022_Agenda.pdf",
            "title": "Agenda",
        },
        {
            "href": (
                "https://planning.cityofomaha.org//images/"
                "ABA_Disposition_1-24-2022.pdf"
            ),
            "title": "Disposition Agenda",
        },
        {
            "href": "https://planning.cityofomaha.org//images/1-24-2022_Minutes.pdf",
            "title": "Minutes",
        },
    ]
