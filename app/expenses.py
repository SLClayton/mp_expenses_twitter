from math import exp
from pathlib import Path
from datetime import datetime, time
from decimal import Decimal
import requests
import pandas as pd
from typing import List
from pandas import DataFrame
from numpy import e, nan
from io import StringIO
from pathlib import Path
import random
from numpy import percentile
from logging import getLogger

from members import get_member
from tools import *
from aws_tools import *
from vals import GROUP_THRESHOLDS_KEY, S3_BUCKET, S3_EXCEPTION_QUEUE_KEY, S3_EXPENSE_QUEUE_KEY, S3_PREV_CLAIM_NUMBERS_KEY, TRAVEL_THRESHOLDS_KEY


log = getLogger()

CACHE_DIR = "csv_cache"
EXPECTED_FIELDS = [
    "memberId", "year", "date", "claimNumber", "category", "expenseType", "shortDescription",
    "details", "journeyType", "journeyFrom", "journeyTo", "travel", "nights", "mileage",
    "amountClaimed", "amountPaid", "amountNotPaid", "amountRepaid", "status", "reasonIfNotPaid",
    "supplyMonth", "supplyPeriod"]
FIRST_CLASS_TYPES_WHITELIST = ["FIRST RETURN", "FIRST SINGLE", "BUSINESS / CLUB RETURN", "BUSINESS / CLUB SINGLE"]


_GROUP_THRESHOLDS = None
_TRAVEL_THRESHOLDS = None


class Expense:

    def __init__(self, data):
        self.data = data
        self._member = None

        self.member_id = int(data["memberId"])
        self.year_code = data["year"]
        self.date = parse_date(data["date"].split("T")[0])
        self.claim_number = data["claimNumber"]
        self.category = data["category"]
        self.expense_type = data["expenseType"]
        self.amount_claimed = Decimal(str(data["amountClaimed"]))
        self.amount_paid = Decimal(str(data["amountPaid"]))
        self.status = data["status"]

        self.short_desc = data.get("shortDescription") or None
        self.details = data.get("details") or None
        self.travel_from = data.get("journeyFrom") or None
        self.travel_to = data.get("journeyTo") or None
        self.travel_type = data.get("travel") or None

        try:
            self.mileage = Decimal(str(data.get("mileage")))
            assert self.mileage > 0
        except Exception:
            self.mileage = None

        try:
            self.nights = Decimal(str(data.get("nights")))
            assert self.nights > 0
        except Exception:
            self.nights = None

    def __repr__(self):
        mp_string = self._member.name if self._member is not None else self.member_id
        return (
            f"<Expense {self.claim_number} on {self.date} mp={mp_string}: "
            f"{money_string(self.amount_claimed)} for {self.category} - {self.expense_type} - {self.short_desc}>"
        )

    def group(self):
        return "/".join([
            str(self.category).strip(), 
            str(self.expense_type).strip(), 
            str(self.short_desc).strip()
            ]).upper()

    def member(self):
        if "DUMMY" in self.claim_number:
            return None
        if self._member is None:
            self._member = get_member(self.member_id)
        return self._member

    def amount_claimed_str(self) -> str:
        return money_string(self.amount_claimed)

    def base_claim_number(self) -> int:
        return int(self.claim_number.split("-")[0])

    def price_per_mile(self):
        if self.mileage is None or self.mileage <= 0 or self.amount_claimed <= 0:
            return None
        return round(Decimal(self.amount_claimed / self.mileage), 2)

    def price_per_night(self):
        if self.nights is None or self.nights <= 0 or self.amount_claimed <= 0:
            return None
        return round(Decimal(self.amount_claimed / self.nights), 2)

    def price_per_unit(self):
        ppm = self.price_per_mile()
        ppn = self.price_per_night()

        if None not in [ppm, ppn]:
            print(f"WARNING: Expense {self.claim_number} has both PPM ({ppm}) and a PPN ({ppn}) value.")
            return None

        if ppm is not None:
            return ppm
        if ppn is not None:
            return ppn
        return None

    def date_string(self):
        day = str(self.date.day)
        if day.startswith("0"):
            day = day[1:]
        datestring = f"{day} {self.date.strftime('%b %y')}"
        return datestring

    def is_rail_booking_fee(self) -> bool:
        return (
            self.is_rail() and 
            ("BOOKING FEE" in str(self.short_desc).upper() or self.amount_claimed == 1))

    def is_first_class(self) -> bool:
        travel_type = str(self.travel_type).upper().strip()
        if travel_type in FIRST_CLASS_TYPES_WHITELIST:
            return True

        keywords = ["FIRST", "BUSINESS", "CLUB", "PREMIUM"]
        if any(word in travel_type for word in keywords):
            log.warn(f"Expense {self.claim_number} travel type '{travel_type}' doesn't appear in "
                     f"{FIRST_CLASS_TYPES_WHITELIST} but has keyword match from {keywords}." )
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
            "TAXI"]

    def is_overnight_expense(self) -> bool:
        return self.expense_type.upper() in [
            "HOTEL - UK NOT LONDON", 
            "HOTEL - LONDON", 
            "HOTEL - EUROPEAN",
            "HOTEL - LATE NIGHT"]

    def claim_text(self, fetch_member=True):
        if not fetch_member or self.member() is None:
            name_str = f"Member:{self.member_id}"
        else:
            name_str = self.member().display_name()

        return (
            f"Claim {self.claim_number}\n\n"
            f"{self.date_string()} - {name_str}\n\n"
            f"{self.expense_text()}")


    def first_class_claim_text(self, fetch_member=True):
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
        if None not in [self.travel_from, self.travel_to]:
            destinations = " from {} to {}".format(self.travel_from, self.travel_to)


        return (f"{name_str} claimed {self.amount_claimed_str()} "
                f"for a {ticket_type} ticket{traveller}{transport}{destinations}."
                f"\n\n{self.claim_number} - {self.date_string()}")


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
        text += " travel" if self.mileage is None else " travelling {} miles".format(self.mileage)

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
            "TAXI": " by taxi"}
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
            "HOTEL - EUROPEAN": "stay at a European hotel"
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


def print_exp(expenses: List[Expense]):
    print(exp_list_str(expenses))


def dummyExpense():
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


    sorted_by_type = sort_by_exp_type(expenses)

    claimed_ranges = {}
    for type, exp_list in sorted_by_type.items():

        regular = []
        with_mileage = []
        with_nights = []

        for e in exp_list:
            pricePerMile = e.pricePerMile()
            pricePerNight = e.pricePerNight()

            if pricePerMile is not None:
                with_mileage.append(float(pricePerMile))
            elif pricePerNight is not None:
                with_nights.append(float(pricePerNight))
            else:
                regular.append(float(e.amount_claimed))

        claimed_ranges[type] = sorted(regular)
        if len(with_mileage) > 0:
            claimed_ranges["{} mileage".format(type)] = sorted(with_mileage)
        if len(with_nights) > 0:
            claimed_ranges["{} nights".format(type)] = sorted(with_nights)

    return claimed_ranges


def get_cached_csv_path(year_code):
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


def save_cache_csv(csv_string, year_code):
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
    url = f"https://www.theipsa.org.uk/api/download?type=individualExpenses&year={year_code}"
    resp = None
    while resp is None:
        try:
            print(f"Attempting to get {year_code} claim data from {url}")
            start = datetime.utcnow()
            resp = requests.get(url)
            seconds = (datetime.utcnow()-start).total_seconds()
        except Exception as e:
            print(f"Exception {e} trying to get claims data for code {year_code}, trying again in 3 seconds.")
            time.sleep(3)
            continue

    resp.encoding = "utf-8"
    csv_text = resp.text
    print(f"Downloaded {year_code} csv of length {len(csv_text)} in {seconds} seconds.")

    # Save to cache
    if not in_aws():
        save_cache_csv(csv_text, year_code)

    return csv_text


def get_expenses_df(year_code, force=False) -> DataFrame:
    return pd.read_csv(StringIO(get_expenses_csv(year_code, force)))


def get_expenses_dicts(year_code, force=False) -> List[dict]:
    return get_expenses_df(year_code, force).replace({nan: None}).to_dict("records")


def get_expenses(year_code, force=False) -> List[Expense]:
    exp_dicts = get_expenses_dicts(year_code, force)
    min_date = None 
    max_date = None
    expenses = []
    for exp_data in exp_dicts:
        if all(field in exp_data for field in EXPECTED_FIELDS):
            expense = Expense(exp_data)
            min_date = min(e for e in [expense.date, min_date] if e is not None)
            max_date = max(e for e in [expense.date, max_date] if e is not None)
            expenses.append(expense)
        else:
            print(f"Invalid expense dict format found.")

    print(f"Found {len(expenses)} expenses for year code '{year_code}' "
          f"from {min_date} to {max_date}.")
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


def generate_group_thresholds(expenses, top_percentile, minimum_count):
    ordered = order_by_group(expenses)
    thresholds = {}
    for group, exp_list in ordered.items():
        amounts = [float(e.amount_claimed) for e in exp_list if e.amount_claimed > 0]
        if len(amounts) >= minimum_count:
            thresholds[group] = round(percentile(amounts, 100-top_percentile), 3)
    return thresholds


def generate_travel_thresholds(expenses: List[Expense], top_percentile, minimum_count):
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
            thresholds[exp_type] = round(percentile(amounts, 100-top_percentile), 3)

    return thresholds
            

def get_travel_thresholds() -> dict:
    global _TRAVEL_THRESHOLDS
    if _TRAVEL_THRESHOLDS is None:
        _TRAVEL_THRESHOLDS = get_json_from_s3(S3_BUCKET, TRAVEL_THRESHOLDS_KEY)
    return _TRAVEL_THRESHOLDS


def get_group_thresholds() -> dict:
    global _GROUP_THRESHOLDS
    if _GROUP_THRESHOLDS is None:
        _GROUP_THRESHOLDS = get_json_from_s3(S3_BUCKET, GROUP_THRESHOLDS_KEY)
    return _GROUP_THRESHOLDS


def date_range(expenses: List[Expense]) -> str:
    min_date = None
    max_date = None
    for e in expenses:
        min_date = e.date if min_date is None else min(e.date, min_date)
        max_date = e.date if max_date is None else max(e.date, max_date)
    return f"{min_date} - {max_date}"


def get_year_codes_range(from_year: int, to_year: int):
    return [
        "{}_{}".format(str(year)[-2:], str(year + 1)[-2:]) 
        for year in range(from_year, to_year)
    ]


def save_new_thresholds(top_percentile, save_s3=False, save_local=False):
    year_codes = get_year_codes_range(2020, 2021)
    expenses = get_mulityear_expenses(year_codes, force=False)
    travel_th = generate_travel_thresholds(expenses, top_percentile, 20)
    group_th = generate_group_thresholds(expenses, top_percentile, 20)

    if save_s3:
        save_json_to_s3(travel_th, S3_BUCKET, TRAVEL_THRESHOLDS_KEY, indent=2)
        save_json_to_s3(group_th, S3_BUCKET, GROUP_THRESHOLDS_KEY, indent=2)

    if save_local:
        with open(GROUP_THRESHOLDS_KEY, "w") as f:
            json.dump(group_th, f)

        with open(TRAVEL_THRESHOLDS_KEY, "w") as f:
            json.dump(travel_th, f)


def get_expense_queue() -> List[Expense]:
    json_list = get_json_from_s3(S3_BUCKET, S3_EXPENSE_QUEUE_KEY)
    return [Expense(exp_data) for exp_data in json_list]


def save_expense_queue(expenses):
    queue = [e.data for e in expenses]
    save_json_to_s3(queue, S3_BUCKET, S3_EXPENSE_QUEUE_KEY)


def add_to_exception_queue(expense):
    print(f"Placing expense in exception queue: {expense}")
    exception_queue = get_json_from_s3(S3_BUCKET, S3_EXCEPTION_QUEUE_KEY)
    exception_queue.append(expense.data)
    save_json_to_s3(exception_queue, S3_BUCKET, S3_EXCEPTION_QUEUE_KEY)


def get_previous_claim_numbers() -> set:
    return set(get_list_from_s3(S3_BUCKET, S3_PREV_CLAIM_NUMBERS_KEY))


def save_previous_claim_numbers(claim_numbers):
    save_list_to_s3(claim_numbers, S3_BUCKET, S3_PREV_CLAIM_NUMBERS_KEY)