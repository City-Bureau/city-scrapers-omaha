from datetime import datetime
from os.path import dirname, join

from city_scrapers_core.utils import file_response
from freezegun import freeze_time

from city_scrapers.spiders.oma_mud import OmahaMudSpider

test_response = file_response(
    join(dirname(__file__), "files", "omaha_mud.html"),
    url="https://www.mudomaha.com/our-company/board-of-directors/board-meetings",
)
spider = OmahaMudSpider()

freezer = freeze_time("2022-08-08")
freezer.start()

parsed_items = [item for item in spider.parse(test_response)]

freezer.stop()


def test_title():
    assert parsed_items[0]["title"] == "Board meeting"


def test_description():
    assert parsed_items[0]["description"] == "Committee meeting 8:15 a.m."


def test_start():
    assert parsed_items[0]["start"] == datetime(2022, 9, 7, 8, 15)
