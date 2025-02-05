from math import exp
from datetime import datetime, time, date
from decimal import Decimal
import requests
import pandas as pd
from typing import List, Optional, Dict
from numpy import e, nan
from io import StringIO
from pathlib import Path
import random
import os
from numpy import percentile
from logging import getLogger
from functools import cached_property

from members import get_member, Member
from tools import (
    parse_date, 
    money_string, 
    positive_decimal_or_none,
)

log = getLogger()


FIRST_CLASS_TYPES = {
    "FIRST RETURN",
    "FIRST SINGLE",
    "BUSINESS / CLUB RETURN",
    "BUSINESS / CLUB SINGLE",
}


class Expense:

    def __init__(self, data):
        self._data = data
        self._member = None
        
        self.member_id = int(data["Parliamentary ID"])
        self.year_code = data["Year"]
        self.claim_number = data["Claim Number"]
        self.category = data["Category"]
        self.expense_type = data["Cost Type"].upper()
        self.amount_claimed = Decimal(str(data["Amount Claimed"]))
        self.amount_paid = Decimal(str(data["Amount Paid"]))
        self.status = data["Status"]
        self.short_desc = data.get("Short Description")
        self.details = data.get("Details")
        self.travel_from = data.get("From")
        self.travel_to = data.get("To")
        self.travel_type = data.get("Travel")

    @cached_property
    def date(self) -> date:
        return parse_date(self._data["Date"])

    @cached_property
    def mileage(self) -> Optional[Decimal]:
        return positive_decimal_or_none(self._data.get("Mileage"))

    @cached_property
    def nights(self) -> Optional[Decimal]:
        return positive_decimal_or_none(self._data.get("Nights"))

    def __repr__(self):
        mp_string = self.member.name if self._member is not None else self.member_id
        return (
            f"<Expense {self.claim_number} on {self.date} mp={mp_string}: "
            f"{money_string(self.amount_claimed)} for {self.category} - {self.expense_type} - {self.short_desc}>"
        )

    @cached_property
    def group(self) -> str:
        return "/".join([
            str(self.category).strip(),
            str(self.expense_type).strip(),
            str(self.short_desc).strip(),
        ]).upper()

    @cached_property
    def member(self) -> Optional[Member]:
        if "DUMMY" in self.claim_number:
            return None
        self._member = get_member(self.member_id)
        return self._member

    @property
    def amount_claimed_str(self) -> str:
        return money_string(self.amount_claimed)

    @cached_property
    def price_per_mile(self) -> Optional[Decimal]:
        if self.mileage is None or self.amount_claimed <= 0:
            return None
        return round(Decimal(self.amount_claimed / self.mileage), 2)

    @cached_property
    def price_per_night(self) -> Optional[Decimal]:
        if self.nights is None or self.amount_claimed <= 0:
            return None
        return round(Decimal(self.amount_claimed / self.nights), 2)

    @cached_property
    def price_per_unit(self) -> Optional[Decimal]:
        if self.price_per_mile and self.price_per_night:
            print(f"WARNING: Expense {self.claim_number} has both PPM and a PPN value. {self}")
        elif self.price_per_night:
            return self.price_per_night
        elif self.price_per_mile:
            return self.price_per_mile
        return None 

    @property
    def date_string(self) -> str:
        day = str(self.date.day)
        if day.startswith("0"):
            day = day[1:]
        datestring = f"{day} {self.date.strftime('%b %y')}"
        return datestring

    @property
    def is_rail_booking_fee(self) -> bool:
        return self.is_rail() and (
            "BOOKING FEE" in str(self.short_desc).upper() or self.amount_claimed == 1
        )

    @property
    def is_first_class(self) -> bool:
        travel_type = str(self.travel_type).upper().strip()
        if travel_type in FIRST_CLASS_TYPES:
            return True

        keywords = ["FIRST", "BUSINESS", "CLUB", "PREMIUM"]
        if any(word in travel_type for word in keywords):
            log.warning(
                f"Expense {self.claim_number} travel type '{travel_type}' doesn't appear in "
                f"{FIRST_CLASS_TYPES} but has keyword match from {keywords}."
            )
        return False

    def is_air_travel(self) -> bool:
        return str(self.expense_type).upper() == "AIR TRAVEL"

    def is_taxi_ride(self) -> bool:
        return str(self.expense_type).upper() == "TAXI"

    def is_rail(self) -> bool:
        return str(self.expense_type).upper() == "RAIL"

    def is_energy(self) -> bool:
        return str(self.short_desc).upper() in ["GAS", "ELECTRICITY", "DUAL FUEL"]

    def is_staff_travel(self) -> bool:
        return str(self.category).strip().upper() == "STAFF TRAVEL"

    def is_dependant_travel(self) -> bool:
        return str(self.category).strip().upper() == "DEPENDANT TRAVEL"

    def is_mp_travel(self) -> bool:
        return str(self.category).strip().upper() == "MP TRAVEL"

    def is_transport_expense(self) -> bool:
        return self.expense_type.upper() in [
            "MILEAGE - CAR",
            "MILEAGE - MOTORCYCLE",
            "MILEAGE - BICYCLE",
            "AIR TRAVEL",
            "RAIL",
            "TAXI",
        ]

    def is_overnight_expense(self) -> bool:
        return self.expense_type.upper() in [
            "HOTEL - UK NOT LONDON",
            "HOTEL - LONDON",
            "HOTEL - EUROPEAN",
            "HOTEL - LATE NIGHT",
        ]

    def claim_text(self, fetch_member=True) -> str:
        if not fetch_member or self.member is None:
            name_str = f"Member:{self.member_id}"
        else:
            name_str = self.member.display_name

        return (
            f"Claim {self.claim_number}\n\n"
            f"{self.date_string} - {name_str}\n\n"
            f"{self.expense_text()}"
        )

    def first_class_claim_text(self, fetch_member=True) -> str:
        ticket_type = str(self.travel_type).strip().lower()
        assert ticket_type.upper() in FIRST_CLASS_TYPES

        # Get MP display string
        if not fetch_member or self.member() is None:
            name_str = f"Member:{self.member_id}"
        else:
            name_str = self.member.display_name

        # Include who its for if not for MP
        traveller = ""
        if self.is_staff_travel():
            traveller = " for staff"
        elif self.is_dependant_travel():
            traveller = " for a dependant"

        # Include if rail or plane
        if self.is_rail():
            transport = " on a train"
        elif self.is_air_travel():
            transport = " on a flight"
        else:
            raise Exception(f"Unrecognized transport type for expense {self}.")

        # Use journey if values given
        destinations = ""
        if None not in [self.travel_from, self.travel_to]:
            destinations = " from {} to {}".format(self.travel_from, self.travel_to)

        return (
            f"{name_str} claimed {self.amount_claimed_str()} "
            f"for a {ticket_type} ticket{traveller}{transport}{destinations}."
            f"\n\n{self.date_string()} - {self.claim_number}"
        )

    def expense_text(self) -> str:

        # Display cash amount
        text = f"{self.amount_claimed_str} for "

        # Construct relevant sentence.
        if self.is_transport_expense():
            text += self.transport_expense_text()
        elif self.is_overnight_expense():
            text += self.overnight_expense_text()
        else:
            text += "{}: {}".format(self.category, self.expense_type)
            if self.short_desc is not None:
                text += " - {}".format(self.short_desc)

        # Details at the end if available.
        if self.details is not None:
            text += " '{}'".format(self.details)

        return text

    def transport_expense_text(self) -> str:

        # Travel cat type (who travelled)
        text = "staff" if self.is_staff_travel() else ""
        text += "MP" if self.is_mp_travel() else ""
        text += "a dependant's" if self.is_dependant_travel() else ""

        # Show how far they travelled
        text += (
            " travel"
            if self.mileage is None
            else " travelling {} miles".format(self.mileage)
        )

        # Use journey if values given
        if None not in [self.travel_from, self.travel_to]:
            text += " from {} to {}".format(self.travel_from, self.travel_to)

        # Method of transport
        suffix_map = {
            "MILEAGE - CAR": " by car",
            "MILEAGE - BICYCLE": " by bicycle",
            "MILEAGE - MOTORCYCLE": " by motorcycle",
            "AIR TRAVEL": " by air",
            "RAIL": " by train",
            "TAXI": " by taxi",
        }
        text += suffix_map.get(self.expense_type, "")

        # Show seat class if train or plane
        if self.travel_type is not None:
            text += " ({})".format(self.travel_type)

        # Show price per mile if mileage is given
        ppm = self.price_per_mile
        if ppm is not None:
            text += " ({} per mile)".format(money_string(ppm))

        text += "."
        return text

    def overnight_expense_text(self) -> str:

        # Add amount of nights
        text = "a {} night ".format(self.nights) if self.nights is not None else "a "

        # Where they stayed
        accom_map = {
            "HOTEL - UK NOT LONDON": "stay at a non-London hotel",
            "HOTEL - LONDON": "stay at a London hotel",
            "HOTEL - EUROPEAN": "stay at a European hotel",
        }
        text += accom_map.get(self.expense_type.upper(), "hotel stay")

        # Show if staff or dependant
        if self.category.upper() == "STAFF TRAVEL":
            text += " for staff"
        elif self.category.upper() == "DEPENDANT TRAVEL":
            text += " for a dependant"

        # Price per night if available
        ppn = self.price_per_night
        if ppn is not None:
            text += " ({} per night)".format(money_string(ppn))

        text += "."
        return text


def exp_list_str(expenses: List[Expense]) -> str:
    if len(expenses) == 0:
        return f"0 expenses"
    if len(expenses) == 1:
        return f"1 expense on {expenses[0].date}"
    return f"{len(expenses)} expenses from {date_range(expenses)}"


def order_by_group(expenses: List[Expense]) -> dict:
    order = {}
    for expense in expenses:
        try:
            order[expense.group].append(expense)
        except KeyError:
            order[expense.group] = [expense]
    print(f"Found {len(order)} groups from {len(expenses)} expenses.")
    return order


def generate_group_thresholds(
    expenses: List[Expense], top_percentile: int, minimum_count: int
) -> Dict[str, float]:
    ordered = order_by_group(expenses)
    thresholds = {}
    for group, exp_list in ordered.items():
        amounts = [float(e.amount_claimed) for e in exp_list if e.amount_claimed > 0]
        if len(amounts) >= minimum_count:
            thresholds[group] = round(percentile(amounts, 100 - top_percentile), 3)
    return thresholds


def generate_travel_thresholds(
    expenses: List[Expense], top_percentile: int, minimum_count: int
) -> Dict[str, float]:
    per_unit_values = {}
    for e in expenses:

        if e.price_per_night is not None:
            unit = e.price_per_night
        elif e.price_per_mile is not None:
            unit = e.price_per_mile
        else:
            continue

        exp_type = e.expense_type.upper()
        try:
            per_unit_values[exp_type].append(unit)
        except KeyError:
            per_unit_values[exp_type] = [unit]

    thresholds = {}
    for exp_type, value_list in per_unit_values.items():
        amounts = [float(x) for x in value_list]
        if len(amounts) >= minimum_count:
            thresholds[exp_type] = round(percentile(amounts, 100 - top_percentile), 3)

    return thresholds


def date_range(expenses: List[Expense]) -> str:
    min_date = None
    max_date = None
    for e in expenses:
        min_date = e.date if min_date is None else min(e.date, min_date)
        max_date = e.date if max_date is None else max(e.date, max_date)
    return f"{min_date} - {max_date}"
