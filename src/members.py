import requests
import json
import time
from typing import List, Union, Dict, Any

from tools import *

global members
members_cache = {}

_MEMBERS_OF_NOTE_IDS = None
VIP_MEMBERS_FILE = "vip_members.json"


class Member:

    def __init__(self, data):
        self.data = data

        self.id = data["id"]
        self.name = remove_title(data["nameDisplayAs"])
        self.party = data["latestParty"]["name"]
        self.party_abbr = data["latestParty"]["abbreviation"]

    def __repr__(self):
        return f"<Member {self.id}: {self.name} ({self.party_abbr}) current-mp={self.current_mp}>"

    @property
    def display_name(self) -> str:
        return "{} ({})".format(self.name, self.party_abbr)

    @property
    def current_mp(self) -> bool:
        if self.data["latestHouseMembership"]["membershipStatus"] is None:
            return False
        return self.data["latestHouseMembership"]["membershipStatus"]["statusIsActive"]


def get_api_json(url, params=None) -> Dict[str, Any]:
    if params is None:
        params = {}

    retrys = 0
    while True:
        print(f"Trying to retrieve data from url: {url}")
        resp = requests.get(url, params=params)

        if resp.status_code != 200:
            retrys += 1
            print(
                f"Error code {resp.status_code} while getting hitting url {url} information."
            )
            if retrys < 5:
                print("Trying again.")
                time.sleep(3)
                continue
            print("Max retries done, returning None.")
            return None
        break

    try:
        data = json.loads(resp.text)
    except Exception as e:
        print(resp.text)
        raise e

    return data


def get_member_data(member_id) -> dict:
    url = "https://members-api.parliament.uk/api/Members/{}".format(member_id)
    print("Requesting member data for id {}.".format(member_id))
    return get_api_json(url)["value"]


def get_member(member_id: int) -> Member:
    try:
        member = members_cache[member_id]
        print("Found member in cache")
    except KeyError:
        member_data = get_member_data(member_id)
        if member_data is None:
            return None
        member = Member(member_data)
        members_cache[member_id] = member
        print("Got member online")
    return member


def search_member(name: str) -> Optional[Member]:
    print(f"Searching for member with name '{name}'.")
    url = "https://members-api.parliament.uk/api/Members/Search"
    api_return = get_api_json(url, {"Name": name})
    members = [Member(item["value"]) for item in api_return["items"]]

    if len(members) == 1:
        print(f"Found matching member {members[0]}")
        return members[0]
    if len(members) > 1:
        print(f"Found {len(members)} members matching the name '{name}'.\n{members}")
    return None


def remove_title(name) -> str:
    titles = ["sir", "mr", "mrs", "ms", "dr"]
    words = name.split()
    first = words[0]
    if first.lower() in titles:
        words.pop(0)
    return " ".join(words)


def is_member_of_note(member: Union[int, str, Member]) -> bool:
    member_id = member.id if isinstance(member, Member) else str(member)
    global _MEMBERS_OF_NOTE_IDS
    if _MEMBERS_OF_NOTE_IDS is None:
        _MEMBERS_OF_NOTE_IDS = set(load_json(VIP_MEMBERS_FILE).values())
    return member_id in _MEMBERS_OF_NOTE_IDS


def update_vip_members_list(names: List[str]):
    current_vip_members = load_json(VIP_MEMBERS_FILE)
    all_names = list(current_vip_members.keys()) + names

    new_vip_members = {}
    for name in all_names:
        member = search_member(name)
        if member:
            new_vip_members[member.name] = member.id

    save_json(new_vip_members, VIP_MEMBERS_FILE, sort=True)
