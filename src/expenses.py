from math import exp
from pathlib import Path
from datetime import datetime, time, date
from decimal import Decimal
import requests
import pandas as pd
from typing import List, Optional
from numpy import e, nan
from io import StringIO
from pathlib import Path
import random
from numpy import percentile
from logging import getLogger
from functools import cached_property

from members import get_member, Member
from tools import *
from aws_tools import *

log = getLogger()

CACHE_DIR = "../csv_cache"
FIRST_CLASS_TYPES_WHITELIST = [
    "FIRST RETURN",
    "FIRST SINGLE",
    "BUSINESS / CLUB RETURN",
    "BUSINESS / CLUB SINGLE",
]

EXPECTED_FIELDS = [
    "Parliamentary ID",
    "Year",
    "Date",
    "Claim Number",
    "Name",
    "Constituency",
    "Category",
    "Cost Type",
    "Short Description",
    "Details",
    "Journey Type",
    "From",
    "To",
    "Travel",
    "Nights",
    "Mileage",
    "Amount Claimed",
    "Amount Paid",
    "Amount Not Paid",
    "Amount Repaid",
    "Status",
    "Reason If Not Paid",
    "Supply Month",
    "Supply Period",
]


class Expense:

    def __init__(self, data):
        self._data = data
        self._member = None

    @property
    def member_id(self) -> int:
        return int(self._data["Parliamentary ID"])

    @property
    def year_code(self) -> str:
        return self._data["Year"]

    @property
    def date(self) -> date:
        return parse_date(self._data["Date"])

    @property
    def claim_number(self) -> str:
        return self._data["Claim Number"]

    @property
    def category(self) -> str:
        return self._data["Category"]

    @property
    def expense_type(self) -> str:
        return self._data["Cost Type"]

    @property
    def amount_claimed(self) -> Decimal:
        return Decimal(str(self._data["Amount Claimed"]))

    @property
    def amount_paid(self) -> Decimal:
        return Decimal(str(self._data["Amount Paid"]))

    @property
    def status(self) -> str:
        return self._data["Status"]

    @property
    def short_desc(self) -> str:
        return self._data.get("Short Description") or None

    @property
    def details(self) -> str:
        return self._data.get("Details") or None

    @property
    def travel_from(self) -> str:
        return self._data.get("From") or None

    @property
    def travel_to(self) -> str:
        return self._data.get("To") or None

    @property
    def travel_type(self) -> str:
        return self._data.get("Travel") or None

    @property
    def mileage(self) -> Optional[Decimal]:
        try:
            mileage = Decimal(str(self._data.get("Mileage")))
            assert mileage > 0
            return mileage
        except Exception:
            return None

    @property
    def nights(self) -> Optional[Decimal]:
        try:
            nights = Decimal(str(self._data.get("Nights")))
            assert nights > 0
            return nights
        except Exception:
            return None

    def __repr__(self):
        mp_string = self.member.name if self._member is not None else self.member_id
        return (
            f"<Expense {self.claim_number} on {self.date} mp={mp_string}: "
            f"{money_string(self.amount_claimed)} for {self.category} - {self.expense_type} - {self.short_desc}>"
        )

    def group(self) -> str:
        return "/".join(
            [
                str(self.category).strip(),
                str(self.expense_type).strip(),
                str(self.short_desc).strip(),
            ]
        ).upper()

    @cached_property
    def member(self) -> Optional[Member]:
        if "DUMMY" in self.claim_number:
            return None
        self._member = get_member(self.member_id)
        return self._member

    def amount_claimed_str(self) -> str:
        return money_string(self.amount_claimed)

    def base_claim_number(self) -> int:
        return int(self.claim_number.split("-")[0])

    def price_per_mile(self) -> Optional[Decimal]:
        if self.mileage is None or self.mileage <= 0 or self.amount_claimed <= 0:
            return None
        return round(Decimal(self.amount_claimed / self.mileage), 2)

    def price_per_night(self) -> Optional[Decimal]:
        if self.nights is None or self.nights <= 0 or self.amount_claimed <= 0:
            return None
        return round(Decimal(self.amount_claimed / self.nights), 2)

    def price_per_unit(self) -> Optional[Decimal]:
        ppm = self.price_per_mile()
        ppn = self.price_per_night()

        if None not in [ppm, ppn]:
            print(
                f"WARNING: Expense {self.claim_number} has both PPM ({ppm}) and a PPN ({ppn}) value. {self}"
            )
            return None

        if ppm is not None:
            return ppm
        if ppn is not None:
            return ppn
        return None

    def date_string(self) -> str:
        day = str(self.date.day)
        if day.startswith("0"):
            day = day[1:]
        datestring = f"{day} {self.date.strftime('%b %y')}"
        return datestring

    def is_rail_booking_fee(self) -> bool:
        return self.is_rail() and (
            "BOOKING FEE" in str(self.short_desc).upper() or self.amount_claimed == 1
        )

    def is_first_class(self) -> bool:
        travel_type = str(self.travel_type).upper().strip()
        if travel_type in FIRST_CLASS_TYPES_WHITELIST:
            return True

        keywords = ["FIRST", "BUSINESS", "CLUB", "PREMIUM"]
        if any(word in travel_type for word in keywords):
            log.warn(
                f"Expense {self.claim_number} travel type '{travel_type}' doesn't appear in "
                f"{FIRST_CLASS_TYPES_WHITELIST} but has keyword match from {keywords}."
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
            name_str = self.member.display_name()

        return (
            f"Claim {self.claim_number}\n\n"
            f"{self.date_string()} - {name_str}\n\n"
            f"{self.expense_text()}"
        )

    def first_class_claim_text(self, fetch_member=True) -> str:
        ticket_type = str(self.travel_type).strip().lower()
        assert ticket_type.upper() in FIRST_CLASS_TYPES_WHITELIST

        # Get MP display string
        if not fetch_member or self.member() is None:
            name_str = f"Member:{self.member_id}"
        else:
            name_str = self.member().display_name()

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
        text = f"{self.amount_claimed_str()} for "

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
        text += suffix_map.get(self.expense_type.upper(), "")

        # Show seat class if train or plane
        if self.travel_type is not None:
            text += " ({})".format(self.travel_type)

        # Show price per mile if mileage is given
        ppm = self.price_per_mile()
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
        ppn = self.price_per_night()
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


def print_exps(expenses: List[Expense]) -> None:
    print(exp_list_str(expenses))


def dummyExpense() -> Expense:
    claim_data = {}
    claim_data["claimNumber"] = "0-DUMMY_CLAIM_" + rndstring(5)
    claim_data["year"] = "20_21"
    claim_data["date"] = "2021-02-02"
    claim_data["nights"] = ""
    claim_data["mileage"] = ""
    claim_data["amountClaimed"] = random.randint(10, 100)
    claim_data["amountPaid"] = claim_data["amountClaimed"]
    claim_data["memberId"] = random.randint(1000000, 9999999)

    for field in EXPECTED_FIELDS:
        if field not in claim_data:
            claim_data[field] = rndstring(6)
    return Expense(claim_data)


def get_cached_csv_path(year_code) -> str:
    return os.path.join(Path(__file__).parent.absolute(), CACHE_DIR, f"{year_code}.csv")


def get_cache_csv(year_code) -> str:
    cached_path = get_cached_csv_path(year_code)
    try:
        csv_text = load_text(cached_path)
        print(f"Found cache file {cached_path} so using that.")
        return csv_text
    except FileNotFoundError:
        pass
    return None


def save_cache_csv(csv_string, year_code) -> None:
    cached_path = get_cached_csv_path(year_code)
    Path(cached_path).parent.mkdir(parents=True, exist_ok=True)
    save_text(csv_string, cached_path)


def get_expenses_csv(year_code, force=False) -> str:

    # Try find in cache
    if not force:
        csv_text = get_cache_csv(year_code)
        if csv_text is not None:
            return csv_text

    # Go download file
    # url = f"https://www.theipsa.org.uk/api/download?type=individualExpenses&year={year_code}"
    url = f"https://www.theipsa.org.uk/api/download?type=individualBusinessCosts&year={year_code}"
    resp = None
    while resp is None:
        try:
            print(f"Attempting to get {year_code} claim data from {url}")
            start = datetime.utcnow()
            resp = requests.get(url)
            seconds = (datetime.utcnow() - start).total_seconds()
        except Exception as e:
            print(
                f"Exception {e} trying to get claims data for code {year_code}, trying again in 3 seconds."
            )
            time.sleep(3)
            continue

    resp.encoding = "utf-8"
    csv_text = resp.text
    print(f"Downloaded {year_code} csv of length {len(csv_text)} in {seconds} seconds.")

    # Save to cache
    if not in_aws():
        save_cache_csv(csv_text, year_code)

    return csv_text


def get_expenses(year_code, force=False) -> List[Expense]:
    exp_dicts = (
        pd.read_csv(StringIO(get_expenses_csv(year_code, force)), na_values=None)
        .replace({nan: None})
        .to_dict("records")
    )
    min_date = None
    max_date = None
    expenses = []

    # Check for empty list
    if len(exp_dicts) == 1 and all(val is None for val in exp_dicts[0].values()):
        print(f"Empty list found for Expense year {year_code}")
        return expenses

    for exp_data in exp_dicts:
        # Check expense data format is expected
        if not all(field in exp_data for field in EXPECTED_FIELDS):
            err = f"Invalid expense dict format found."
            print(err)
            pp(exp_data)
            raise Exception(err)
        else:
            try:
                expense = Expense(exp_data)
                min_date = min(e for e in [expense.date, min_date] if e is not None)
                max_date = max(e for e in [expense.date, max_date] if e is not None)
                expenses.append(expense)
            except Exception as e:
                print(f"Error creating Expense object - {e}")
                pp(expense)
                raise e

    print(
        f"Found {len(expenses)} expenses for year code '{year_code}' "
        f"from {min_date} to {max_date}."
    )
    return expenses


def get_mulityear_expenses(year_codes, force=False) -> List[Expense]:
    expenses = []
    for year_code in year_codes:
        expenses += get_expenses(year_code, force)
    return expenses


def order_by_group(expenses: List[Expense]) -> dict:
    order = {}
    for expense in expenses:
        try:
            order[expense.group()].append(expense)
        except KeyError:
            order[expense.group()] = [expense]
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

        if e.price_per_night() is not None:
            unit = e.price_per_night()
        elif e.price_per_mile() is not None:
            unit = e.price_per_mile()
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


def get_year_codes_range(from_year: int, to_year: int) -> List[str]:
    return [
        "{}_{}".format(str(year)[-2:], str(year + 1)[-2:])
        for year in range(from_year, to_year)
    ]


def get_expenses_since_year(from_year: int) -> List[Expense]:
    year_codes = get_year_codes_range(from_year, datetime.utcnow().year)
    return get_mulityear_expenses(year_codes, force=True)


if __name__ == "__main__":
    expenses = get_expenses("22_23", force=True)
    for e in expenses:
        print(e.expense_text())
