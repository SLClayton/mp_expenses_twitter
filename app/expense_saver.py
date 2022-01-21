from datetime import datetime, date
from operator import attrgetter

from expenses import *
from members import get_members_of_note_ids
from timing import *

MIN_DATE_LIMIT = date(2021, 5, 25)

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

    # Date must be new enough and not in future
    if not (MIN_DATE_LIMIT < expense.date < date.today()):
        return False
    
    # Basic filter
    if (str(expense.claim_number) == "1" or expense.amount_claimed <= 0):
        return False

    # If a popular MP, use their expense regardless
    member_of_note_ids = get_members_of_note_ids()
    if expense.member_id in member_of_note_ids:
        return True

    # Ignore booking fees
    if expense.is_booking_fee() and expense.amount_claimed <= 5:
        return False

    # Always use very small claims
    if expense.amount_claimed < 4:
        return True

    # Check expense is a per unit cost (Overnight stay or transport mileage)
    exp_type = expense.expense_type.upper()
    travel_thresholds = get_travel_thresholds()
    price_per_unit = expense.price_per_unit()
    if (expense.is_transport_expense() or expense.is_overnight_expense()) and price_per_unit is not None:
        if exp_type not in travel_thresholds or price_per_unit >= travel_thresholds[exp_type]:
            return True
        return False

    # Check expense 'group' and if amount is above group threshold value
    group = expense.group()
    group_thresholds = get_group_thresholds()
    if group not in group_thresholds or expense.amount_claimed >= group_thresholds[group]:
        return True

    return False
