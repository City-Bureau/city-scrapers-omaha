import dateutil.parser
from city_scrapers_core.constants import NOT_CLASSIFIED
from city_scrapers_core.items import Meeting
from city_scrapers_core.spiders import CityScrapersSpider


class OmahaExaminingBoardMixin:
    """Base spider for scraping tables on Omaha examining boards"""

    timezone = "America/Chicago"
    BASE_URL = "https://planning.cityofomaha.org"

    def parse(self, response):
        table = response.css("table.tabclr")

        for row in table.xpath(".//tr")[2:]:
            try:
                _, _, meeting = row.xpath("./td")
            except ValueError:
                continue

            date = meeting.xpath("string()").get().strip()

            # look for cancelled meetings, irregularly specified
            if "CANCELED" in date or "CANCELLED" in date or "NO " in date:
                continue

            meeting_link = meeting.xpath(".//a/@href").get()

            try:
                start = dateutil.parser.parse(f"{date} {self.time}".replace("*", ""))
            except Exception:
                print("Could not parse date: ", date, self.time)
                continue

            links = []
            if meeting_link:
                links.append({"href": self.BASE_URL + meeting_link, "title": "Minutes"})

            meeting = Meeting(
                title=date,
                description="",
                classification=NOT_CLASSIFIED,
                start=start,
                end=None,
                all_day=False,
                time_notes="",
                location={"address": self.address, "name": ""},
                links=links,
                source=response.url,
            )

            meeting["status"] = self._get_status(meeting)
            meeting["id"] = self._get_id(meeting)

            yield meeting


class OmahaPlanningExaminersPipefitters(OmahaExaminingBoardMixin, CityScrapersSpider):
    name = "oma_planning_exam_pipefitters"
    agency = "Omaha Planning Department: Board of Examiners (For Engineers)"
    start_urls = [
        "https://planning.cityofomaha.org/boards/steamfitters-examining-board"  # noqa
    ]
    time = "1pm"
    address = "11th Floor - Central Conference Room; Omaha-Douglas Civic Center, 1819 Farnam Street"  # noqa
