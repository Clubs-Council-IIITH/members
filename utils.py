import os
from datetime import datetime

import requests

from db import membersdb
from models import Member
from otypes import MemberType

inter_communication_secret = os.getenv("INTER_COMMUNICATION_SECRET")


def non_deleted_members(member_input) -> MemberType:
    """
    Returns the non-deleted member

    Function to return a non-deleted member for a particular cid, uid
    Only to be used in admin functions,
    as it returns both approved/non-approved members.

    Inputs:
        member_input (dict): Contains the cid and uid of the member.

    Returns:
        MemberType: Contains the details of the member.

    Raises Exception:
        No such Record: If the member with the given uid, cid is not found in the database.
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

    This method makes a query to the user-service to get the details of a particular user.
    It is used to get the details of a user.
    It is resolved by the userProfile resolver. 

    Inputs:
        uid (str): The uid of the user.
        cookies (dict): The cookies of the user.

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
