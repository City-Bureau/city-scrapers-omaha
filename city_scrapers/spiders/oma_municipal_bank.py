import scrapy
from city_scrapers_core.constants import BOARD
from city_scrapers_core.items import Meeting
from city_scrapers_core.spiders import CityScrapersSpider
from dateutil.parser import parse as parse_date


class OmaMunicipalBankSpider(CityScrapersSpider):
    name = "oma_municipal_bank"
    agency = "Omaha Municipal Land Bank"
    timezone = "America/Chicago"
    start_url = "https://omahalandbank.org/get-involved/board-meetings/"
    location = {
        "name": (
            "Metropolitan Community College - "
            "Fort Omaha Campus - Mule Barn Building 21 - Room 112"
        ),
        "address": "5300 North 30th Street, Omaha, NE 68111",
    }

    def start_requests(self):
        yield scrapy.Request(self.start_url, callback=self.parse)

    def parse(self, response):
        """Parse all meetings: tentative (inline) and archived (via follow)."""
        # Tentative: full data available on main page
        for a in response.css("a.et_pb_button[href*='eventbrite']"):
            date_text = a.css("::text").get("").strip()
            href = a.attrib.get("href", "").strip()
            if not date_text or not href:
                continue
            start = self._parse_dt(f"{date_text} 9:00 AM")
            if start:
                yield self._build_meeting(
                    start=start,
                    links="",
                    source=href,
                )

        # Archived: follow detail page to get links/attachments
        for item in response.css(".et_pb_portfolio_item"):
            start = self._parse_start(item)
            detail_url = item.css("h2.et_pb_module_header a::attr(href)").get()
            if not start or not detail_url:
                continue
            yield response.follow(
                detail_url,
                callback=self._parse_archived_detail,
                meta={"start": start, "source": detail_url},
            )

    def _parse_archived_detail(self, response):
        """Parse archived meeting detail page for links/attachments."""
        links = [
            {"href": a.attrib["href"].strip(), "title": a.css("::text").get("").strip()} # noqa
            for a in response.css("a.et_pb_button")
            if a.attrib.get("href")
        ]
        yield self._build_meeting(
            start=response.meta["start"],
            links=links,
            source=response.meta["source"],
        )

    def _build_meeting(self, start, links, source):
        meeting = Meeting(
            title="Board Meeting",
            description="",
            classification=BOARD,
            start=start,
            end=None,
            all_day=False,
            time_notes="",
            location=self.location,
            links=links,
            source=source,
        )
        meeting["status"] = self._get_status(meeting)
        meeting["id"] = self._get_id(meeting)
        return meeting

    def _parse_start(self, item):
        """Parse start datetime from an archived portfolio card."""
        date_text = (
            item.css("h2.et_pb_module_header a::text").get("").strip().rstrip(",")
        )
        year = item.css('p.post-meta a[href*="project_category/20"]::text').get("")
        return (
            self._parse_dt(f"{date_text} {year} 9:00 AM")
            if date_text and year
            else None
        )

    def _parse_dt(self, text):
        """Parse a datetime string, logging a warning on failure."""
        try:
            return parse_date(text)
        except Exception:
            self.logger.warning(f"Could not parse date: {text}")
            return None
