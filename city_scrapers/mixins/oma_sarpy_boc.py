"""
Mixin and metaclass for Sarpy County Board of Commissioners spiders that share
a common CivicWeb data source.

Required class variables on child spiders:
    name (str): Spider name/slug
    agency (str): Full agency name for this board/commission
    agency_name (str): Parent organization name

"""

import json
import re
from datetime import date, datetime, timezone
from html import unescape
from urllib.parse import quote, urlencode

import scrapy
from city_scrapers_core.constants import (
    BOARD,
    CANCELLED,
    COMMISSION,
    COMMITTEE,
    NOT_CLASSIFIED,
)
from city_scrapers_core.items import Meeting
from city_scrapers_core.spiders import CityScrapersSpider
from dateutil.relativedelta import relativedelta


class OmaSarpyBocMixinMeta(type):
    """Metaclass that enforces required static variables on child spiders."""

    def __init__(cls, name, bases, dct):
        if name == "OmaSarpyBocMixin":
            super().__init__(name, bases, dct)
            return

        if any(getattr(base, "__name__", "") == "OmaSarpyBocMixin" for base in bases):
            required_static_vars = ["agency", "name"]
            missing_vars = [var for var in required_static_vars if var not in dct]

            if missing_vars:
                missing_vars_str = ", ".join(missing_vars)
                raise NotImplementedError(
                    f"{name} must define the following static variable(s): "
                    f"{missing_vars_str}."
                )

        super().__init__(name, bases, dct)


class OmaSarpyBocMixin(CityScrapersSpider, metaclass=OmaSarpyBocMixinMeta):
    timezone = "America/Chicago"
    start_date = "2019-01-01"
    source_url = "https://sarpy.civicweb.net/Portal/MeetingSchedule.aspx"
    meetings_api_url = (
        "https://sarpy.civicweb.net/Services/MeetingsService.svc/meetings"
    )
    video_api_url = "https://sarpy.civicweb.net/api/geteventwithindexpoints"

    custom_settings = {"ROBOTSTXT_OBEY": False}
    meeting_info_url = (
        "https://sarpy.civicweb.net/Portal/MeetingInformation.aspx?Org=Cal&Id={}"
    )

    def _get_cache_busting_timestamp(self):
        """Generate a cache-busting timestamp for API requests."""
        return int(datetime.now(timezone.utc).timestamp() * 1000)

    def start_requests(self):
        """Request meetings from 2019 through one year in the future."""
        today = date.today()
        params = {
            "from": self.start_date,
            "to": (today + relativedelta(years=1)).isoformat(),
            "_": self._get_cache_busting_timestamp(),
        }
        url = f"{self.meetings_api_url}?{urlencode(params)}"
        yield scrapy.Request(url=url, callback=self.parse)

    def parse(self, response):
        prefixes = getattr(self, "name_prefixes", None) or [self.agency]
        excludes = getattr(self, "name_excludes", None) or []
        seen = set()

        for item in response.json():
            name = item.get("Name") or ""

            if not any(name.startswith(prefix) for prefix in prefixes):
                continue
            if any(name.startswith(exclude) for exclude in excludes):
                continue

            title = self._parse_title(item)
            start = self._parse_start(item)

            dedup_key = (title, item.get("MeetingDateTime", ""))
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            meeting = Meeting(
                title=title,
                description="",
                classification=self._parse_classification(title),
                start=start,
                end=None,
                all_day=False,
                time_notes=self._parse_time_notes(start),
                location=self._parse_location(item),
                links=[],
                source=self._parse_source(item),
            )

            is_no_meeting = "NO MEETING" in name
            if is_no_meeting:
                meeting["status"] = CANCELLED

            meeting_id = item.get("Id")
            if not meeting_id:
                if not is_no_meeting:
                    meeting["status"] = self._get_status(meeting)
                meeting["id"] = self._get_id(meeting)
                yield meeting
                continue

            docs_url = (
                f"{self.meetings_api_url}/{meeting_id}/meetingDocuments"
                f"?_={self._get_cache_busting_timestamp()}"
            )
            yield scrapy.Request(
                url=docs_url,
                callback=self.parse_meeting_documents,
                errback=self.errback_meeting_documents,
                cb_kwargs={
                    "meeting": meeting,
                    "meeting_id": meeting_id,
                    "force_cancelled": is_no_meeting,
                },
            )

    def parse_meeting_documents(
        self, response, meeting, meeting_id, force_cancelled=False
    ):
        documents = response.json()
        meeting["links"].extend(self._parse_document_links(documents))

        if force_cancelled or self._is_cancelled(documents):
            meeting["status"] = CANCELLED
        else:
            meeting["status"] = self._get_status(meeting)

        video_url = (
            f"{self.video_api_url}/{meeting_id}"
            f"?_={self._get_cache_busting_timestamp()}"
        )
        yield scrapy.Request(
            url=video_url,
            callback=self.parse_video_link,
            errback=self.errback_video_link,
            cb_kwargs={"meeting": meeting},
        )

    def parse_video_link(self, response, meeting):
        video_href = self._parse_video_link(response)
        if video_href:
            meeting["links"].append({"href": video_href, "title": "Video"})
        meeting["links"] = self._dedupe_links(meeting["links"])
        meeting["id"] = self._get_id(meeting)
        yield meeting

    def errback_meeting_documents(self, failure):
        meeting = failure.request.cb_kwargs["meeting"]
        if not failure.request.cb_kwargs.get("force_cancelled"):
            meeting["status"] = self._get_status(meeting)
        meeting["id"] = self._get_id(meeting)
        yield meeting

    def errback_video_link(self, failure):
        meeting = failure.request.cb_kwargs["meeting"]
        meeting["id"] = self._get_id(meeting)
        yield meeting

    def _parse_video_link(self, response):
        text = response.text.strip()
        if not text or text == '""':
            return None
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None

        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                return None

        if not isinstance(data, list) or not data:
            return None

        record = data[0]
        if not isinstance(record, dict) or not record.get("ShowVideoLink"):
            return None

        event = record.get("Event")
        event_id = event.get("eventId") if isinstance(event, dict) else None
        if record.get("YouTube") and event_id:
            return f"https://www.youtube.com/watch?v={event_id}"

        return None

    def _is_cancelled(self, documents):
        for doc in documents:
            searchable_text = " ".join(
                [
                    str(doc.get("Html") or ""),
                    str(doc.get("AgendaCover") or ""),
                    str(doc.get("Name") or ""),
                ]
            ).lower()
            if "cancelled" in searchable_text or "canceled" in searchable_text:
                return True
        return False

    def _parse_document_links(self, documents):
        groups = {"Agenda": [], "Minutes": []}
        for doc in documents:
            href = self._build_document_url(doc)
            if not href:
                continue
            label = "Agenda" if doc.get("DocumentType") in (1, 4) else "Minutes"
            is_pdf = not bool(doc.get("Html"))
            groups[label].append({"href": href, "title": label, "is_pdf": is_pdf})

        links = []
        for label in ("Agenda", "Minutes"):
            candidates = groups[label]
            if not candidates:
                continue
            pdfs = [c for c in candidates if c["is_pdf"]]
            chosen = pdfs[0] if pdfs else candidates[0]
            links.append({"href": chosen["href"], "title": chosen["title"]})
        return links

    def _build_document_url(self, doc):
        doc_id = doc.get("Id")
        name = (doc.get("Name") or "").strip()
        if not doc_id:
            return None
        if name:
            encoded_name = quote(unescape(name), safe="")
            if doc.get("Html"):
                return (
                    f"https://sarpy.civicweb.net/document/{doc_id}/{encoded_name}.html"
                )
            return f"https://sarpy.civicweb.net/document/{doc_id}/{encoded_name}.pdf"
        return f"https://sarpy.civicweb.net/document/{doc_id}/"

    def _dedupe_links(self, links):
        seen = set()
        unique_links = []
        for link in links:
            key = (link.get("href", ""), link.get("title", ""))
            if key not in seen:
                seen.add(key)
                unique_links.append(link)
        return unique_links

    def _parse_title(self, item):
        title = (item.get("Name") or "").strip()
        title = re.sub(
            r"\s*-\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
            r"\s+\d{1,2}\s+\d{4}.*$",
            "",
            title,
            flags=re.IGNORECASE,
        )
        return title.strip()

    def _parse_classification(self, title):
        if "Planning Commission" in title:
            return COMMISSION
        if "Committee" in title:
            return COMMITTEE
        if "Board" in title:
            return BOARD
        return NOT_CLASSIFIED

    def _parse_start(self, item):
        dt_str = item.get("MeetingDateTime", "")
        if dt_str:
            return datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        return None

    def _parse_time_notes(self, start_time):
        if start_time and start_time.hour == 0 and start_time.minute == 0:
            return (
                "Please check meeting source website or attachment "
                "for more accurate meeting start time"
            )
        return ""

    def _parse_source(self, item):
        meeting_id = item.get("Id")
        if meeting_id:
            return self.meeting_info_url.format(meeting_id)
        return self.source_url

    def _parse_location(self, item):
        location = (item.get("MeetingLocation") or "").strip()
        if location.startswith("County Boardroom"):
            return {
                "name": "County Boardroom",
                "address": "1210 Golden Gate Drive, Papillion, NE 68046",
            }
        return {"name": location, "address": ""}
