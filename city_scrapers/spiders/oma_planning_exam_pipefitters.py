import re
from urllib.parse import urljoin

from city_scrapers_core.constants import NOT_CLASSIFIED
from city_scrapers_core.items import Meeting
from city_scrapers_core.spiders import CityScrapersSpider
from dateutil import parser


class OmahaPlanningExaminersEngineersSpider(CityScrapersSpider):
    name = "oma_planning_exam_pipefitters"
    agency = "Omaha Planning Department: Steamfitters/Pipefitters Board"
    start_urls = [
        "https://planning.cityofomaha.org/boards/board-of-examiners-for-engineers"  # noqa
    ]
    timezone = "America/Chicago"
    base_url = "https://planning.cityofomaha.org"
    start_time = "1 p.m."
    location = {
        "name": "",
        "address": "11th Floor - Central Conference Room, Omaha-Douglas Civic Center, 1819 Farnam Street",  # noqa
    }

    def parse(self, response):
        table = response.css("table.tabclr")

        # skip the first two rows, which are headers
        col_headers = table.css("tr")[1]
        for row in table.css("tr")[2:]:
            start = self._parse_start(row)
            if not start:
                # If we can't parse the start time, skip this row
                continue
            meeting = Meeting(
                title="Steamfitters/Pipefitters Board meeting",
                description="",
                classification=NOT_CLASSIFIED,
                start=start,
                end=None,
                all_day=False,
                time_notes="",
                location=self.location,
                links=self._parse_links(row, col_headers),
                source=response.url,
            )
            meeting["status"] = self._get_status(meeting)
            meeting["id"] = self._get_id(meeting)
            yield meeting

    def _parse_start(self, row):
        """
        Parse the start time from the second column of the row.
        Date is in format "Month Day, Year" and time is always 12 p.m.
        Date might be in a link, so we need to check for that.
        """
        second_col = row.css("td:nth-child(2)")
        date_str = second_col.css("::text").extract_first()

        if not date_str:
            date_str = second_col.css("a::text").extract_first()
            if not date_str:
                return
        # use regex to capture only the date string in format "Month Day, Year"
        clean_date = re.search(r"([A-Z][a-z]+ \d{1,2}, \d{4})", date_str)
        if not clean_date:
            return
        clean_date_str = clean_date.group(0)
        full_start_str = f"{clean_date_str} {self.start_time}"
        return parser.parse(full_start_str)

    def _parse_links(self, row, col_headers):
        """
        Third and four columns contain links to meeting minutes and agendas.
        """
        links = []
        for col_num in [3]:
            col = row.css(f"td:nth-child({col_num})")
            if col.css("a"):
                header_selector = f"td:nth-child({col_num}) strong::text"
                title_els = col_headers.css(header_selector)
                # loop over all title_els and join
                title = " ".join(title_els.extract())
                clean_title = re.sub(r"\s+", " ", title)
                relative_url = col.css("a::attr(href)").extract_first()
                abs_url = urljoin(self.base_url, relative_url)
                links.append(
                    {
                        "title": clean_title,
                        "href": abs_url,
                    }
                )
        return links
