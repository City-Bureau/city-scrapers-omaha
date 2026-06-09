import html
import re
from datetime import datetime

import dateutil.parser
import scrapy
from city_scrapers_core.constants import CITY_COUNCIL, NOT_CLASSIFIED
from city_scrapers_core.items import Meeting
from city_scrapers_core.spiders import CityScrapersSpider


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
            "image/avif,image/webp,image/apng,*/*;q=0.8,"
            "application/signed-exchange;v=b3;q=0.7"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "max-age=0",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux aarch64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/148.0.0.0 Safari/537.36 CrKey/1.54.250320"
        ),
    }

    clerk_headers = {
        **browser_headers,
        "Referer": "https://cityclerk.cityofomaha.org/",
    }

    council_headers = {
        **browser_headers,
        "Referer": "https://citycouncil.cityofomaha.org/",
    }

    custom_settings = {
        "DOWNLOAD_HANDLERS": {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        "PLAYWRIGHT_BROWSER_TYPE": "chromium",
        "PLAYWRIGHT_LAUNCH_OPTIONS": {
            "headless": False,
            "args": ["--disable-blink-features=AutomationControlled"],
        },
        "PLAYWRIGHT_PROCESS_REQUEST_HEADERS": None,
        "PLAYWRIGHT_CONTEXTS": {
            "clerk": {
                "user_agent": (
                    "Mozilla/5.0 (X11; Linux aarch64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/148.0.0.0 Safari/537.36 CrKey/1.54.250320"
                ),
            },
            "council": {
                "user_agent": (
                    "Mozilla/5.0 (X11; Linux aarch64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/148.0.0.0 Safari/537.36 CrKey/1.54.250320"
                ),
            },
        },
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2,
        "COOKIES_ENABLED": True,
        "ROBOTSTXT_OBEY": False,
        "USER_AGENT": (
            "Mozilla/5.0 (X11; Linux aarch64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/148.0.0.0 Safari/537.36 CrKey/1.54.250320"
        ),
    }

    def __init__(self, *args, **kwargs):
        self.links_by_date = {}
        self._pending_attachment_requests = 0
        self._calendar_started = False
        self._seen_meetings_by_date = {}
        super().__init__(*args, **kwargs)

    async def start(self):
        yield scrapy.Request(
            self.clerk_home_url,
            callback=self._prime_clerk_session,
            errback=self._prime_clerk_errback,
            headers=self.clerk_headers,
            meta={"playwright": True, "playwright_context": "clerk"},
            dont_filter=True,
        )

    def _prime_clerk_session(self, response):
        self.logger.info(
            "Primed cityclerk session: status=%s len=%s",
            response.status,
            len(response.text),
        )

        if response.status == 403:
            self.logger.warning(
                "Cityclerk homepage was blocked before cookies could be collected"
            )

        attachment_pages = self._get_attachment_pages()
        self._pending_attachment_requests = len(attachment_pages)

        for url, link_title in attachment_pages:
            yield scrapy.Request(
                url,
                callback=self.parse_links,
                errback=self._aux_errback,
                cb_kwargs={"link_title": link_title},
                headers=self.clerk_headers,
                meta={"playwright": True, "playwright_context": "clerk"},
                dont_filter=True,
            )

    def _prime_clerk_errback(self, failure):
        self.logger.warning(
            "Could not prime cityclerk session: %s", failure.request.url
        )

        attachment_pages = self._get_attachment_pages()
        self._pending_attachment_requests = len(attachment_pages)

        for url, link_title in attachment_pages:
            yield scrapy.Request(
                url,
                callback=self.parse_links,
                errback=self._aux_errback,
                cb_kwargs={"link_title": link_title},
                headers=self.clerk_headers,
                meta={"playwright": True, "playwright_context": "clerk"},
                dont_filter=True,
            )

    def _aux_errback(self, failure):
        self.logger.warning("Could not fetch auxiliary page: %s", failure.request.url)
        self._pending_attachment_requests -= 1
        yield from self._start_calendar()

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
                errback=self._aux_errback,
                cb_kwargs={"link_title": link_title},
                headers=self.clerk_headers,
                meta={"playwright": True, "playwright_context": "clerk"},
                dont_filter=True,
            )
            return

        self._pending_attachment_requests -= 1
        yield from self._start_calendar()

    def _start_calendar(self):
        if self._pending_attachment_requests > 0 or self._calendar_started:
            return

        self._calendar_started = True

        yield scrapy.Request(
            self.council_home_url,
            callback=self._prime_council_session,
            errback=self._prime_council_errback,
            headers=self.council_headers,
            meta={"playwright": True, "playwright_context": "council"},
            dont_filter=True,
        )

    def _prime_council_session(self, response):
        self.logger.info(
            "Primed citycouncil session: status=%s len=%s",
            response.status,
            len(response.text),
        )

        if response.status == 403:
            self.logger.warning(
                "Citycouncil homepage was blocked before cookies could be collected"
            )

        for url in self._iter_calendar_urls():
            yield scrapy.Request(
                url,
                callback=self.parse,
                headers=self.council_headers,
                meta={"playwright": True, "playwright_context": "council"},
                dont_filter=True,
            )

    def _prime_council_errback(self, failure):
        self.logger.warning(
            "Could not prime citycouncil session: %s", failure.request.url
        )

        for url in self._iter_calendar_urls():
            yield scrapy.Request(
                url,
                callback=self.parse,
                headers=self.council_headers,
                meta={"playwright": True, "playwright_context": "council"},
                dont_filter=True,
            )

    def _iter_years(self):
        now = datetime.now()
        for year in range(
            now.year - self.past_year_range, now.year + self.future_year_range + 1
        ):
            yield year

    def _iter_calendar_urls(self):
        now = datetime.now()
        for year in range(
            now.year - self.past_year_range, now.year + self.future_year_range + 1
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
                headers=self.council_headers,
                meta={"playwright": True, "playwright_context": "council"},
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
        date_match = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", href)
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
