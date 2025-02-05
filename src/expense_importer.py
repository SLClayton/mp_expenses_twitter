import os
from datetime import datetime
import requests
from typing import List
import time
from io import StringIO
import pandas as pd
from numpy import nan
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from aws_tools import in_aws
from expenses import Expense
from tools import pp, load_text, save_text, get_year_codes_range


CACHE_DIR = "../csv_cache"
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


def get_expenses_csv(year_code: str, force: bool = False) -> str:
    """Download the Expense data CSV for the yearcode given."""

    # Try find in cache
    if not force:
        csv_text = get_cache_csv(year_code)
        if csv_text is not None:
            return csv_text

    # Go download file
    url = f"https://www.theipsa.org.uk/api/download?type=individualBusinessCosts&year={year_code}"
    resp = None
    while resp is None:
        try:
            print(f"Attempting to get {year_code} claim data from {url}")
            start = datetime.utcnow()
            resp = requests.get(url)
            seconds = (datetime.utcnow() - start).total_seconds()
        except Exception as e:
            print(f"Exception {e} trying to get {year_code} data, retrying...")
            time.sleep(2)
            continue

    resp.encoding = "utf-8"
    csv_text = resp.text
    print(f"Downloaded {year_code} csv of length {len(csv_text)} in {seconds} seconds.")

    # Save to cache
    if not in_aws():
        save_cache_csv(csv_text, year_code)

    return csv_text


def get_expenses(year_code: str, force: bool = False) -> List[Expense]:
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


def get_mulityear_expenses_single(year_codes: List[str], force: bool = False) -> List[Expense]:
    expenses = []
    for year_code in year_codes:
        expenses += get_expenses(year_code, force)
    return expenses


def get_mulityear_expenses(year_codes: List[str], force: bool = False) -> List[Expense]:
    with ThreadPoolExecutor() as executor:
        results = executor.map(lambda year: get_expenses(year, force), year_codes)
    return [expense for sublist in results for expense in sublist]


def get_expenses_since_year(from_year: int) -> List[Expense]:
    year_codes = get_year_codes_range(from_year, datetime.utcnow().year)
    return get_mulityear_expenses(year_codes, force=True)


def save_cache_csv(csv_string: str, year_code: str) -> None:
    cached_path = cached_csv_path(year_code)
    Path(cached_path).parent.mkdir(parents=True, exist_ok=True)
    save_text(csv_string, cached_path)


def cached_csv_path(year_code: str) -> str:
    return os.path.join(Path(__file__).parent.absolute(), CACHE_DIR, f"{year_code}.csv")


def get_cache_csv(year_code: str) -> str:
    cached_path = cached_csv_path(year_code)
    try:
        csv_text = load_text(cached_path)
        print(f"Found cache file {cached_path} so using that.")
        return csv_text
    except FileNotFoundError:
        pass
    return None
