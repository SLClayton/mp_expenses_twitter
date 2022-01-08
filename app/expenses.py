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
from operator import attrgetter

from members import get_member
from tools import *
from aws_tools import *


S3_BUCKET = "mpexpenses"
S3_EXPENSE_QUEUE_KEY = "new_expenses_queue.json"
S3_PREV_CLAIM_NUMBERS_KEY = "previous_claimNumbers.txt"


CACHE_DIR = "csv_cache"
EXPECTED_FIELDS = [
    "memberId", "year", "date", "claimNumber", "category", "expenseType", "shortDescription",
    "details", "journeyType", "journeyFrom", "journeyTo", "travel", "nights", "mileage",
    "amountClaimed", "amountPaid", "amountNotPaid", "amountRepaid", "status", "reasonIfNotPaid",
    "supplyMonth", "supplyPeriod"]


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
            f"<Expense {self.date} no={self.claim_number} mp={mp_string}: "
            f"{money_string(self.amount_claimed)} for {self.category} - {self.expense_type}>"
        )

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

    def pricePerMile(self):
        if self.mileage is None or self.mileage <= 0 or self.amount_claimed <= 0:
            return None
        return round(Decimal(self.amount_claimed / self.mileage), 2)

    def pricePerNight(self):
        if self.nights is None or self.nights <=0 or self.amount_claimed <=0:
            return None
        return round(Decimal(self.amount_claimed / self.nights), 2)

    def claim_text(self, fetch_member=True):
        if not fetch_member or self.member() is None:
            name_str = f"Member:{self.member_id}"
        else:
            name_str = self.member().display_name()

        return (
            f"Claim {self.claim_number}\n\n"
            f"{self.date_string()} - {name_str}"
            f"\n\n{self.expense_text()}")

    def date_string(self):
        day = str(self.date.day)
        if day.startswith("0"):
            day = day[1:]
        datestring = f"{day} {self.date.strftime('%b %y')}"
        return datestring

    def is_travel_expense(self) -> bool:
        return self.expense_type.upper() in [
            "MILEAGE - CAR", 
            "MILEAGE - MOTORCYCLE",
            "MILEAGE - BICYCLE",
            "AIR TRAVEL", 
            "RAIL", 
            "TAXI"]

    def is_overnight_expense(self) -> bool:
        return self.expense_type in [
            "HOTEL - UK NOT LONDON", 
            "HOTEL - LONDON", 
            "HOTEL - EUROPEAN",
            "HOTEL - LATE NIGHT"]

    def expense_text(self):
        text = f"{self.amount_claimed_str()} for"

        if self.is_travel_expense():
            text += " " + self.travel_expense_text()
        elif self.is_overnight_expense():
            text += " " + self.overnight_expense_text()
        else:
            text += " {}: {}".format(self.category, self.expense_type)
            if self.short_desc is not None:
                text += " - {}".format(self.short_desc)

        # Details at the end if available.
        if self.details is not None:
            text += " '{}'".format(self.details)

        return text

    def travel_expense_text(self):
        # Travel cat type (who travelled)
        text = "staff" if self.category == "Staff Travel" else ""
        text += " MP" if self.category == "MP Travel" else ""
        text += " dependant" if self.category == "Dependant Travel" else ""

        # Show how far they travelled
        text += " travel" if self.mileage is None else " travelling {} miles".format(self.mileage)


        if None not in [self.travel_from, self.travel_to]:
            text += " from {} to {}".format(self.travel_from, self.travel_to)

        suffix_map = {"Mileage - car": " by car",
                        "Mileage - bicycle": " by bicycle",
                        "Mileage - motorcycle": " by motorcycle",
                        "Air travel": " by air travel",
                        "Rail": " by train",
                        "Taxi": " by taxi"}
        text += suffix_map.get(self.expense_type, "")

        if self.expense_type == "Rail" and self.travel_type is not None:
            text += " ({})".format(self.travel_type)

        ppm = self.pricePerMile()
        if ppm is not None:
            text += " ({} per mile)".format(money_string(ppm))

        text += "."
        return text

    def overnight_expense_text(self):
        text = "staff" if self.category == "Staff Travel" else ""
        text += " dependant" if self.category == "Dependant Travel" else ""
        text += " {} night".format(self.nights) if self.nights is not None else ""

        text += " stay at"

        accom_map = {
            "Hotel - UK Not London": "non-London hotel",
            "Hotel - London": "London hotel",
            "Hotel - European": "European hotel"
        }
        text += " " + accom_map.get(self.expense_type, 'hotel')

        ppn = self.pricePerNight()
        if ppn is not None:
            text += " ({} per night)".format(money_string(ppn))

        text += "."
        return text

    def queue_format(self) -> dict:
        datestring = date.today().strftime("%Y-%m-%d")
        return {
            "claimNumber": self.claim_number,
            "discovery_date": datestring,
            "claim": self.data
        }

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
            print(f"Invalid expense dict format found: {exp_data}")

    print(f"Found {len(expenses)} expenses for year code '{year_code}' "
          f"from {min_date} to {max_date}.")
    return expenses


def get_queue_expenses() -> List[Expense]:
    print(f"Getting expense queue from S3://{S3_BUCKET}/{S3_EXPENSE_QUEUE_KEY}")
    start = datetime.utcnow()
    queue_json = get_json_from_s3(S3_BUCKET, S3_EXPENSE_QUEUE_KEY)
    print(f"Downloaded queue from S3 in {(datetime.utcnow() - start).total_seconds()} seconds.")
    expenses = sorted([Expense(data["item"]) for data in queue_json.values()], key=attrgetter("date"))
    return expenses


def get_previous_claim_numbers() -> set:
    print(f"Getting previous claim numbers from S3://{S3_BUCKET}/{S3_PREV_CLAIM_NUMBERS_KEY}")
    start = datetime.utcnow()
    prev_claimnumbers_list = get_list_from_s3(S3_BUCKET, S3_PREV_CLAIM_NUMBERS_KEY)
    seconds = (datetime.utcnow() - start).total_seconds()
    print(f"Downloaded prev claimnumbers from S3 in {seconds} seconds.")
    return set(prev_claimnumbers_list)


def order_by_desc(expenses: List[Expense]) -> dict:
    order = {}
    for expense in expenses:
        desc = "/".join([expense.category, expense.expense_type, str(expense.short_desc)])
        try:
            order[desc].append(expense)
        except KeyError:
            order[desc] = [expense]
    print(f"Found {len(order)} groups from {len(expenses)} expenses.")
    return order

expenses = get_expenses("20_21")
order = order_by_desc(expenses)

order_less = {}
for group, expense_list in order.items():
    if len(expense_list) >= 100:
        order_less[group] = expense_list



save_json(order_less, "test3.json")


