import requests
from datetime import datetime
import os

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

    return MemberType.from_pydantic(Member.parse_obj(updated_sample))


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
                "http://gateway/graphql", json={"query": query, "variables": variable}
            )

        return request.json()["data"]["userProfile"]
    except Exception:
        return None
