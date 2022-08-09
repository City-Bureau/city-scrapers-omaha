import re

import dateutil.parser
from city_scrapers_core.constants import NOT_CLASSIFIED
from city_scrapers_core.items import Meeting
from city_scrapers_core.spiders import CityScrapersSpider


class OmahaPlanningMixin:
    """Base spider for scraping tables on Omaha planning commissions"""

    timezone = "America/Chicago"
    BASE_URL = "https://planning.cityofomaha.org/"

    def parse(self, response):
        table = response.css("table.tabclr")

        header = table.xpath(".//td[@colspan=4]").xpath("string()").get()
        for line in header.splitlines():
            try:
                time = re.findall(r"\d{1,2}:\d{2} [AP]\.M\.", line)[0]
            except IndexError:
                pass
        # not perfect since markup varies wildly, but gets enough to be useful
        address = header.split(" - ")[-1].strip()

        for row in table.xpath(".//tr[@valign='top']"):
            try:
                _, agenda, disposition_agenda, minutes = row.xpath("./td")
            except ValueError:
                continue

            date = agenda.xpath("string()").get().strip()
            date = date.replace("20222", "2022")

            agenda_link = agenda.xpath(".//a/@href").get()
            disposition_link = disposition_agenda.xpath(".//a/@href").get()
            minutes_link = minutes.xpath(".//a/@href").get()

            start = dateutil.parser.parse(f"{date} {time}".replace("*", ""))

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


class OmahaPlanningAppeals(OmahaPlanningMixin, CityScrapersSpider):
    name = "omaha_planning_appeals"
    agency = "Omaha Planning Department: Board of Appeals"
    start_urls = [
        "https://planning.cityofomaha.org/boards/administrative-board-of-appeals"
    ]


class OmahaPlanningAir(OmahaPlanningMixin, CityScrapersSpider):
    name = "omaha_planning_air"
    agency = "Omaha Planning Department: Air Conditioning / Air Distribution Board"
    start_urls = [
        "https://planning.cityofomaha.org/boards/"
        "air-conditioning-air-distribution-board",
    ]


class OmahaPlanningBuildingReview(OmahaPlanningMixin, CityScrapersSpider):
    name = "omaha_planning_building_review"
    agency = "Omaha Planning Department: Building Board of Review"
    start_urls = [
        "https://planning.cityofomaha.org/boards/" "building-board-of-review",
    ]


class OmahaPlanningElectrical(OmahaPlanningMixin, CityScrapersSpider):
    name = "omaha_planning_electrical"
    agency = "Omaha Planning Department: Electrical Board"
    start_urls = [
        "https://planning.cityofomaha.org/boards/" "electrical-examining-board",
    ]


class OmahaPlanningLandmarks(OmahaPlanningMixin, CityScrapersSpider):
    name = "omaha_planning_landmarks"
    agency = "Omaha Planning Department: Landmarks Commission"
    start_urls = [
        "https://planning.cityofomaha.org/boards/" "landmarks-commission",
    ]
