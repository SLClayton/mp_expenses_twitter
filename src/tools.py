from decimal import Decimal
import os
import json
import random
from datetime import datetime, date
from typing import Dict, Any, List


def pp(d: dict) -> None:
    print(json.dumps(d, indent=2, default=str, ensure_ascii=False))


def save_json(
    d,
    file_path: str = "output.json",
    indent: int = 2,
    compact: bool = False,
    encoding: str = "utf-8",
) -> None:
    if compact:
        seperators = (",", ":")
        indent = None
    else:
        seperators = (", ", ": ")
    with open(file_path, "w", encoding=encoding) as f:
        json.dump(
            d, f, indent=indent, ensure_ascii=False, separators=seperators, default=str
        )


def load_json(file_path: str) -> Dict[str, Any]:
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_text(text: str, file_path: str = "output.txt") -> None:
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(text)


def load_text(file_path: str, encoding: str = "utf-8") -> str:
    with open(file_path, "r", encoding=encoding) as f:
        return f.read()


def load_list(filename: str) -> List[str]:
    list = []
    with open(filename, "r") as file:
        for line in file:
            list.append(line.strip())
    return list


def save_list(list: List[Any], filename: str) -> None:
    with open(filename, "w") as f:
        for item in list:
            f.write(str(item) + "\n")


def money_string(money: Decimal) -> str:
    prefix = "-" if money < Decimal(0) else ""
    return "{}£{:,.2f}".format(prefix, abs(money))


def shard(input_list: List[Any], max_shard_size: int) -> List[List[Any]]:
    shards = []
    i = 0
    while i < len(input_list):
        shards.append(input_list[i : i + max_shard_size])
        i += max_shard_size
    return shards


def shard_n(input_list: List[Any], n_shards: int) -> List[List[Any]]:
    shards = []
    for i in range(n_shards):
        shards.append([])

    shard_index = 0
    for input in input_list:
        shards[shard_index].append(input)

        if shard_index == len(shards) - 1:
            shard_index = 0
        else:
            shard_index += 1

    return shards


def rndstring(n: int) -> str:
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return "".join(random.choice(alphabet) for i in range(n))


def parse_date(date_string: str) -> date:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(date_string, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"no valid date format found for string '{date_string}'")
