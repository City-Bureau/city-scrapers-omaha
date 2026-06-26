import re
from datetime import datetime

import scrapy
from city_scrapers_core.constants import BOARD, CANCELLED
from city_scrapers_core.items import Meeting
from city_scrapers_core.spiders import CityScrapersSpider
from dateutil import tz
from dateutil.parser import parse as dateutil_parse


class OmaPublicSchoolsBoeSpider(CityScrapersSpider):
    name = "oma_public_schools_boe"
    agency = "Omaha Public Schools Board of Education"
    timezone = "America/Chicago"
    upcoming_meetings_url = "https://www.ops.org/board/upcoming-meetings-and-livestream"
    past_meetings_url = "https://meeting.sparqdata.com/Public/Organization/120"
    youtube_playlist_url = (
        "https://www.youtube.com/playlist?list=PLznBr7jR8aKWxFFAXV3aeXG45JzJ9Iboy"
    )

    start_year = 2020

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
    }

    def __init__(self, *args, **kwargs):
        self._past_meeting_starts = set()
        super().__init__(*args, **kwargs)

    def start_requests(self):
        yield scrapy.Request(
            self.past_meetings_url,
            callback=self.parse_past_meetings,
            errback=self._past_meetings_errback,
        )

    def _past_meetings_errback(self, failure):
        self.logger.error("SparqData request failed: %s", failure.request.url)
        yield scrapy.Request(self.upcoming_meetings_url, callback=self.parse)

    def parse_past_meetings(self, response):
        """Parse past meetings from SparqData and yield Meeting objects."""
        rows = response.css("tr.row-for-board")

        if not rows:
            self.logger.warning(
                f"No SparqData past meeting rows found on {response.url}"
            )
            yield scrapy.Request(self.upcoming_meetings_url, callback=self.parse)
            return

        for row in rows:
            raw = (
                row.css("td:first-child div:first-child")
                .xpath("string()")
                .get("")
                .strip()
            )
            if not raw:
                continue

            is_cancelled = "cancelled" in raw.lower() or "canceled" in raw.lower()
            clean_raw = re.sub(
                r"cancelled|canceled", "", raw, flags=re.IGNORECASE
            ).strip(
                " -"
            )  # noqa

            if " - " in clean_raw:
                date_time_part, title = clean_raw.split(" - ", 1)
                title = title.strip()
            else:
                date_time_part = clean_raw
                title = "Board Meeting"

            date_time_part = date_time_part.strip().replace(" at ", " ")
            try:
                start = dateutil_parse(date_time_part)
            except Exception:
                self.logger.error(f"Failed to parse date from: {raw!r}")
                continue

            if start.year < self.start_year:
                continue

            links = [
                {
                    "href": f"https://meeting.sparqdata.com{a.attrib['href']}",
                    "title": a.css("::text").get("").strip() or "Attachment",
                }
                for a in row.css("td:nth-child(3) a")
                if a.attrib.get("href", "").startswith("/")
            ]
            links.append(
                {"href": self.youtube_playlist_url, "title": "YouTube Playlist"}
            )

            meeting = self._build_meeting(
                title=title,
                start=start,
                end=None,
                location=self._parse_past_meetings_location(row),
                links=links,
                source=self.past_meetings_url,
                is_cancelled=is_cancelled,
            )
            self._past_meeting_starts.add(start.replace(tzinfo=None))
            yield meeting

        yield scrapy.Request(
            self.upcoming_meetings_url,
            callback=self.parse,
        )

    def parse(self, response):
        yield from self._parse_upcoming_meetings(response)
        yield from self._follow_load_more(response)

    def parse_more_events(self, response):
        """Parse Finalsite Load More HTML fragment and request the next batch."""
        meetings = list(self._parse_upcoming_meetings(response))
        if not meetings:
            return
        yield from meetings

        btn = response.css("button.fsLoadMoreButton")
        if not btn:
            return
        next_start_row = btn.attrib.get("data-start-row", "")
        if not next_start_row:
            return

        element_id = response.meta["element_id"]
        page_id = response.meta["page_id"]

        yield scrapy.Request(
            self._build_load_more_url(element_id, page_id, next_start_row),
            callback=self.parse_more_events,
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Referer": self.upcoming_meetings_url,
                "Accept": "text/html, */*; q=0.01",
            },
            meta={"element_id": element_id, "page_id": page_id},
            dont_filter=True,
        )

    def _parse_upcoming_meetings(self, selector):
        """Yield upcoming Meeting items from a selector."""
        for article in selector.css("article"):
            start = self._parse_dt(article.css("time.fsDate::attr(datetime)").get())
            if not start:
                continue

            if start.replace(tzinfo=None) in self._past_meeting_starts:
                continue

            title = article.css("a.fsCalendarEventLink::text").get("").strip()
            if not title:
                title = "Board Meeting"

            yield self._build_meeting(
                title=title,
                start=start,
                end=self._parse_dt(article.css("time.fsEndTime::attr(datetime)").get()),
                location=self._parse_upcoming_location(article),
                links=[],
                source=self.upcoming_meetings_url,
            )

    def _follow_load_more(self, response):
        """Follow Finalsite's Load More endpoint for upcoming meetings."""
        btn = response.css("button.fsLoadMoreButton")
        if not btn:
            return

        start_row = btn.attrib.get("data-start-row", "")
        if not start_row:
            return

        section = response.css("section.fsCalendar")
        if not section:
            return

        element_id = section.attrib.get("id", "").replace("fsEl_", "")
        if not element_id:
            return

        page_id = self._get_page_id(response)
        if not page_id:
            self.logger.warning(
                "Could not determine Finalsite page_id; skipping Load More"
            )  # noqa
            return

        yield scrapy.Request(
            self._build_load_more_url(element_id, page_id, start_row),
            callback=self.parse_more_events,
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Referer": self.upcoming_meetings_url,
                "Accept": "text/html, */*; q=0.01",
            },
            meta={"element_id": element_id, "page_id": page_id},
            dont_filter=True,
        )

    def _build_load_more_url(self, element_id, page_id, start_row):
        timestamp = int(datetime.now().timestamp() * 1000)
        return (
            f"https://www.ops.org/fs/elements/{element_id}"
            f"?start_row={start_row}&is_draft=false&is_load_more=true"
            f"&page_id={page_id}&parent_id={element_id}&_={timestamp}"
        )

    def _get_page_id(self, response):
        """Extract Finalsite page_id from the page."""
        page_id = response.css("[data-pageid]::attr(data-pageid)").get()
        if page_id:
            return page_id

        match = re.search(r"page_id[\"']?\s*[:=]\s*[\"']?(\d+)", response.text)
        if match:
            return match.group(1)

        return None

    def _build_meeting(
        self, title, start, end, location, links, source, is_cancelled=False
    ):
        meeting = Meeting(
            title=title,
            description="",
            classification=BOARD,
            start=start,
            end=end,
            all_day=False,
            time_notes="",
            location=location,
            links=links,
            source=source,
        )
        meeting["status"] = CANCELLED if is_cancelled else self._get_status(meeting)
        meeting["id"] = self._get_id(meeting)
        return meeting

    def _parse_dt(self, dt_str):
        """Parse ISO 8601 datetime string to naive local datetime."""
        if not dt_str:
            return None
        try:
            dt = dateutil_parse(dt_str)
            if dt.tzinfo is not None:
                local_tz = tz.gettz(self.timezone)
                dt = dt.astimezone(local_tz).replace(tzinfo=None)
            return dt
        except Exception:
            self.logger.error(f"Failed to parse datetime: {dt_str}")
            return None

    def _parse_past_meetings_location(self, row):
        """Parse location from a SparqData table row."""
        name = row.css("td:nth-child(2) span[id$='-description']::text").get("").strip()
        line1 = row.css("td:nth-child(2) span[id$='-line1']::text").get("").strip()
        csz = row.css("td:nth-child(2) span[id$='-csz']::text").get("").strip()
        address = ", ".join(part for part in [line1, csz] if part)
        return {"name": name, "address": address}

    def _parse_upcoming_location(self, article):
        """Parse location from an upcoming-page article element."""
        location_text = article.css("div.fsLocation::text").get("").strip()
        if not location_text:
            return {"name": "", "address": ""}

        parts = location_text.split(",", 1)
        if parts[0].strip()[:1].isdigit():
            return {"name": "", "address": location_text}

        name = parts[0].strip()
        address = parts[1].strip() if len(parts) > 1 else location_text
        return {"name": name, "address": address}
