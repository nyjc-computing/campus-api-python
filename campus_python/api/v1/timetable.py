"""campus_python.api.v1.timetable

Campus API timetable resource (v1).
"""

import campus.model

from ...interface import Resource, ResourceCollection

TIMESLOTS = [
    "0730",
    "0800",
    "0830",
    "0900",
    "0930",
    "1000",
    "1030",
    "1100",
    "1130",
    "1200",
    "1230",
    "1300",
    "1330",
    "1400",
    "1430",
    "1500",
    "1530",
    "1600",
    "1630",
    "1700",
    "1730",
    "1800",
    "1830",
    "1900",
]
WEEKDAYS = [
    "Mon A",
    "Tue A",
    "Wed A",
    "Thu A",
    "Fri A",
    "Mon B",
    "Tue B",
    "Wed B",
    "Thu B",
    "Fri B",
]


class Timetable(ResourceCollection):
    """Campus API Timetable resource."""
    path = "timetable"
    # hardcoded enums
    timeslots = TIMESLOTS
    weekdays = WEEKDAYS
