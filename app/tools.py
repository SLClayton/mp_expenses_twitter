from decimal import Decimal
from json import encoder
import os
import json
import random
from datetime import datetime, date, timedelta


def pp(d):
    print(json.dumps(d, indent=2, default=str, ensure_ascii=False))


def save_json(d, file_path="output.json", indent=2, compact=False, encoding="utf-8"):
    if compact:
        seperators = (",", ":")
        indent = None
    else:
        seperators = (", ", ": ")
    with open(file_path, "w", encoding=encoding) as f:
        json.dump(d, f, indent=indent, ensure_ascii=False, separators=seperators, default=str)


def load_json(file_path) -> dict:
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_text(text, file_path="output.txt"):
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(text)


def load_text(file_path, encoding="utf-8") -> str:
    with open(file_path, "r", encoding=encoding) as f:
        return f.read()


def load_list(filename) -> list:
    list = []
    with open(filename, "r") as file:
        for line in file:
            list.append(line.strip())
    return list


def save_list(list, filename):
    with open(filename, "w") as f:
        for item in list:
            f.write(str(item) + "\n")


def money_string(money: Decimal) -> str:
    prefix = "-" if money < Decimal(0) else ""
    return "{}£{:,.2f}".format(prefix, abs(money))


def shard(input_list, max_shard_size):
    shards = []
    i = 0
    while i < len(input_list):
        shards.append(input_list[i:i+max_shard_size])
        i += max_shard_size
    return shards


def shard_n(input_list, n_shards):
    shards = []
    for i in range(n_shards):
        shards.append([])

    shard_index = 0
    for input in input_list:
        shards[shard_index].append(input)

        if (shard_index == len(shards) - 1):
            shard_index = 0
        else:
            shard_index += 1

    return shards


def getAllFilenames(dir):
    return [f for f in os.listdir(dir) if os.path.isfile(os.path.join(dir, f))]


def getAllFilepaths(dir):
    filepaths = []
    for filename in os.listdir(dir):
        filepath = os.path.join(dir, filename)
        if os.path.isfile(filepath):
            filepaths.append(filepath)

    return filepaths


def rndstring(n):
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return "".join(random.choice(alphabet) for i in range(n))


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


def split_text(text, char_limit):
    if text == "":
        return [""]
    parts = []
    while len(text) > 0:
        if len(text) <= char_limit:
            if len(parts) > 0:
                parts.append("…" + text)
            else:
                parts.append(text)
            text = ""
        else:
            if len(parts) > 0:
                i = char_limit - 2
                parts.append("…" + text[:i] + "…")
            else:
                i = char_limit - 1
                parts.append(text[:i] + "…")
            text = text[i:]
    return parts


def parse_date(date_string):
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(date_string, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"no valid date format found for string '{date_string}'")


def in_aws():
    return os.environ.get("AWS_EXECUTION_ENV") is not None