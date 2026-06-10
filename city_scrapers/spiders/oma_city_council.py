import html
import re
from datetime import datetime

import dateutil.parser
import scrapy
from city_scrapers_core.constants import CITY_COUNCIL, NOT_CLASSIFIED
from city_scrapers_core.items import Meeting
from city_scrapers_core.spiders import CityScrapersSpider
from curl_cffi import requests as cffi_requests
from scrapy.http import HtmlResponse

REAL_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
)

# Akamai can block Scrapy/requests/Playwright based on TLS + HTTP/2 fingerprint.
# curl-cffi with Chrome impersonation gives us a browser-like network fingerprint.
IMPERSONATE = "chrome131"
AKAMAI_TIMEOUT = 30


class OmaCityCouncilSpider(CityScrapersSpider):
    name = "oma_city_council"
    agency = "Omaha City Council"
    timezone = "America/Chicago"

    clerk_home_url = "https://cityclerk.cityofomaha.org/"
    council_home_url = "https://citycouncil.cityofomaha.org/"

    calendar_url_template = (
        "https://citycouncil.cityofomaha.org/"
        "council-calender/month.calendar/{year}/{month:02d}/01/73"
    )
    agenda_url_template = (
        "https://cityclerk.cityofomaha.org/"
        "category/city-council-downloads/agendas/{year}-agendas/"
    )
    video_url = (
        "https://cityclerk.cityofomaha.org/category/city-council-downloads/videos/"
    )
    journal_url_template = (
        "https://cityclerk.cityofomaha.org/"
        "category/city-council-downloads/journals/{year}-journals/"
    )

    past_year_range = 3
    future_year_range = 1

    browser_headers = {
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "max-age=0",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": REAL_UA,
    }

    clerk_headers = {
        **browser_headers,
        "Referer": clerk_home_url,
    }

    council_headers = {
        **browser_headers,
        "Referer": council_home_url,
    }

    custom_settings = {
        "USER_AGENT": REAL_UA,
        "COOKIES_ENABLED": True,
        "ROBOTSTXT_OBEY": False,
        "FEED_EXPORT_ENCODING": "utf-8",
        "DOWNLOAD_DELAY": 1,
        "AUTOTHROTTLE_ENABLED": True,
        "CONCURRENT_REQUESTS": 1,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
    }

    def __init__(self, *args, **kwargs):
        self.links_by_date = {}
        self._seen_meetings_by_date = {}

        # Keep separate sessions so cookies do not get mixed between domains.
        self._akamai_sessions = {}

        super().__init__(*args, **kwargs)

    async def start(self):
        """Kick off the spider with a normal Scrapy request.

        The real protected pages are fetched inside _run_crawl() using curl-cffi.
        This avoids relying on Scrapy/Playwright for Akamai-sensitive pages.
        """
        yield scrapy.Request(
            self.clerk_home_url,
            callback=self._run_crawl,
            errback=self._run_crawl_errback,
            headers=self.clerk_headers,
            meta={"handle_httpstatus_all": True},
            dont_filter=True,
        )

    def _run_crawl(self, response):
        self.logger.info(
            "Starting curl-cffi crawl after initial response: status=%s url=%s",
            response.status,
            response.url,
        )

        self._collect_attachment_links()
        yield from self._fetch_calendar_pages()

    def _run_crawl_errback(self, failure):
        self.logger.warning(
            "Initial Scrapy request failed, continuing with curl-cffi: %s",
            failure.request.url,
        )

        self._collect_attachment_links()
        yield from self._fetch_calendar_pages()

    def _akamai_get(self, url, headers=None, session_name="default"):
        """GET an Akamai-protected URL with curl-cffi Chrome impersonation.

        Returns a Scrapy HtmlResponse so existing .css()/.xpath() parsing can
        stay the same.
        """
        session = self._akamai_sessions.setdefault(
            session_name,
            cffi_requests.Session(),
        )

        request_headers = {
            **(headers or {}),
            "User-Agent": REAL_UA,
        }

        try:
            response = session.get(
                url,
                impersonate=IMPERSONATE,
                timeout=AKAMAI_TIMEOUT,
                headers=request_headers,
            )
        except Exception as e:
            self.logger.warning("Akamai fetch error for %s: %s", url, e)
            return None

        if response.status_code != 200:
            self.logger.warning(
                "Akamai fetch returned %s for %s",
                response.status_code,
                url,
            )
            return None

        body = response.content
        text_preview = body[:1000].decode("utf-8", errors="ignore").lower()
        if "access denied" in text_preview or "akamai" in text_preview:
            self.logger.warning("Possible Akamai block page for %s", url)

        return HtmlResponse(
            url=str(response.url),
            status=response.status_code,
            body=body,
            encoding="utf-8",
        )

    def _collect_attachment_links(self):
        """Fetch agenda, journal, and video pages through curl-cffi.

        This replaces the old Playwright-driven auxiliary page flow.
        """
        for url, link_title in self._get_attachment_pages():
            self._fetch_attachment_page(url, link_title)

    def _fetch_attachment_page(self, url, link_title):
        current_url = url

        while current_url:
            response = self._akamai_get(
                current_url,
                headers=self.clerk_headers,
                session_name="clerk",
            )
            if response is None:
                self.logger.warning(
                    "Could not fetch %s attachment page: %s",
                    link_title,
                    current_url,
                )
                return

            next_url = None
            for result in self.parse_links(response, link_title):
                if isinstance(result, scrapy.Request):
                    next_url = result.url

            current_url = next_url

    def _fetch_calendar_pages(self):
        """Fetch calendar listing pages and detail pages through curl-cffi."""
        council_home_response = self._akamai_get(
            self.council_home_url,
            headers=self.council_headers,
            session_name="council",
        )

        if council_home_response is None:
            self.logger.warning(
                "Could not prime citycouncil session; trying calendar pages anyway"
            )
        else:
            self.logger.info(
                "Primed citycouncil session: status=%s len=%s",
                council_home_response.status,
                len(council_home_response.text),
            )

        for url in self._iter_calendar_urls():
            yield from self._fetch_calendar_page(url)

    def _fetch_calendar_page(self, url):
        response = self._akamai_get(
            url,
            headers=self.council_headers,
            session_name="council",
        )
        if response is None:
            self.logger.warning("Could not fetch calendar page: %s", url)
            return

        for result in self.parse(response):
            if not isinstance(result, scrapy.Request):
                yield result
                continue

            detail_response = self._akamai_get(
                result.url,
                headers=self.council_headers,
                session_name="council",
            )
            if detail_response is None:
                self.logger.warning("Could not fetch detail page: %s", result.url)
                continue

            yield from self.parse_detail(
                detail_response,
                **result.cb_kwargs,
            )

    def _iter_years(self):
        now = datetime.now()
        for year in range(
            now.year - self.past_year_range,
            now.year + self.future_year_range + 1,
        ):
            yield year

    def _iter_calendar_urls(self):
        now = datetime.now()
        for year in range(
            now.year - self.past_year_range,
            now.year + self.future_year_range + 1,
        ):
            for month in range(1, 13):
                yield self.calendar_url_template.format(year=year, month=month)

    def _get_attachment_pages(self):
        pages = []
        for year in self._iter_years():
            pages.append((self.agenda_url_template.format(year=year), "Agenda"))
            pages.append((self.journal_url_template.format(year=year), "Journal"))
        pages.append((self.video_url, "Video"))
        return pages

    def parse_links(self, response, link_title):
        self.logger.info(
            "parse_links %s: status=%s len=%s",
            link_title,
            response.status,
            len(response.text),
        )

        if "Access Denied" in response.text or "akamai" in response.text.lower():
            self.logger.warning("Possible block on %s (%s)", link_title, response.url)

        posts = response.css("article.hentry, div.hentry")
        self.logger.info("parse_links %s: found %s posts", link_title, len(posts))

        for post in posts:
            date_text = post.css(".entry-title a::text").get("").strip()

            if "Board of Equalization" in date_text:
                continue

            date = self._parse_link_date(date_text)
            if not date:
                continue

            href = self._parse_doc_href(post, link_title)
            if href:
                link_obj = {"href": response.urljoin(href), "title": link_title}
                date_links = self.links_by_date.setdefault(date, [])
                if link_obj not in date_links:
                    date_links.append(link_obj)

        next_page = self._parse_next_page(response)
        if next_page:
            self.logger.info("Following %s pagination: %s", link_title, next_page)
            yield scrapy.Request(
                next_page,
                callback=self.parse_links,
                cb_kwargs={"link_title": link_title},
                headers=self.clerk_headers,
                dont_filter=True,
            )

    def _parse_next_page(self, response):
        next_page = response.xpath(
            "//div[contains(@class, 'navigation')]"
            "//a[contains(normalize-space(.), 'Next Page')]/@href"
        ).get()
        return response.urljoin(next_page) if next_page else None

    def _sort_links(self, links):
        order = {"Agenda": 0, "Journal": 1, "Video": 2}
        return sorted(links, key=lambda link: order.get(link.get("title", ""), 99))

    def _parse_doc_href(self, post, link_title):
        if link_title == "Video":
            src = post.css("iframe[src*='youtube.com/embed']::attr(src)").get("")
            match = re.search(r"youtube\.com/embed/([^?&/]+)", src)
            if match:
                return f"https://www.youtube.com/watch?v={match.group(1)}"
            return post.css("a[href*='youtube.com/watch']::attr(href)").get("")

        return post.css("a.docaccess-activated[href$='.pdf']::attr(href)").get(
            ""
        ) or post.css("a[href$='.pdf']::attr(href)").get("")

    def parse(self, response):
        events = response.css("span.editlinktip.hasjevtip")
        self.logger.info("Calendar page %s: found %s events", response.url, len(events))

        for event in events:
            link = event.css("a.cal_titlelink::attr(href)").get()
            if not link:
                continue

            title_html = event.attrib.get("data-bs-original-title", "")
            content_html = event.attrib.get("data-bs-content", "")
            link_text = event.css("a.cal_titlelink::text").get("").strip()

            title = self._parse_title(title_html, link_text)

            if not self._is_target_meeting(title):
                self.logger.debug("Skipping non-target event: %s", title)
                continue

            start = self._parse_dt(content_html, link, start=True)
            end = self._parse_dt(content_html, link, start=False)

            if not start:
                self.logger.warning(
                    "Skipping event with no start date on %s: title=%r link=%r content=%r",  # noqa
                    response.url,
                    title,
                    link,
                    content_html[:300],
                )
                continue

            date_key = start.date()
            self._seen_meetings_by_date.setdefault(date_key, set()).add(title)

            links = self._sort_links(self.links_by_date.get(date_key, []))
            detail_url = response.urljoin(link)

            yield scrapy.Request(
                detail_url,
                callback=self.parse_detail,
                cb_kwargs={
                    "title": title,
                    "start": start,
                    "end": end,
                    "links": links,
                    "source": detail_url,
                },
                dont_filter=True,
            )

    def parse_detail(self, response, title, start, end, links, source):
        raw = "".join(response.css("div.jev_evdt_desc ::text").getall())
        desc_text = re.sub(r"\s+", " ", raw.replace("\xa0", " ")).strip()
        match = re.search(
            r"(?:takes place|is held) in\s+(.+?)(?:\.|$)", desc_text, re.I
        )
        location_name = self._clean_location_name(match.group(1)) if match else ""

        meeting = Meeting(
            title=title,
            description="",
            classification=self._parse_classification(title),
            start=start,
            end=end,
            all_day=False,
            time_notes=(
                ""
                if location_name
                else "See attachments for more accurate location details"
            ),
            location={
                "name": location_name,
                "address": "1819 Farnam St, Omaha, NE 68183" if location_name else "",
            },
            links=links,
            source=source,
        )
        meeting["status"] = self._get_status(meeting)
        meeting["id"] = self._get_id(meeting)
        yield meeting

    def _clean_location_name(self, name):
        name = re.sub(r"\s+", " ", name).strip()
        return re.sub(r"^the\s+", "", name, flags=re.I)

    def closed(self, _reason):
        expected = {"Pre-Council Meeting", "City Council Meeting"}
        for meeting_date, titles in self._seen_meetings_by_date.items():
            if titles != expected:
                self.logger.warning(
                    "Unexpected meeting pair on %s: %s",
                    meeting_date,
                    sorted(titles),
                )

    def _parse_title(self, title_html, link_text=""):
        if title_html:
            title_html = html.unescape(title_html)
            match = re.search(r"jevtt_title[^>]*>\s*([^<]+)", title_html)
            if match:
                return match.group(1).strip()

        return (
            re.sub(r"^\d{1,2}:\d{2}\s*(?:am|pm)\s+", "", link_text, flags=re.I)
            .strip()
            .rstrip(" .")
        )

    def _is_target_meeting(self, title):
        return title in {"Pre-Council Meeting", "City Council Meeting"}

    def _parse_classification(self, title):
        if title in {"City Council Meeting", "Pre-Council Meeting"}:
            return CITY_COUNCIL

        return NOT_CLASSIFIED

    def _parse_dt(self, content_html, href, start=True):
        date_match = re.search(r"/(\d{4})/(\d{1,2})/(\d{1,2})/", href)
        if not date_match:
            return None

        year, month, day = map(int, date_match.groups())

        content_html = html.unescape(content_html)

        range_match = re.search(
            r"(\d{1,2}:\d{2}\s*(?:am|pm))\s*-\s*(\d{1,2}:\d{2}\s*(?:am|pm))",
            content_html,
            re.I,
        )

        if range_match:
            time_str = range_match.group(1) if start else range_match.group(2)
        elif start:
            single_match = re.search(r"(\d{1,2}:\d{2}\s*(?:am|pm))", content_html, re.I)
            if not single_match:
                return None
            time_str = single_match.group(1)
        else:
            return None

        try:
            return datetime.strptime(
                f"{year}-{month:02d}-{day:02d} {time_str.upper().replace(' ', '')}",
                "%Y-%m-%d %I:%M%p",
            )
        except ValueError:
            return None

    def _parse_link_date(self, text):
        try:
            return dateutil.parser.parse(text, fuzzy=True).date()
        except (ValueError, OverflowError):
            return None
