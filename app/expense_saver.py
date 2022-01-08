from datetime import datetime, date
from math import exp
from operator import attrgetter

from expenses import *
from members import get_members_of_note_ids

members_of_note_ids = get_members_of_note_ids()

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
    if (str(expense.claim_number) == "1" or 
            expense.amount_claimed > 0):
        return False

    # If a popular MP, use their expense regardless
    if expense.id in members_of_note_ids:
        return True

    # Ignore 1.00 rail booking fees
    if ("BOOKING FEE" in expense.short_desc.upper() and expense.amount_claimed == 1):
        return False

    # Use very small claims
    if expense.amount_claimed < 6:
        return True

    return True


def save_new_expenses():

    # Get every expense from prev year to next years
    year_codes = get_year_codes()
    print(f"Using year codes {year_codes}")
    all_expenses = []
    for year_code in year_codes:
        all_expenses += get_expenses(year_code, force=False)
    print(f"Found a total of {len(all_expenses)} expenses fron years {year_codes}")

    # Filter list
    prev_claim_numbers = get_previous_claim_numbers()

    expenses = [e for e in all_expenses if
                e.claim_number != "1" and
                e.amount_claimed > Decimal(0) and
                e.date > date(2021, 4, 26) and
                e.claim_number not in prev_claim_numbers
                ]

    print(f"Found {len(expenses)}/{len(all_expenses)} expenses that claim > 0.00 and "
          f"have a claim number that isn't '1' or in the previous claim set.")




