from datetime import datetime
from os.path import dirname, join

import pytest
from city_scrapers_core.utils import file_response
from freezegun import freeze_time

from city_scrapers.spiders.omaha_planning import (
    OmahaPlanningAir,
    OmahaPlanningAppeals,
    OmahaPlanningBuildingReview,
    OmahaPlanningElectrical,
    OmahaPlanningLandmarks,
)

test_response = file_response(
    join(dirname(__file__), "files", "omaha_planning_appeals.html"),
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


@pytest.mark.parametrize(
    "cls, file, first_meeting",
    [
        (
            OmahaPlanningAppeals,
            "omaha_planning_appeals.html",
            datetime(2022, 1, 24, 13, 0),
        ),
        (OmahaPlanningAir, "omaha_planning_air.html", datetime(2022, 1, 4, 13, 30)),
        (
            OmahaPlanningBuildingReview,
            "omaha_planning_building.html",
            datetime(2022, 1, 10, 13, 0),
        ),
        (
            OmahaPlanningElectrical,
            "omaha_planning_electrical.html",
            datetime(2022, 4, 15, 13, 30),
        ),
        (
            OmahaPlanningLandmarks,
            "omaha_planning_landmarks.html",
            datetime(2022, 1, 12, 13, 30),
        ),
    ],
)
def test_planning_subclasses(cls, file, first_meeting):
    test_response = file_response(
        join(dirname(__file__), "files", file), url="https://not-used.example"
    )
    spider = cls()
    parsed_items = [item for item in spider.parse(test_response)]

    assert parsed_items[0]["start"] == first_meeting
