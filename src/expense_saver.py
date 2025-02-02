from datetime import datetime, date
from typing import List

from expenses import (
    Expense, 
    generate_group_thresholds, 
    generate_travel_thresholds,
)
from members import is_member_of_note

MIN_DATE_LIMIT = date(2023, 8, 1)
MAX_DATE_LIMIT = date.today()

def get_year_codes() -> List[str]:
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


def expenses_filter(expenses: List[Expense]) -> List[Expense]:
    travel_thresholds = generate_travel_thresholds(expenses, 5, 20)
    group_thresholds = generate_group_thresholds(expenses, 5, 20)
    return [e for e in expenses if expense_filter(e, travel_thresholds, group_thresholds)]


def expense_filter(expense: Expense, travel_thresholds: dict, group_thresholds: dict) -> bool:
    try:
        # Date must be new enough and not in future
        if expense.date > date.today():
            return False
        
        # Basic filter
        if (str(expense.claim_number) == "1" or expense.amount_claimed <= 0):
            return False
        
        # Ignore rail booking fees
        if expense.is_rail_booking_fee() and expense.amount_claimed <= 5:
            return False

        # First class handled by other bot
        #if expense.is_first_class():
        #    return False

        # If a popular MP, use their expense regardless
        if is_member_of_note(expense.member_id):
            return True

        # Always use certain expense types
        if any((
            expense.is_air_travel(),
            #expense.is_taxi_ride(),
            #expense.is_energy(),
        )):
            return True

        # Always use very small claims
        if expense.amount_claimed < 3:
            return True

        # Check expense is a per unit cost (Overnight stay or transport mileage)
        exp_type = expense.expense_type.upper()
        price_per_unit = expense.price_per_unit()
        if (expense.is_transport_expense() or expense.is_overnight_expense()) and price_per_unit is not None:
            if exp_type not in travel_thresholds or price_per_unit >= travel_thresholds[exp_type]:
                return True
            return False

        # Check expense 'group' and if amount is above group threshold value
        group = expense.group()
        if group not in group_thresholds or expense.amount_claimed >= group_thresholds[group]:
            return True
        
    except Exception as e:
        print(f"ERROR '{e}' when filtering expense {expense}.")
        pp(expense._data)

    return False
