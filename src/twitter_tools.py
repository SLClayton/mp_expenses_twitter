import tweepy

from aws_tools import *


TWITTER_KEYS = get_secret_dict(os.getenv("MPE_TWITTER_SECRET_NAME"))


class TwitterClient():

    def __init__(self):
        self.client = tweepy.Client(
            bearer_token=TWITTER_KEYS["BEARER_TOKEN"],
            consumer_key=TWITTER_KEYS["API_KEY"],
            consumer_secret=TWITTER_KEYS["API_KEY_SECRET"],
            access_token=TWITTER_KEYS["ACCESS_TOKEN"],
            access_token_secret=TWITTER_KEYS["ACCESS_TOKEN_SECRET"]
        )

    def tweet(self, text: str) -> dict:
        try:
            tweet_response = self.client.create_tweet(text=text)
        except tweepy.TweepyException as e:
            print("Error during tweeting:", e)
            return None
        print("Tweet posted successfully!")
        return tweet_response.data
