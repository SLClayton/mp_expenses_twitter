from datetime import date
from typing import List, Dict

from expenses import (
    Expense,
    generate_group_thresholds,
    generate_travel_thresholds,
)
from members import is_member_of_note
from tools import pp


def expenses_filter(expenses: List[Expense]) -> List[Expense]:
    travel_thresholds = generate_travel_thresholds(expenses, 5, 20)
    group_thresholds = generate_group_thresholds(expenses, 5, 20)
    return [
        e for e in expenses if expense_filter(e, travel_thresholds, group_thresholds)
    ]


def expense_filter(
    expense: Expense, travel_thresholds: Dict[str, float], group_thresholds: Dict[str, float]
) -> bool:
    try:
        # Not in the future
        if expense.date > date.today():
            return False

        # Removes weird data
        if str(expense.claim_number) == "1" or expense.amount_claimed <= 0:
            return False

        # Ignore rail booking fees
        if expense.is_rail_booking_fee and expense.amount_claimed <= 5:
            return False

        # First class (data not given anymore)
        if expense.is_first_class:
            return True

        # If a popular MP, use their expense regardless
        if is_member_of_note(expense.member_id):
            return True

        # Always use certain expense types
        if any(
            (
                expense.is_air_travel(),
                expense.is_taxi_ride(),
                #expense.is_energy(),
            )
        ):
            return True

        # Always use very small claims
        if expense.amount_claimed < 3:
            return True

        # If overnight stay or transport, check if price per unit is above threshold
        if expense.price_per_unit:
            return expense.price_per_unit > travel_thresholds.get(expense.expense_type, 99999)

        # Check expense 'group' and if amount is above group threshold value
        if expense.amount_claimed >= group_thresholds.get(expense.group, 99999):
            return True

    except Exception as e:
        print(f"ERROR '{e}' when filtering expense {expense}.")
        pp(expense._data)

    return False
