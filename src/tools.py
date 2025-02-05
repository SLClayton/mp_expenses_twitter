from decimal import Decimal, InvalidOperation
import os
import json
import random
from datetime import datetime, date
from typing import Dict, Any, List, Optional


def pp(d: dict) -> None:
    print(json.dumps(d, indent=2, default=str, ensure_ascii=False))


def save_json(
    d,
    file_path: str = "output.json",
    indent: int = 2,
    sort: bool = False,
    encoding: str = "utf-8",
) -> None:
    with open(file_path, "w", encoding=encoding) as f:
        json.dump(
            d, f, indent=indent, ensure_ascii=False, sort_keys=sort, default=str
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


def get_year_codes() -> List[str]:
    this_year = datetime.utcnow().year
    next_next_year = this_year + 2
    next_year = this_year + 1
    last_year = this_year - 1
    last_last_year = this_year - 2

    return [
        "{}_{}".format(str(next_year)[-2:], str(next_next_year)[-2:]),
        "{}_{}".format(str(this_year)[-2:], str(next_year)[-2:]),
        "{}_{}".format(str(last_year)[-2:], str(this_year)[-2:]),
        "{}_{}".format(str(last_last_year)[-2:], str(last_year)[-2:]),
    ]


def get_year_codes_range(from_year: int, to_year: int) -> List[str]:
    return [
        "{}_{}".format(str(year)[-2:], str(year + 1)[-2:])
        for year in range(from_year, to_year)
    ]

def positive_decimal_or_none(input: Any) -> Optional[Decimal]:
    try:
        d_val = Decimal(str(input))
        if d_val > 0:
            return d_val
    except (InvalidOperation, ValueError, TypeError):
        pass
    return None

