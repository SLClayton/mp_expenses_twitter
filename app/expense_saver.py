from datetime import datetime, date
from math import exp
from operator import attrgetter
from typing import Dict
from numpy import percentile

from expenses import *
from members import get_members_of_note_ids
from vals import MEMBERS_OF_NOTE_IDS, GROUP_THRESHOLDS


def get_year_codes():
    this_year = datetime.utcnow().year
    next_next_year = this_year + 2
    next_year = this_year + 1
    last_year = this_year - 1
    last_last_year = this_year - 2

    return [
        "{}_{}".format(str(next_year)[-2:], str(next_next_year)[-2:]),
        "{}_{}".format(str(this_year)[-2:], str(next_year)[-2:]),
        "{}_{}".format(str(last_year)[-2:], str(this_year)[-2:]),
        "{}_{}".format(str(last_last_year)[-2:], str(last_year)[-2:])
        ]


def expense_filter(expense: Expense) -> bool:
    
    # Basic filter
    if (str(expense.claim_number) == "1" or expense.amount_claimed <= 0):
        return False

    # If a popular MP, use their expense regardless
    if expense.member_id in MEMBERS_OF_NOTE_IDS:
        return True

    # Ignore 1.00 rail booking fees
    if (expense.amount_claimed == 1 and "BOOKING FEE" in str(expense.short_desc).upper()):
        return False

    # Always use very small claims
    if expense.amount_claimed < 4:
        return True

    # Check expense 'group' and if amount is above group threshold value
    group = expense.group()
    if group not in GROUP_THRESHOLDS:
        return True
    if expense.amount_claimed > GROUP_THRESHOLDS[group]:
        return True

    return False


def save_new_expenses():
    # Get every expense from prev year to next years
    year_codes = get_year_codes()
    print(f"Using year codes {year_codes}")
    all_expenses = []
    for year_code in year_codes:
        all_expenses += get_expenses(year_code, force=False)
    print(f"Found a total of {len(all_expenses)} expenses fron years {year_codes}")

