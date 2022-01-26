from operator import attrgetter
import traceback

from expenses import *
from timing import mins_until_next_publication
from vals import *
from twitter_tools import tweet
from tools import *

event_bridge = boto3.client("events")


def update_tweet_interval(interval_minutes):
    cron = f"cron(0/{interval_minutes} {TWEET_START_TIME.hour}-{TWEET_END_TIME.hour} ? * * *)"
    event_bridge.put_rule(Name= EVENTBRIDGE_EVENT_NAME, ScheduleExpression=cron)


def tweet_expense_from_queue():

    # Get expenses from queue and sort them by date
    expense_queue = get_expense_queue()
    expense_queue.sort(key=attrgetter("date"))
    prev_claim_numbers = get_previous_claim_numbers()

    tweet_failure_count = 0
    resulting_tweet = None
    while True:
        
        # Exit if no items left in queue
        if len(expense_queue) == 0:
            print("There are no items in the queue. Exiting.")
            break

        # Choose one of the oldest expenses in queue
        expense = expense_queue.pop(0)
        print(f"Next expense is {expense}.")

        # Check expense hasn't been tweeted before
        if expense.claim_number in prev_claim_numbers:
            print("Claim number was already in previous claim numbers.")
            continue
        
        # Try tweeting it. If an error occurs place in exception queue
        try:
            print("Attempting to tweet.")
            resulting_tweet = tweet(expense.claim_text())
            print(f"Tweet sent: {resulting_tweet}")
        except Exception as e:
            traceback.print_exc()
            print(f"Error while tweeting. Adding to exception queue.")
            add_to_exception_queue(expense)
            tweet_failure_count += 1
            if tweet_failure_count < 5:
                continue
            else:
                break

        break

    # Save claim number to history
    try:
        prev_claim_numbers.add(expense.claim_number)
        save_previous_claim_numbers(prev_claim_numbers)
    except Exception as e:
        print(f"Exception '{e}' while trying to save previous claim numbers.")
        traceback.print_exc()

    # Save queue
    try:
        save_expense_queue(expense_queue)
    except Exception as e:
        print(f"Exception '{e}' while trying to save expense queue.")
        traceback.print_exc()

    # Update new tweet interval so tweets are spaced out right
    try:
        new_tweet_interval = round(mins_until_next_publication() / len(expense_queue))
        new_tweet_interval = min(59, max(5, new_tweet_interval))
        update_tweet_interval(new_tweet_interval)
    except Exception as e:
        print(f"Exception '{e}' while trying to update tweet interval.")
        traceback.print_exc()

    return resulting_tweet, new_tweet_interval


def tweet_handler(event, context):
    try:
        tweet, update_interval = tweet_expense_from_queue()
    except Exception as e:
        traceback.print_exc()
        return {
            'statusCode': 500,
            'error': str(e)
        }
    return {
        'statusCode': 200,
        'tweet_id': str(tweet),
        "update_interval": update_interval
    }


if __name__ == "__main__":
    pp(tweet_handler(None, None))
