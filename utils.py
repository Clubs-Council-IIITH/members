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
