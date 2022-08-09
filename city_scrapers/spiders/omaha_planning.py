import re

import dateutil.parser
from city_scrapers_core.constants import NOT_CLASSIFIED
from city_scrapers_core.items import Meeting
from city_scrapers_core.spiders import CityScrapersSpider


class OmahaPlanningSpider(CityScrapersSpider):
    """Base spider for scraping tables on Omaha planning commissions"""

    timezone = "America/Chicago"
    BASE_URL = "https://planning.cityofomaha.org/"

    def parse(self, response):
        table = response.css("table.tabclr")

        header_spans = table.xpath(".//td[@colspan=4]//span/text()").getall()
        time = re.findall(r"\d{1,2}:\d{2} [AP]\.M\.", header_spans[-2])[0]
        address = header_spans[-1]

        for row in table.xpath(".//tr[@valign='top']"):
            try:
                _, agenda, disposition_agenda, minutes = row.xpath("./td")
            except ValueError:
                continue

            # the text here may be nested in a few ways
            date = agenda.xpath(".//text()").get().strip()
            if not date:
                date = agenda.xpath(".//a/text()").get()
            if date is None:
                date = agenda.xpath(".//p/text()").get()
            if date is None:
                date = agenda.xpath(".//span/text()").get().strip("*")
            date = date.replace("20222", "2022")

            agenda_link = agenda.xpath(".//a/@href").get()
            disposition_link = disposition_agenda.xpath(".//a/@href").get()
            minutes_link = minutes.xpath(".//a/@href").get()

            start = dateutil.parser.parse(f"{date} {time}")

            links = []
            if agenda_link:
                links.append({"href": self.BASE_URL + agenda_link, "title": "Agenda"})
            if disposition_link:
                links.append(
                    {
                        "href": self.BASE_URL + disposition_link,
                        "title": "Disposition Agenda",
                    }
                )
            if minutes_link:
                links.append({"href": self.BASE_URL + minutes_link, "title": "Minutes"})

            meeting = Meeting(
                title=date,
                description="",
                classification=NOT_CLASSIFIED,
                start=start,
                end=None,
                all_day=False,
                time_notes="",
                location={"address": address},
                links=links,
                source=response.url,
            )

            meeting["status"] = self._get_status(meeting)
            meeting["id"] = self._get_id(meeting)

            yield meeting


class OmahaPlanningAppeals(OmahaPlanningSpider):
    name = "omaha_planning_appeals"
    agency = "Omaha Planning Department: Board of Appeals"
    start_urls = [
        "https://planning.cityofomaha.org/boards/administrative-board-of-appeals"
    ]


class OmahaAirSpider(OmahaPlanningSpider):
    name = "omaha_planning_air"
    agency = "Omaha Planning Department: Air Conditioning / Air Distribution Board"
    start_urls = [
        "https://planning.cityofomaha.org/boards/"
        "air-conditioning-air-distribution-board",
    ]
