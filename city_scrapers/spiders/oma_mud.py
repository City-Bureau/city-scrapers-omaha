import re

import dateutil.parser
from city_scrapers_core.constants import NOT_CLASSIFIED
from city_scrapers_core.items import Meeting
from city_scrapers_core.spiders import CityScrapersSpider


class OmahaMudSpider(CityScrapersSpider):
    name = "oma_mud"
    agency = "Omaha Metropolitan Utilities District"
    timezone = "America/Chicago"
    start_urls = ["https://www.mudomaha.com/about-us/board-meetings/"]
    location = {
        "address": "7350 World Communications Drive",  # No specific address given
        "name": "Metropolitan Utilities District",
    }
    title = "Committee and Board meetings"

    def parse(self, response):
        for item in response.xpath("//ul[@class='meetings-list']/li"):
            date_text = item.xpath(".//p[@class='date']/text()").get()
            if not date_text:
                continue
            date_text = date_text.strip()
            details = item.xpath(".//article//p/text()").getall()
            time = re.findall(r"\d{1,2}:\d{2} [a|p]\.m\.", " ".join(details))
            if not time:
                continue
            # Assuming the first time is always the start of the meeting
            start = dateutil.parser.parse(date_text + " " + time[0])
            meeting = Meeting(
                title=self.title,
                description=" ".join(details).replace("\n", "").strip(),
                classification=self._parse_classification(item),
                start=start,
                end=False,
                all_day=self._parse_all_day(item),
                time_notes="",
                location=self.location,
                links=self._parse_links(item),
                source=self._parse_source(response),
            )

            meeting["status"] = self._get_status(meeting)
            meeting["id"] = self._get_id(meeting)

            yield meeting

    def _parse_classification(self, item):
        return NOT_CLASSIFIED

    def _parse_all_day(self, item):
        return False

    def _parse_links(self, item):
        links = item.xpath(
            ".//div[contains(@class, 'meetings-media')]//a/@href"
        ).getall()
        return [
            {"href": link, "title": "Video" if "youtube" in link else "Documents"}
            for link in links
        ]

    def _parse_source(self, response):
        return response.url
