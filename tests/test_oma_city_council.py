from datetime import date, datetime
from os.path import dirname, join

import pytest
from city_scrapers_core.constants import CITY_COUNCIL
from city_scrapers_core.utils import file_response
from freezegun import freeze_time

from city_scrapers.spiders.oma_city_council import OmaCityCouncilSpider


@pytest.fixture
def spider():
    return OmaCityCouncilSpider()


@pytest.fixture
def city_council_meeting(spider):
    response = file_response(
        join(dirname(__file__), "files", "oma_city_council_meeting.html"),
        url="https://citycouncil.cityofomaha.org/council-calender/icalrepeat.detail/2024/05/21/853/73/city-council-meeting",  # noqa
    )
    with freeze_time("2026-06-03"):
        return next(
            spider.parse_detail(
                response,
                title="City Council Meeting",
                start=datetime(2024, 5, 21, 14, 0),
                end=None,
                links=[],
                source=response.url,
            )
        )


@pytest.fixture
def pre_council_meeting(spider):
    response = file_response(
        join(dirname(__file__), "files", "oma_pre_council_meeting.html"),
        url="https://citycouncil.cityofomaha.org/council-calender/icalrepeat.detail/2026/12/15/1139/73/pre-council-meeting",  # noqa
    )
    with freeze_time("2026-06-03"):
        return next(
            spider.parse_detail(
                response,
                title="Pre-Council Meeting",
                start=datetime(2026, 12, 15, 10, 30),
                end=datetime(2026, 12, 15, 11, 0),
                links=[],
                source=response.url,
            )
        )


@pytest.fixture
def city_council_meeting_with_agenda():
    spider_with_links = OmaCityCouncilSpider()
    agendas_response = file_response(
        join(dirname(__file__), "files", "oma_city_council_agendas.html"),
        url="https://cityclerk.cityofomaha.org/category/city-council-downloads/agendas/2024-agendas/",  # noqa
    )
    spider_with_links.parse_links(agendas_response, link_title="Agenda")

    links = spider_with_links._sort_links(
        spider_with_links.links_by_date.get(date(2024, 5, 21), [])
    )

    detail_response = file_response(
        join(dirname(__file__), "files", "oma_city_council_meeting.html"),
        url="https://citycouncil.cityofomaha.org/council-calender/icalrepeat.detail/2024/05/21/853/73/city-council-meeting",  # noqa
    )
    with freeze_time("2026-06-03"):
        return next(
            spider_with_links.parse_detail(
                detail_response,
                title="City Council Meeting",
                start=datetime(2024, 5, 21, 14, 0),
                end=None,
                links=links,
                source=detail_response.url,
            )
        )


def test_city_council_meeting_title(city_council_meeting):
    assert city_council_meeting["title"] == "City Council Meeting"


def test_city_council_meeting_classification(city_council_meeting):
    assert city_council_meeting["classification"] == CITY_COUNCIL


def test_city_council_meeting_start(city_council_meeting):
    assert city_council_meeting["start"] == datetime(2024, 5, 21, 14, 0)


def test_city_council_meeting_end(city_council_meeting):
    assert city_council_meeting["end"] is None


def test_city_council_meeting_location(city_council_meeting):
    assert city_council_meeting["location"] == {
        "name": "LC-4, Legislative Chambers of the Omaha/Douglas Civic Center",
        "address": "1819 Farnam St, Omaha, NE 68183",
    }


def test_city_council_meeting_time_notes(city_council_meeting):
    assert city_council_meeting["time_notes"] == ""


def test_city_council_meeting_status(city_council_meeting):
    assert city_council_meeting["status"] == "passed"


def test_city_council_meeting_source(city_council_meeting):
    assert city_council_meeting["source"] == (
        "https://citycouncil.cityofomaha.org/council-calender/icalrepeat.detail/2024/05/21/853/73/city-council-meeting"  # noqa
    )


def test_city_council_meeting_all_day(city_council_meeting):
    assert city_council_meeting["all_day"] is False


def test_pre_council_meeting_title(pre_council_meeting):
    assert pre_council_meeting["title"] == "Pre-Council Meeting"


def test_pre_council_meeting_classification(pre_council_meeting):
    assert pre_council_meeting["classification"] == CITY_COUNCIL


def test_pre_council_meeting_start(pre_council_meeting):
    assert pre_council_meeting["start"] == datetime(2026, 12, 15, 10, 30)


def test_pre_council_meeting_end(pre_council_meeting):
    assert pre_council_meeting["end"] == datetime(2026, 12, 15, 11, 0)


def test_pre_council_meeting_location(pre_council_meeting):
    assert pre_council_meeting["location"] == {
        "name": "Jesse Lowe Conference Room on the 3rd Floor",
        "address": "1819 Farnam St, Omaha, NE 68183",
    }


def test_pre_council_meeting_time_notes(pre_council_meeting):
    assert pre_council_meeting["time_notes"] == ""


def test_pre_council_meeting_status(pre_council_meeting):
    assert pre_council_meeting["status"] == "tentative"


def test_pre_council_meeting_source(pre_council_meeting):
    assert pre_council_meeting["source"] == (
        "https://citycouncil.cityofomaha.org/council-calender/icalrepeat.detail/2026/12/15/1139/73/pre-council-meeting"  # noqa
    )


def test_pre_council_meeting_all_day(pre_council_meeting):
    assert pre_council_meeting["all_day"] is False


@pytest.fixture
def calendar_requests(spider):
    response = file_response(
        join(dirname(__file__), "files", "oma_city_council_calendar.html"),
        url="https://citycouncil.cityofomaha.org/council-calender/month.calendar/2024/05/01/73",  # noqa
    )
    with freeze_time("2026-06-10"):
        return list(spider.parse(response))


def test_calendar_request_count(calendar_requests):
    assert len(calendar_requests) == 2


def test_calendar_city_council_start(calendar_requests):
    req = next(
        r for r in calendar_requests if r.cb_kwargs["title"] == "City Council Meeting"
    )
    assert req.cb_kwargs["start"] == datetime(2024, 5, 21, 14, 0)


def test_calendar_city_council_end(calendar_requests):
    req = next(
        r for r in calendar_requests if r.cb_kwargs["title"] == "City Council Meeting"
    )
    assert req.cb_kwargs["end"] == datetime(2024, 5, 21, 17, 0)


def test_calendar_pre_council_start(calendar_requests):
    req = next(
        r for r in calendar_requests if r.cb_kwargs["title"] == "Pre-Council Meeting"
    )
    assert req.cb_kwargs["start"] == datetime(2024, 5, 21, 10, 30)


def test_calendar_pre_council_end(calendar_requests):
    req = next(
        r for r in calendar_requests if r.cb_kwargs["title"] == "Pre-Council Meeting"
    )
    assert req.cb_kwargs["end"] == datetime(2024, 5, 21, 11, 0)


def test_calendar_pre_council_links_empty(calendar_requests):
    req = next(
        r for r in calendar_requests if r.cb_kwargs["title"] == "Pre-Council Meeting"
    )
    assert req.cb_kwargs["links"] == []


def test_parse_dt_start(spider):
    assert spider._parse_dt(
        "2:00pm - 5:00pm", "/2024/5/21/853/", start=True
    ) == datetime(2024, 5, 21, 14, 0)


def test_parse_dt_end(spider):
    assert spider._parse_dt(
        "2:00pm - 5:00pm", "/2024/5/21/853/", start=False
    ) == datetime(2024, 5, 21, 17, 0)


def test_parse_dt_single_digit_month_day(spider):
    assert spider._parse_dt("10:30am", "/2024/5/7/853/", start=True) == datetime(
        2024, 5, 7, 10, 30
    )


def test_parse_dt_no_end_without_range(spider):
    assert spider._parse_dt("2:00pm", "/2024/5/21/853/", start=False) is None


def test_city_council_meeting_agenda_link(city_council_meeting_with_agenda):
    assert {
        "href": "https://cityclerk.cityofomaha.org/wp-content/uploads/images/2024-05-21a2.pdf",  # noqa
        "title": "Agenda",
    } in city_council_meeting_with_agenda["links"]
