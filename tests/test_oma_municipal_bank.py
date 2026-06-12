from datetime import datetime
from os.path import dirname, join

import pytest
from city_scrapers_core.constants import BOARD, TENTATIVE
from city_scrapers_core.utils import file_response
from freezegun import freeze_time

from city_scrapers.spiders.oma_municipal_bank import OmaMunicipalBankSpider

START_URL = "https://omahalandbank.org/get-involved/board-meetings/"
EVENTBRITE_JUNE_URL = (
    "https://www.eventbrite.com/e/"
    "omaha-municipal-land-bank-board-meeting-tickets-1985378116391"
    "?aff=oddtdtcreator&keep_tld=true"
)

LOCATION = {
    "name": (
        "Metropolitan Community College - "
        "Fort Omaha Campus - Mule Barn Building 21 - Room 112"
    ),
    "address": "5300 North 30th Street, Omaha, NE 68111",
}

spider = OmaMunicipalBankSpider()


@pytest.fixture(scope="module")
def listing_requests():
    """All Scrapy requests yielded from the main listing page."""
    response = file_response(
        join(dirname(__file__), "files", "oma_municipal_bank.html"),
        url=START_URL,
    )
    with freeze_time("2026-06-01"):
        return list(spider.parse(response))


@pytest.fixture(scope="module")
def tentative_june():
    """Meeting parsed from June Eventbrite detail page."""
    response = file_response(
        join(dirname(__file__), "files", "oma_municipal_bank_eventbrite.html"),
        url=EVENTBRITE_JUNE_URL,
    )
    response.meta["date_text"] = "June 10, 2026"
    response.meta["source"] = EVENTBRITE_JUNE_URL
    with freeze_time("2026-06-01"):
        return list(spider._parse_tentative_detail(response))[0]


def test_yields_tentative_requests(listing_requests):
    eventbrite = [
        r for r in listing_requests if hasattr(r, "url") and "eventbrite" in r.url
    ]
    assert len(eventbrite) == 3


def test_listing_tentative_details_page_urls(listing_requests):
    urls = {
        r.url for r in listing_requests if hasattr(r, "url") and "eventbrite" in r.url
    }
    assert (
        "https://www.eventbrite.com/e/omaha-municipal-land-bank-board-meeting-tickets-1985378116391?aff=oddtdtcreator&keep_tld=true"  # noqa
        in urls
    )
    assert (
        "https://www.eventbrite.com/e/omaha-municipal-land-bank-board-meeting-tickets-1987354858881?aff=oddtdtcreator"  # noqa
        in urls
    )
    assert "https://www.eventbrite.com/e/1989847883585?aff=oddtdtcreator" in urls


def test_listing_archived_requests_count(listing_requests):
    archived = [
        r
        for r in listing_requests
        if hasattr(r, "url") and "omahalandbank.org/project/" in r.url
    ]
    assert len(archived) == 45


def test_listing_first_archived_url(listing_requests):
    archived = [
        r
        for r in listing_requests
        if hasattr(r, "url") and "omahalandbank.org/project/" in r.url
    ]
    assert archived[0].url == "https://omahalandbank.org/project/may-13/"


def test_listing_first_archived_start(listing_requests):
    """Start date is parsed from listing page and passed in request meta."""
    archived = [
        r
        for r in listing_requests
        if hasattr(r, "url") and "omahalandbank.org/project/" in r.url
    ]
    assert archived[0].meta["start"] == datetime(2026, 5, 13)


def test_listing_archived_has_time_notes(listing_requests):
    archived = [
        r
        for r in listing_requests
        if hasattr(r, "url") and "omahalandbank.org/project/" in r.url
    ]
    assert (
        "The Omaha Municipal Land Bank\u2019s Board of Directors meet at 9 AM on "
        "the second Wednesday of each month. Our board meetings are held at "
        "Metropolitan Community College \u2013 Fort Campus \u2013 Mule Barn Room 112."
    ) in archived[0].meta["time_notes"]


# --- Tentative meeting (June 10) ---


def test_tentative_identity(tentative_june):
    assert tentative_june["title"] == "Board Meeting"
    assert tentative_june["classification"] == BOARD
    assert tentative_june["status"] == TENTATIVE
    assert tentative_june["start"] == datetime(2026, 6, 10, 8, 30)
    assert tentative_june["end"] == datetime(2026, 6, 10, 11, 00)
    assert tentative_june["all_day"] is False
    assert tentative_june["location"] == LOCATION
    assert tentative_june["source"] == EVENTBRITE_JUNE_URL
    assert tentative_june["links"] == []
    assert (
        "Our monthly board meeting were we vote on items and discuss "
        "future plans with our board of directors. This is free and open "
        "to the public. For those who cannot attend in-person, we will be streaming "
        "our meeting via Zoom. Please see the link below to join: "
        "https://us02web.zoom.us/j/88260954305?pwd=TmgikhiIhaszWAOtlzUCocsFaXOuIm.1"
    ).lower() in tentative_june["description"].lower()


# --- Parametrized across tentative ---


@pytest.mark.parametrize("fixture_name", ["tentative_june"])
def test_all_day_false(fixture_name, request):
    assert request.getfixturevalue(fixture_name)["all_day"] is False


@pytest.mark.parametrize("fixture_name", ["tentative_june"])
def test_title_board_meeting(fixture_name, request):
    assert request.getfixturevalue(fixture_name)["title"] == "Board Meeting"


@pytest.mark.parametrize("fixture_name", ["tentative_june"])
def test_classification_board(fixture_name, request):
    assert request.getfixturevalue(fixture_name)["classification"] == BOARD


@pytest.mark.parametrize("fixture_name", ["tentative_june"])
def test_location_correct(fixture_name, request):
    assert request.getfixturevalue(fixture_name)["location"] == LOCATION
