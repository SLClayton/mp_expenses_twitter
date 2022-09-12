from datetime import date

from expenses import *
from tools import *
from aws_tools import *
from vals import *
from timing import *

MIN_DATE = date(2021, 12, 1)
MAX_DATE = date.today()


def save_expenses(force=False, save=False):

    this_year = date.today().year
    year_codes = get_year_codes_range(this_year - 2, this_year + 2)
    all_expenses = get_mulityear_expenses(year_codes, force)

    expenses = [e for e in all_expenses if e.is_first_class() and e.amount_claimed > 1]
    print(f"Found {len(expenses)} 'First Class' expenses using year codes {year_codes}")

    expenses = [e for e in expenses if MIN_DATE <= e.date <= MAX_DATE]
    print(f"Found {len(expenses)} of those expenses between {MIN_DATE} - {MAX_DATE}")

    prev_claim_numbers = get_previous_claim_numbers()
    new_expenses = [e for e in expenses if e.claim_number not in prev_claim_numbers]

    tweets_ph = len(new_expenses) / hours_until_next_publication()
    print(f"Found {exp_list_str(new_expenses)} that aren't in prev claim list and pass filter. "
          f"Thats {tweets_ph:.1f} tweets per hour until {get_next_publication_date()}.")

    if save:
        assert PROJECT_CODE == "FCMPS"
        save_expense_queue(expenses)

    
def get_previous_claim_numbers() -> set:
    prev_claim_numbers = get_list_from_s3(S3_BUCKET, S3_PREV_CLAIM_NUMBERS_KEY)
    return set() if prev_claim_numbers is None else set(prev_claim_numbers)


if __name__ == "__main__":
    save_expenses(force=True, save=True)
