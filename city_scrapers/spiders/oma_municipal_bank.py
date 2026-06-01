from zoneinfo import ZoneInfo

import scrapy
# from pytz import timezone
from city_scrapers_core.constants import BOARD
from city_scrapers_core.items import Meeting
from city_scrapers_core.spiders import CityScrapersSpider
from dateutil.parser import parse as parse_date


class OmaMunicipalBankSpider(CityScrapersSpider):
    name = "oma_municipal_bank"
    agency = "Omaha Municipal Land Bank"
    timezone = "America/Chicago"
    start_url = "https://omahalandbank.org/get-involved/board-meetings/"
    custom_settings = {
        "FEED_EXPORT_ENCODING": "utf-8",
    }
    location = {
        "name": (
            "Metropolitan Community College - "
            "Fort Omaha Campus - Mule Barn Building 21 - Room 112"
        ),
        "address": "5300 North 30th Street, Omaha, NE 68111",
    }
    # def _tz(self):
    #     return timezone(self.timezone)
    tz = ZoneInfo(timezone)

    def start_requests(self):
        # self.seen_ids = set()

        yield scrapy.Request(self.start_url, callback=self.parse)

    def parse(self, response):
        """Parse all meetings: tentative (follow Eventbrite) and archived (follow detail)."""  # noqa
        time_notes = self._parse_time_notes(response)

        # Tentative: follow Eventbrite page to get exact start time
        for a in response.css("a.et_pb_button[href*='eventbrite']"):
            date_text = a.css("::text").get("").strip()
            href = a.attrib.get("href", "").strip()
            if not date_text or not href:
                continue
            yield scrapy.Request(
                href,
                callback=self._parse_tentative_detail,
                meta={"date_text": date_text, "source": href},
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
                meta={"start": start, "time_notes": time_notes},
            )

    def _parse_tentative_detail(self, response):
        """Parse start time and description from Eventbrite detail page."""
        dt_attr = response.css("time[datetime]::attr(datetime)").get("")
        start = (
            self._parse_dt(dt_attr)
            if dt_attr
            else self._parse_dt(f"{response.meta['date_text']} 9:00 AM")
        )
        description = " ".join(
            t.strip()
            for t in response.css("[class*='Overview_summary'] p::text").getall()
            if t.strip()
        )
        if start:
            meeting = self._build_meeting(
                start=start,
                links=[],
                source=response.meta["source"],
                description=description,
            )
            if meeting:
                yield meeting

    def _parse_archived_detail(self, response):
        """Parse archived meeting detail page for links/attachments."""
        if response.url == "https://omahalandbank.org/project/july-12/":
            return  # Skip this page which is incorrect

        links = [
            {"href": a.attrib["href"].strip(), "title": a.css("::text").get("").strip()}
            for a in response.css("a.et_pb_button")
            if a.attrib.get("href")
        ]
        if not links:
            self.logger.warning(f"No links found for archived meeting: {response.url}")
            return

        meeting = self._build_meeting(
            start=response.meta["start"],
            links=links,
            source=self.start_url,
            time_notes=response.meta["time_notes"],
            # deduplicate=True,
        )
        if meeting:
            yield meeting

    def _build_meeting(self, start, links, source, time_notes="", description=""):
        meeting = Meeting(
            title="Board Meeting",
            description=description,
            classification=BOARD,
            start=start,
            end=None,
            all_day=False,
            time_notes=time_notes,
            location=self.location,
            links=links,
            source=source,
        )
        meeting["status"] = self._get_status(meeting)
        meeting["id"] = self._get_id(meeting)

        # if deduplicate:
        #     # Always prefer the version with links:
        #     # - if this meeting has links, register it and yield
        #     # - if this meeting has no links and we've already seen it, skip
        #     # - if this meeting has no links and it's new, register it tentatively
        #     if links:
        #         self.seen_ids.add(meeting["id"])
        #         return meeting
        #     if meeting["id"] in self.seen_ids:
        #         return None
        #     self.seen_ids.add(meeting["id"])
        meeting["status"] = self._get_status(meeting)
        meeting["id"] = self._get_id(meeting)
        return meeting

    def _parse_time_notes(self, response):
        for p in response.css(".et_pb_header_content_wrapper p"):
            text = " ".join(t.strip() for t in p.css("::text").getall() if t.strip())
            if text:
                return text
        return ""

    def _parse_start(self, item):
        """Parse start date (no time) from an archived portfolio card."""
        date_text = (
            item.css("h2.et_pb_module_header a::text").get("").strip().rstrip(",")
        )
        year = item.css('p.post-meta a[href*="project_category/20"]::text').get("")
        return self._parse_dt(f"{date_text} {year}") if date_text and year else None

    def _parse_dt(self, text):
        """Parse a datetime string, logging a warning on failure."""
        try:
            dt = parse_date(text)
            if dt.tzinfo:
                dt = dt.astimezone(self.tz).replace(tzinfo=None)
            return dt
        except Exception:
            self.logger.warning(f"Could not parse date: {text}")
            return None
