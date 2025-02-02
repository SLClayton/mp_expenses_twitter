import requests
import json
import time
from typing import List, Union, Dict, Any

from tools import *

global members
members_cache = {}

_MEMBERS_OF_NOTE_IDS = None

class Member:

    def __init__(self, data):
        self.data = data

        self.id = data["id"]
        self.name = data["nameDisplayAs"]
        self.party = data["latestParty"]["name"]
        self.party_abbr = data["latestParty"]["abbreviation"]

        self.current_mp = (
            False if data["latestHouseMembership"]["membershipStatus"] is None 
            else data["latestHouseMembership"]["membershipStatus"]["statusIsActive"]
        )

    def __repr__(self):
        return f"<Member {self.id}: {self.name} ({self.party_abbr}) current-mp={self.current_mp}>"

    def display_name(self) -> str:
        return "{} ({})".format(remove_title(self.name), self.party_abbr)


def get_api_json(url, params=None) -> Dict[str, Any]:
    if params is None:
        params = {}

    retrys = 0
    while True:
        print(f"Trying to retrieve data from url: {url}")
        resp = requests.get(url, params=params)

        if resp.status_code != 200:
            retrys += 1
            print(f"Error code {resp.status_code} while getting hitting url {url} information.")
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


def get_member(member_id) -> Member:
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


def search_members(name) -> List[Member]:
    print(f"Searching for member with name '{name}'.")
    url = "https://members-api.parliament.uk/api/Members/Search"
    api_return = get_api_json(url, {"Name": name})
    members = [Member(item["value"]) for item in api_return["items"]]
    print(f"Found {len(members)} members matching the name '{name}'.")
    return members


def map_member_ids(member_names: List[str]) -> Dict[str, int]:
    member_ids = {}
    for name in member_names:
        matching_members = search_members(name)
        if len(matching_members) == 1:
            member = matching_members[0]
            member_ids[member.name] = member.id
        else:
            print(f"Found {len(matching_members)} members that match the "
                  f"name '{name}'. {matching_members}")
            member_ids[name] = None
    
    return member_ids


def remove_title(name) -> str:
    titles = ["sir", "mr", "mrs", "ms"]
    words = name.split()
    first = words[0]
    if first.lower() in titles:
        words.pop(0)
    return " ".join(words)


def is_member_of_note(member: Union[int, str, Member]) -> bool:
    member_id = member.id if isinstance(member, Member) else str(member)
    global _MEMBERS_OF_NOTE_IDS
    if _MEMBERS_OF_NOTE_IDS is None:
        _MEMBERS_OF_NOTE_IDS = set(load_json("vip_members.json").values())
    return member_id in _MEMBERS_OF_NOTE_IDS
