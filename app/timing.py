
from datetime import timedelta, date, datetime
from time import time

from tools import *
from vals import *


def positional_weekday(year, month, weekday, positional):
    d = date(year, month, 1)
    while d.month == month:
        if d.isoweekday() == weekday:
            if positional == 1:
                return d
            else:
                positional -= 1
                d += timedelta(days=7)
        else:
            days_to_add = weekday - d.isoweekday()
            if days_to_add < 0:
                days_to_add += 7
            d += timedelta(days=days_to_add)
    return None


def get_publication_dates(start_date, end_date):
    pub_dates = []
    for year in range(start_date.year, end_date.year+1):
        pub_dates += [
            positional_weekday(year, 1, 4, 3),  # 3rd Thurs of Jan
            positional_weekday(year, 3, 4, 2),  # 2nd Thurs of March
            positional_weekday(year, 5, 4, 2),  # 2nd Thurs of May
            positional_weekday(year, 7, 4, 2),  # 2nd Thurs of July
            positional_weekday(year, 9, 4, 2),  # 2nd Thurs of Sept
            positional_weekday(year, 11, 4, 3)  # 3rd Thurs of Nov
        ]
    pub_dates = [d for d in pub_dates if start_date < d <= end_date]
    return pub_dates


def get_next_publication_date() -> date:
    today = datetime.today().date()
    much_later = (today + timedelta(days=365))
    pub_dates = get_publication_dates(
        start_date=today,
        end_date=much_later
    )
    pub_dates.sort()
    for date in pub_dates:
        if date != today:
            return date
    raise Exception(f"NO NEXT PUBLISH DATE FOUND FROM: {pub_dates}")


def secs_left_today() -> int:
    now = datetime.now()
    start_time = datetime.combine(date.today(), TWEET_START_TIME)
    end_time = datetime.combine(date.today(), TWEET_END_TIME)
    if now < start_time:
        return int((end_time - start_time).total_seconds())
    elif now > end_time:
        return 0
    else:
        return int((end_time - now).total_seconds())
    

def mins_until_next_publication() -> float:
    next_pub = get_next_publication_date()
    tomorrow = datetime.today().date() + timedelta(days=1)
    start_time = datetime.combine(date.today(), TWEET_START_TIME)
    end_time = datetime.combine(date.today(), TWEET_END_TIME)
    secs_per_day = int((end_time - start_time).total_seconds())

    full_days_until = (next_pub - tomorrow).days
    total_seconds = secs_left_today() + (full_days_until * secs_per_day)
    minutes = total_seconds / 60
    return minutes


def hours_until_next_publication() -> float:
    return mins_until_next_publication() / 60
