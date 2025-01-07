import os
from datetime import datetime

import requests

from db import membersdb
from models import Member
from otypes import MemberType

inter_communication_secret = os.getenv("INTER_COMMUNICATION_SECRET")


def non_deleted_members(member_input) -> MemberType:
    """
    Function to return non-deleted members for a particular cid, uid
    Only to be used in admin functions,
    as it returns both approved/non-approved members.
    """
    updated_sample = membersdb.find_one(
        {
            "$and": [
                {"cid": member_input["cid"]},
                {"uid": member_input["uid"]},
            ]
        },
        {"_id": 0},
    )
    if updated_sample is None:
        raise Exception("No such Record")

    roles = []
    for i in updated_sample["roles"]:
        if i["deleted"] is True:
            continue
        roles.append(i)
    updated_sample["roles"] = roles

    return MemberType.from_pydantic(Member.model_validate(updated_sample))


def unique_roles_id(uid, cid):
    """
    Function to give unique ids for each of the role in roles list
    """
    pipeline = [
        {
            "$set": {
                "roles": {
                    "$map": {
                        "input": {"$range": [0, {"$size": "$roles"}]},
                        "in": {
                            "$mergeObjects": [
                                {"$arrayElemAt": ["$roles", "$$this"]},
                                {
                                    "rid": {
                                        "$toString": {
                                            "$add": [
                                                {"$toLong": datetime.now()},
                                                "$$this",
                                            ]
                                        }
                                    }
                                },
                            ]
                        },
                    }
                }
            }
        }
    ]
    membersdb.update_one(
        {
            "$and": [
                {"cid": cid},
                {"uid": uid},
            ]
        },
        pipeline,
    )


def getUser(uid, cookies=None):
    """
    Function to get a particular user details
    """
    try:
        query = """
            query GetUserProfile($userInput: UserInput!) {
                userProfile(userInput: $userInput) {
                    firstName
                    lastName
                    email
                    rollno
                    batch
                }
            }
        """
        variable = {"userInput": {"uid": uid}}
        if cookies:
            request = requests.post(
                "http://gateway/graphql",
                json={"query": query, "variables": variable},
                cookies=cookies,
            )
        else:
            request = requests.post(
                "http://gateway/graphql",
                json={"query": query, "variables": variable},
            )

        return request.json()["data"]["userProfile"]
    except Exception:
        return None


# get club name from club id
def getClubDetails(
    clubid: str,
    cookies,
) -> dict:
    try:
        query = """
                    query Club($clubInput: SimpleClubInput!) {
                        club(clubInput: $clubInput) {
                            cid
                            name
                            email
                            category
                        }
                    }
                """
        variable = {"clubInput": {"cid": clubid}}
        request = requests.post(
            "http://gateway/graphql",
            json={"query": query, "variables": variable},
            cookies=cookies,
        )
        return request.json()["data"]["club"]
    except Exception:
        return {}


def getClubs(cookies=None):
    """
    Function to call the all clubs query
    """
    try:
        query = """
                    query AllClubs {
                        allClubs {
                            cid
                            name
                            code
                            email
                        }
                    }
                """
        if cookies:
            request = requests.post(
                "http://gateway/graphql",
                json={"query": query},
                cookies=cookies,
            )
        else:
            request = requests.post("http://gateway/graphql", json={"query": query})
        return request.json()["data"]["allClubs"]
    except Exception:
        return []
