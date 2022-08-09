import re
import dateutil.parser
from city_scrapers_core.constants import NOT_CLASSIFIED
from city_scrapers_core.items import Meeting
from city_scrapers_core.spiders import CityScrapersSpider


class OmahaMudSpider(CityScrapersSpider):
    name = "omaha_mud"
    agency = "Omaha Metropolitan Utilities District"
    timezone = "America/Chicago"
    start_urls = [
        "https://www.mudomaha.com/our-company/board-of-directors/board-meetings"
    ]

    def parse(self, response):
        """
        `parse` should always `yield` Meeting items.

        Change the `_parse_title`, `_parse_start`, etc methods to fit your scraping
        needs.
        """
        for item in response.xpath("//table[1]/tbody/tr"):
            date_td = item.css(".views-field-field-date::text").get()
            if not date_td:
                continue
            date_td = date_td.strip()
            details_td = item.css(".views-field-field-details::text").get().strip()
            time = re.findall(r" \d{1,2}:\d{2} [a|p]\.m\.", details_td)[0]
            # date is first part of date_td + time extracted from details
            start = dateutil.parser.parse(date_td.split(" - ")[0] + time)
            meeting = Meeting(
                title=date_td,
                description=details_td,
                classification=self._parse_classification(item),
                start=start,
                end=self._parse_end(item),
                all_day=self._parse_all_day(item),
                time_notes=self._parse_time_notes(item),
                location=self._parse_location(item),
                links=self._parse_links(item),
                source=self._parse_source(response),
            )

            meeting["status"] = self._get_status(meeting)
            meeting["id"] = self._get_id(meeting)

            yield meeting

    def _parse_classification(self, item):
        """Parse or generate classification from allowed options."""
        return NOT_CLASSIFIED

    def _parse_start(self, item):
        """Parse start datetime as a naive datetime object."""
        return None

    def _parse_end(self, item):
        """Parse end datetime as a naive datetime object. Added by pipeline if None"""
        return None

    def _parse_time_notes(self, item):
        """Parse any additional notes on the timing of the meeting"""
        return ""

    def _parse_all_day(self, item):
        """Parse or generate all-day status. Defaults to False."""
        return False

    def _parse_location(self, item):
        """Parse or generate location."""
        return {
            "address": "",
            "name": "",
        }

    def _parse_links(self, item):
        """Parse or generate links."""
        BASE_URL = "https://www.mudomaha.com/"
        links = item.xpath(".//a/@href").getall() or []
        return [
            {
                "href": BASE_URL + link,
                "title": "Video" if "youtube" in link else "Documents",
            }
            for link in links
        ]

    def _parse_source(self, response):
        """Parse or generate source."""
        return response.url
