import os
from datetime import datetime

import requests

from db import membersdb
from models import Member
from otypes import MemberType

inter_communication_secret = os.getenv("INTER_COMMUNICATION_SECRET")


def non_deleted_members(member_input) -> MemberType:
    """
    Returns a member with his non-deleted roles

    Args:
        member_input (dict): json serialised FullMemberInput.

    Returns:
        MemberType: Contains the details of the member.

    Raises:
        Exception: No such Record
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
    Generates unique role ids for a member's roles

    Args:
        uid (str): The uid of the user.
        cid (str): The cid of the club.
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


def getUser(uid, cookies=None) -> dict | None:
    """
    Query request to the Users microservice to fetch user details.

    Args:
        uid (str): The uid of the user.
        cookies (dict): The cookies of the user. Defaults to None.

    Returns:
        dict: The details of the user.
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
    

def getUsersByList(uids: list, cookies=None):
    """
    Function to get user details in bulk, returns a dict with keys of user uids
    and value of user details
    """
    userProfiles = {}

    try:
        query = """
            query usersByList($userInputs: [UserInput!]!) {
                usersByList(userInputs: $userInputs) {
                    firstName
                    lastName
                    email
                    rollno
                    batch
                }
            }
        """
        variable = {"userInputs": [{"uid": uid} for uid in uids]}
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

        for i in range(len(uids)):
            userProfiles[uids[i]] = request.json()["data"]["usersByList"][i]

        return userProfiles
    except Exception:
        return None

def getUsersByBatch(batch: int, cookies=None):
    """
    Function to get all users in a particular batch
    """
    try:
        batchDetails = dict()
        query = """
            query GetUsersByBatch($batchYear: Int!) {
                usersByBatch(batchYear: $batchYear) {
                    uid
                    firstName
                    lastName
                    rollno
                    batch
                    email
                }
            }
        """
        variable = {"batchYear": batch}
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

        for result in request.json()["data"]["usersByBatch"]:
            batchDetails[result["uid"]] = result
        
        return batchDetails
    except Exception:
        return dict()

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
