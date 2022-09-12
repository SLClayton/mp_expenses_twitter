from re import A
import pytwitter

from aws_tools import *
from vals import TWITTER_CREDENTIALS_SECRET_ARN

MAX_TWEET_LENGTH = 280
_TWITTER_CLIENT = None


def get_twitter_client() -> pytwitter.Api:
    global _TWITTER_CLIENT
    if _TWITTER_CLIENT is None:
        print(f"Logging into twitter with credentials from {TWITTER_CREDENTIALS_SECRET_ARN}")
        credentials = get_secret(TWITTER_CREDENTIALS_SECRET_ARN)
        _TWITTER_CLIENT = pytwitter.Api(
            consumer_key=credentials["CONSUMER_KEY"],
            consumer_secret=credentials["CONSUMER_SECRET"],
            access_token=credentials["TOKEN_KEY"],
            access_secret=credentials["TOKEN_SECRET"]
            )
    return _TWITTER_CLIENT



def tweet(text):

    client = get_twitter_client()
    tweet_text_parts = split_text(text, MAX_TWEET_LENGTH-2)

    prev_id = None
    main_tweet = None
    for i, tweet_text_part in enumerate(tweet_text_parts):
        
        print(f"Attempting to tweet part {i+1} of {len(tweet_text_parts)}: {tweet_text_part}")
        tweet = client.create_tweet(
            text=tweet_text_part, 
            reply_in_reply_to_tweet_id=prev_id,
            reply_exclude_reply_user_ids=None if prev_id is None else [])

        print(f"Tweeted: {tweet}")
        prev_id = tweet.id
        if main_tweet is None:
            main_tweet = tweet
    return main_tweet
