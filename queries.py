"""
Query resolvers
"""

from typing import List

import strawberry
from fastapi.encoders import jsonable_encoder

from db import membersdb
from models import Member

# import all models and types
from otypes import Info, MemberType, SimpleClubInput, SimpleMemberInput


@strawberry.field
def member(memberInput: SimpleMemberInput, info: Info) -> MemberType:
    """
    Fetches details of a club member using the cid and uid given,
    for club and CC

    Args:
        memberInput (SimpleMemberInput): Contains the cid and uid of the member.
        info (Info): Contains the logged in user's details.

    Returns:
        MemberType: Contains the details of the member.

    Raises:
        Exception: Not Authenticated
        Exception: Not Authenticated to access this API
        Exception: No such Record
    """

    user = info.context.user
    if user is None:
        raise Exception("Not Authenticated")

    uid = user["uid"]
    member_input = jsonable_encoder(memberInput)

    if (member_input["cid"] != uid or user["role"] != "club") and user[
        "role"
    ] != "cc":
        raise Exception("Not Authenticated to access this API")

    member = membersdb.find_one(
        {
            "$and": [
                {"cid": member_input["cid"]},
                {"uid": member_input["uid"]},
            ]
        },
        {"_id": 0},
    )
    if member is None:
        raise Exception("No such Record")

    return MemberType.from_pydantic(Member.model_validate(member))


@strawberry.field
def memberRoles(uid: str, info: Info) -> List[MemberType]:
    """
    Fetches a club memeber along with his roles

    A user can be part of many clubs and therefore have multiple roles, 
    each in a different club hence each in a different document.
    This method searches for documents belonging to the same user.
    It returns the user's non-deleted and approved roles details in all 
    clubs, for public.
    CC can also get unapproved roles.

    Args:
        uid (str): The uid of the user.
        info (Info): Contains the logged in user's details.

    Returns:
        List[MemberType]: Contains a list of member with their current roles.

    Raises:
        Exception: No Member Result/s Found
    """

    user = info.context.user
    if user is None:
        role = "public"
    else:
        role = user["role"]

    results = membersdb.find({"uid": uid}, {"_id": 0})

    if not results:
        raise Exception("No Member Result/s Found")

    members = []
    for result in results:
        roles = result["roles"]
        roles_result = []

        for i in roles:
            if i["deleted"] is True:
                continue
            if role != "cc":
                if i["approved"] is False:
                    continue
            roles_result.append(i)

        if len(roles_result) > 0:
            result["roles"] = roles_result
            members.append(
                MemberType.from_pydantic(Member.model_validate(result))
            )

    return members


@strawberry.field
def members(clubInput: SimpleClubInput, info: Info) -> List[MemberType]:
    """
    Returns all the members of a club.

    This method fetches all the members of a club.
    For CC and club, it returns all the members with their current 
    non-deleted, approved and pending roles.
    For public, it returns all the members with their current non-deleted 
    and approved roles.

    Args:
        clubInput (SimpleClubInput): Contains the cid of the club.
        info (Info): Contains the logged in user's details.

    Returns:
        List[MemberType]: Contains a list of members.

    Raises:
        Exception: No Member Result/s Found
    """

    user = info.context.user
    if user is None:
        role = "public"
    else:
        role = user["role"]

    club_input = jsonable_encoder(clubInput)

    if role not in ["cc"] or club_input["cid"] != "clubs":
        results = membersdb.find({"cid": club_input["cid"]}, {"_id": 0})
    else:
        results = membersdb.find({}, {"_id": 0})

    if results:
        members = []
        for result in results:
            roles = result["roles"]
            roles_result = []

            for i in roles:
                if i["deleted"] is True:
                    continue
                if not (
                    role in ["cc"]
                    or (role in ["club"] and user["uid"] == club_input["cid"])
                ):
                    if i["approved"] is False:
                        continue
                roles_result.append(i)

            if len(roles_result) > 0:
                result["roles"] = roles_result
                members.append(
                    MemberType.from_pydantic(Member.model_validate(result))
                )

        return members

    else:
        raise Exception("No Member Result/s Found")


@strawberry.field
def currentMembers(clubInput: SimpleClubInput, info: Info) -> List[MemberType]:
    """
    Returns the current members of a club with their non-deleted, 
    approved roles, for Public.

    Args:
        clubInput (SimpleClubInput): Contains the cid of the club.
        info (Info): Contains the logged in user's details.

    Returns:
        List[MemberType]: Contains a list of members.

    Raises:
        Exception: Not Authenticated
        Exception: No Member Result/s Found
    """  # noqa: E501

    user = info.context.user
    if user is None:
        role = "public"
    else:
        role = user["role"]

    club_input = jsonable_encoder(clubInput)

    if club_input["cid"] == "clubs":
        if role != "cc":
            raise Exception("Not Authenticated")

        results = membersdb.find({}, {"_id": 0})
    else:
        results = membersdb.find({"cid": club_input["cid"]}, {"_id": 0})

    if results:
        members = []
        for result in results:
            roles = result["roles"]
            roles_result = []

            for i in roles:
                if i["deleted"] is True or i["end_year"] is not None:
                    continue
                if i["approved"] is False:
                    continue
                roles_result.append(i)

            if len(roles_result) > 0:
                result["roles"] = roles_result
                members.append(
                    MemberType.from_pydantic(Member.model_validate(result))
                )

        return members
    else:
        raise Exception("No Member Result/s Found")


@strawberry.field
def pendingMembers(info: Info) -> List[MemberType]:
    """
    Returns the pending members of all clubs with their non-deleted, 
    pending roles for CC.

    Args:
        info (Info): Contains the logged in user's details.

    Returns:
        List[MemberType]: Contains a list of members.

    Raises:
        Exception: Not Authenticated
        Exception: No Member Result/s Found
    """

    user = info.context.user
    if user is None or user["role"] not in ["cc"]:
        raise Exception("Not Authenticated")

    results = membersdb.find({}, {"_id": 0})

    if results:
        members = []
        for result in results:
            roles = result["roles"]
            roles_result = []

            for i in roles:
                if i["deleted"] or i["approved"] or i["rejected"]:
                    continue
                roles_result.append(i)

            if len(roles_result) > 0:
                result["roles"] = roles_result
                members.append(
                    MemberType.from_pydantic(Member.model_validate(result))
                )

        return members
    else:
        raise Exception("No Member Result/s Found")


# register all queries
queries = [
    member,
    memberRoles,
    members,
    currentMembers,
    pendingMembers,
]
