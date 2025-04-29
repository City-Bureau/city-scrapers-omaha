#import re
from city_scrapers_core.constants import BOARD
from city_scrapers_core.items import Meeting
from city_scrapers_core.spiders import CityScrapersSpider
from datetime import datetime
from dateutil.parser import parser


class OmaParksRecreationSpider(CityScrapersSpider):
    name = "oma_parks_recreation"
    agency = "Omaha Parks & Recreation Board"
    timezone = "America/Chicago"
    start_urls = [
        "https://mayors-office.cityofomaha.org/2-uncategorised/205-parks-recreation-board"
    ]
    # other hard-coded attributes
    location = "Dewey Dog Park Building, 550 Turner Blvd., Omaha, NE 68105"
    time = "14:00:00"
    
    def parse(self, response):
        """
        `parse` should always `yield` Meeting items.

        Change the `_parse_title`, `_parse_start`, etc methods to fit your scraping
        needs.
        """
        meeting_items = response.css(".gmail_default")
        header = meeting_items[0].css("::text").get()
        if "Meeting Dates" not in header:
            raise(ValueError(
                "Site Formatting Change Detected [{}]: Extracted wrong page element".format(
                    self.name)))
        self.year=header[:4]
        for item in meeting_items[1:]:
            meeting = Meeting(
                title=self._parse_title(item),
                description=self._parse_description(item),
                classification=self._parse_classification(item),
                start=self._parse_start(item),
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

    def _parse_title(self, item):
        """Parse or generate meeting title."""
        title = "Quarterly Meeting"
        return title

    def _parse_description(self, item):
        """Parse or generate meeting description."""
        return ""

    def _parse_classification(self, item):
        """Parse or generate classification from allowed options."""
        return BOARD

    def _parse_start(self, item):
        """Parse start datetime as a naive datetime object."""
        dateRaw = (item.css("::text").get()).strip().split()
        month = datetime.strptime(dateRaw[1], '%B').month
        day = dateRaw[2][:-2]
        dt_obj = "{}-{}-{} {}".format(
            self.year, month, day, self.time)
        return parser().parse(dt_obj)

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
        # Possible alternative location:
        #   Parks, Recreation and Public Property Department, 1819 Farnam St., Suite 701
        #   Omaha, NE 68183
        return {
            "address": self.location,
            "name": "Parks and Recreation Board"
        }

    def _parse_links(self, item):
        """Parse or generate links."""
        return [
            {
            }
        ]
        agenda = ""
        packet = ""

    def _parse_source(self, response):
        """Parse or generate source."""
        return response.url
