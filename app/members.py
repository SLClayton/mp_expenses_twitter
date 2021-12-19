import requests
import json
import time

from tools import *

global members
members_cache = {}

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

    def display_name(self):
        return "{} ({})".format(remove_title(self.name), self.party_abbr)


def get_member_data(member_id):

    url = "https://members-api.parliament.uk/api/Members/{}".format(member_id)

    retrys = 0
    while True:
        print("Requesting member data for id {}.".format(member_id))
        resp = requests.get(url)
        if resp.status_code != 200:
            retrys += 1
            print("Error code {} while getting member id {} information.".format(resp.status_code, member_id))
            if retrys < 5:
                print("Trying again.")
                time.sleep(3)
                continue
            print("Max retries done, returning None.")
            return None

        data = json.loads(resp.text)["value"]
        break

    return data


def get_member(member_id):
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


def remove_title(name):
    titles = ["sir", "mr", "mrs", "ms"]
    words = name.split()
    first = words[0]
    if first.lower() in titles:
        words.pop(0)
    return " ".join(words)