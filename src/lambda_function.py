from datetime import datetime, time, timedelta
import random
from zoneinfo import ZoneInfo

from expenses import exp_list_str
from expense_importer import get_expenses_since_year
from expense_filter import expenses_filter
from twitter_tools import TwitterClient
from aws_tools import save_item_to_db, item_in_db
from tools import pp


TWEET_START_TIME = time(6, 55, 0)
TWEET_END_TIME = time(21, 5, 0)


def lambda_handler(event, context):
    force = event.get("force") is True

    # Ensure it is within tweeting time
    now = datetime.now(ZoneInfo("Europe/London"))
    if not force and not (TWEET_START_TIME <= now.time() <= TWEET_END_TIME):
        message = f"{now.time()} Not within tweeting time of {TWEET_START_TIME}-{TWEET_END_TIME}"
        print(message)
        return {"statusCode": 200, "tweet_id": None, "message": message}

    # Get all expenses from last few spreadsheet years
    expenses = get_expenses_since_year(now.year - 2)
    print(f"Found {exp_list_str(expenses)}")

    # Filter
    min_date = (now - timedelta(weeks=52)).date()
    max_date = (now - timedelta(weeks=8)).date()
    expenses = [e for e in expenses_filter(expenses) if max_date >= e.date >= min_date]
    print(f"Found {exp_list_str(expenses)} after filters.")

    # Choose randomly from remaining
    while True:
        expense = random.choice(expenses)
        print(f"Checking if expense {expense.claim_number} has already been used.")
        if not item_in_db(expense.claim_number):
            break

    # Tweet the expense
    print(f"Chosen expense {expense}")
    tweet_text = expense.claim_text()
    print(f"Tweeting: {tweet_text}")
    try:
        twitter = TwitterClient()
        tweet = twitter.tweet(tweet_text)
    except Exception as e:
        msg = "Error while tweeting: {e}"
        print(msg)
        e.with_traceback()
        return {"statusCode": 500, "error": msg}

    # Save to DB
    item = {
        "expense_id": expense.claim_number,
        "tweet_id": tweet["id"] if tweet else None,
        "when_created": datetime.utcnow().isoformat(),
    }
    if tweet is None:
        print("Tweet came back NULL.")
    else:
        save_item_to_db(item)
        print("tweet saved to db!")

    return {
        "statusCode": 200,
        "data": item,
    }


if __name__ == "__main__":
    pp(lambda_handler({"force": True}, None))
