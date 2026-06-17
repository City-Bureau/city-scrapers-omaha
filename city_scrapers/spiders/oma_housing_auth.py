import re
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from city_scrapers_core.constants import BOARD
from city_scrapers_core.items import Meeting
from city_scrapers_core.spiders import CityScrapersSpider
from dateutil.parser import parse


class OmaHousingAuthSpider(CityScrapersSpider):
    name = "oma_housing_auth"
    agency = "Omaha Housing Authority"
    timezone = "America/Chicago"
    start_urls = ["https://meeting.sparqdata.com/Public/Organization/201"]
    base_url = "https://meeting.sparqdata.com"
    links_and_tentative_meetings_url = (
        "https://ohauthority.org/about-oha/board-of-commissioners/board-meetings/"
    )

    custom_settings = {"ROBOTSTXT_OBEY": False}

    SECONDARY_TIME_NOTES = "Please refer to the meeting attachments for more accurate meeting time and location."  # noqa

    tz = ZoneInfo(timezone)

    def _clean_text(self, text):
        return re.sub(r"\s+", " ", text).strip() if text else ""

    def parse(self, response):
        cutoff_year = datetime.now(self.tz).year - 2
        raw_meetings = []

        for item in response.css("table tbody tr[class*='row-for-board']"):
            start, has_explicit_time = self._parse_start(item)
            if not start or start.year < cutoff_year:
                continue
            raw_meetings.append(
                {
                    "title": self._parse_title(item),
                    "start": start,
                    "has_explicit_time": has_explicit_time,
                    "location": self._parse_location(item),
                    "links": [],
                    "source": response.url,
                }
            )

        date_groups = defaultdict(list)
        for i, m in enumerate(raw_meetings):
            date_groups[m["start"].date()].append(i)

        for indices in date_groups.values():
            explicit_times = [
                raw_meetings[i]["start"]
                for i in indices
                if raw_meetings[i]["has_explicit_time"]
            ]
            if explicit_times:
                shared_time = explicit_times[0]
                for i in indices:
                    if not raw_meetings[i]["has_explicit_time"]:
                        orig = raw_meetings[i]["start"]
                        raw_meetings[i]["start"] = orig.replace(
                            hour=shared_time.hour,
                            minute=shared_time.minute,
                            second=shared_time.second,
                        )

        yield response.follow(
            self.links_and_tentative_meetings_url,
            callback=self._links_and_tentative_meetings_page,
            cb_kwargs={"raw_meetings": raw_meetings},
        )

    def _links_and_tentative_meetings_page(self, response, raw_meetings):
        cutoff_year = datetime.now(self.tz).year - 2
        secondary_by_date = {}

        for section in response.css("div.usa-text"):
            for row in section.css("table tr"):
                date, start = self._parse_secondary_url_date_and_time(row)
                if not date or start.year < cutoff_year:
                    continue

                tds = row.css("td")
                agenda_cell = tds[0] if tds else None
                if not agenda_cell:
                    continue
                agenda_text = self._clean_text(
                    agenda_cell.xpath("string()").get() or ""
                )
                cancelled = bool(re.search(r"CANCELL?ED", agenda_text.upper()))

                links = [
                    {
                        "href": a.attrib["href"],
                        "title": self._clean_text(a.css("::text").get()),
                    }
                    for a in row.css("td a")
                    if a.attrib.get("href") and a.css("::text").get()
                ]

                # Split links by type
                annual_links = [l for l in links if "annual" in l["title"].lower()]
                regular_links = [l for l in links if "annual" not in l["title"].lower()]

                secondary_by_date[date] = {
                    "start": start,
                    "links": links,
                    "annual_links": annual_links,
                    "regular_links": regular_links,
                    "cancelled": cancelled,
                }

        primary_dates = {m["start"].date() for m in raw_meetings}

        # Enrich primary meetings with links from secondary
        for m in raw_meetings:
            if m["start"].date() in secondary_by_date:
                data = secondary_by_date[m["start"].date()]
                m["cancelled"] = data["cancelled"]
                if "annual" in m["title"].lower():
                    m["links"] = data["annual_links"]
                else:
                    m["links"] = data["regular_links"]
            else:
                m["cancelled"] = False

        for m in raw_meetings:
            yield self._build_meeting(
                title=m["title"],
                start=m["start"],
                time_notes="",
                location=m["location"],
                links=m["links"],
                source=m["source"],
                cancelled=m["cancelled"],
            )

        for date, data in secondary_by_date.items():
            if date in primary_dates:
                continue
            yield self._build_meeting(
                title="Board of Commissioners",
                start=data["start"],
                time_notes=self.SECONDARY_TIME_NOTES,
                location={"name": "", "address": ""},
                links=data["links"],
                cancelled=data["cancelled"],
                source=self.links_and_tentative_meetings_url,
            )

    def _build_meeting(
        self, title, start, time_notes, location, links, source, cancelled=False
    ):
        meeting = Meeting(
            title=title,
            description="",
            classification=BOARD,
            start=start,
            end=None,
            all_day=False,
            time_notes=time_notes,
            location=location,
            links=links,
            source=source,
        )
        meeting["status"] = self._get_status(
            meeting, text="cancelled" if cancelled else ""
        )
        meeting["id"] = self._get_id(meeting)
        return meeting

    def _parse_secondary_url_date_and_time(self, row):
        th = row.css("th[scope='row']")
        if not th:
            return None, None
        raw = th.xpath("text()[1]").get()
        if not raw:
            return None, None
        raw = self._clean_text(raw)

        time_match = re.search(r"@\s*(\d+(?::\d+)?\s*[ap]m)", raw, re.IGNORECASE)
        date_str = re.sub(r"[*@].*$", "", raw).strip()

        try:
            dt = (
                parse(f"{date_str} {time_match.group(1)}", fuzzy=True)
                if time_match
                else parse(date_str, fuzzy=True).replace(hour=0, minute=0, second=0)
            )
            return dt.date(), dt
        except Exception:
            self.logger.warning(f"Failed to parse date/time from: {raw}")
            return None, None

    def _parse_title(self, item):
        tds = item.css("td")
        if not tds:
            return ""
        text = tds[0].css("div").xpath("string()").get()
        if not text:
            return ""
        text = text.strip()
        return text.split(" - ", 1)[1].strip() if " - " in text else text

    def _parse_start(self, item):
        tds = item.css("td")
        if not tds:
            return None, False
        text = tds[0].css("div").xpath("string()").get()
        if not text:
            return None, False
        text = text.strip()
        match = re.search(r"(\w+ \d+, \d{4})", text)
        if match:
            date_str = match.group(1)
            time_match = re.search(r"at (\d+:\d+ [AP]M)", text)
            if time_match:
                return parse(f"{date_str} {time_match.group(1)}"), True
            return parse(f"{date_str} 12:00 AM"), False
        self.logger.warning("Could not parse start date from: %r", text)
        return None, False

    def _parse_location(self, item):
        tds = item.css("td")
        if len(tds) < 2:
            return {"name": "", "address": ""}
        location_td = tds[1]
        spans = [
            self._clean_text(t)
            for t in location_td.css("span::text").getall()
            if self._clean_text(t) not in ("", "[", "]")
        ]
        name = spans[0] if spans else ""
        address = ", ".join(spans[1:])
        return {"name": name, "address": address}
