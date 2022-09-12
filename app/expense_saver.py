from datetime import datetime, date
from operator import attrgetter

from expenses import *
from members import get_members_of_note_ids
from timing import *

MIN_DATE_LIMIT = date(2021, 12, 1)
MAX_DATE_LIMIT = date(2022, 6, 1)

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
    if expense.date > date.today():
        return False
    
    # Basic filter
    if (str(expense.claim_number) == "1" or expense.amount_claimed <= 0):
        return False
    
    # Ignore rail booking fees
    if expense.is_rail_booking_fee() and expense.amount_claimed <= 5:
        return False

    # First class handled by other bot
    if expense.is_first_class():
        return False

    # If a popular MP, use their expense regardless
    member_of_note_ids = get_members_of_note_ids()
    if expense.member_id in member_of_note_ids:
        return True

    # Always use certain expense types
    if any((
        expense.is_air_travel(),
        expense.is_taxi_ride(),
        expense.is_energy())):
            return True

    # Always use very small claims
    if expense.amount_claimed < 3:
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


def get_new_expenses(force=False, save=False):

    # Get all expenses from surrounding years
    print("Getting new expenses.")
    year_codes = get_year_codes()
    all_expenses = get_mulityear_expenses(year_codes, force=force)
    print(f"Found {exp_list_str(all_expenses)} for year codes {year_codes}.")

    # Get the previous claim numbers already tweeted
    prev_claim_numbers = get_previous_claim_numbers()
    print(f"Found {len(prev_claim_numbers)} previous claim numbers.")

    # Filter expenses
    filtered_expenses = list(filter(expense_filter, all_expenses))
    perc = (len(filtered_expenses) / len(all_expenses)) * 100
    print(f"Found {exp_list_str(filtered_expenses)} expenses that pass filter ({perc:.1f}%).")

    new_expenses = [e for e in filtered_expenses if 
        e.claim_number not in prev_claim_numbers and 
        e.date >= MIN_DATE_LIMIT and
        (MAX_DATE_LIMIT is None or e.date <= MAX_DATE_LIMIT)]

    tweets_ph = len(new_expenses) / hours_until_next_publication()
    print(f"Found {exp_list_str(new_expenses)} that aren't in prev claim list and pass filter. "
          f"Thats {tweets_ph:.1f} tweets per hour until {get_next_publication_date()}.")

    if save:
        assert PROJECT_CODE == "MPE"
        save_expense_queue(new_expenses)

if __name__ == "__main__":
    get_new_expenses(force=False, save=True)
