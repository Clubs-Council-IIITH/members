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
        (MemberType): Contains the details of the member.

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
        (dict | None): The details of the user.
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


def getUsersByList(uids: list, cookies=None) -> dict | None:
    """
    Query to Users Microservice to get user details in bulk,
    returns a dict with keys of user uids
    and value of user details

    Args:
        uids (list): list of uids of the users
        cookies (dict): The cookies of the user. Defaults to None.

    Returns:
        (dict | None): keys of user uids and value of user details
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


def getUsersByBatch(
    batch: int, ug: bool = True, pg: bool = True, cookies=None
) -> dict | None:
    """
    Query to Users Microservice to get all
    users belonging to a particular batch

    Args:
        batch (int): batch year of the users
        cookies (dict): The cookies of the user. Defaults to None.

    Returns:
        (dict | None): keys of user uids and value of user details
    """
    try:
        batchDetails = dict()
        query = """
            query GetUsersByBatch($batchYear: Int!, $ug: Boolean, $pg: Boolean) {
                usersByBatch(batchYear: $batchYear, ug: $ug, pg: $pg) {
                    uid
                    firstName
                    lastName
                    rollno
                    batch
                    email
                }
            }
        """  # noqa: E501
        variable = {"batchYear": batch, "ug": ug, "pg": pg}
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
) -> dict | None:
    """
    Query to Clubs Microservice to get club details from club id

    Args:
        clubid (str): club id
        cookies (dict): The cookies of the user. Defaults to None.

    Returns:
        (dict | None): the club details
    """

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


def getClubs(cookies=None) -> dict | None:
    """
    Query to Clubs Microservice to call the all clubs query

    Args:
        cookies (dict): The cookies of the user. Defaults to None.

    Returns:
        (dict | None): list of all clubs
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
            request = requests.post(
                "http://gateway/graphql", json={"query": query}
            )
        return request.json()["data"]["allClubs"]
    except Exception:
        return []
