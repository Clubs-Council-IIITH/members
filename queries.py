"""
Query resolvers

This file contains the query resolvers.

Resolvers:
    member: Returns the details of a member of a specific club.
    memberRoles: Returns the member with his current roles from all clubs.
    members: Returns the details of all the members of a specific club.
    currentMembers: Returns the details of all the current members of a specific club.
    pendingMembers: Returns the details of all the pending members.
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
    Details of a member of a specific club

    This method fetches the details of a member of a specific club.
    The member is searched in the database using the cid and uid of the member.

    Inputs:
        memberInput (SimpleMemberInput): Contains the cid and uid of the member.
        info (Info): Contains the logged in user's details.

    Returns:
        MemberType: Contains the details of the member.

    Accessibility:
        CC and club both have full access.

    Raises Exception:
        Not Authenticated/Not Authenticated to access this API: If the user is not authenticated.
        No such Record: If the member with the given uid, cid is not found in the database.
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
    Returns memeber along with his roles

    A user can be part of many clubs.
    And therefore have multiple roles, each in a different club.
    This method searches member documents having the given uid.
    It returns the member details in each club along with their current roles.

    Inputs:
        uid (str): The uid of the member.
        info (Info): Contains the logged in user's details.

    Returns:
        List[MemberType]: Contains a list of member with their current roles.

    Accessibility:
        Public

    Raises Exception:
        No Member Result/s Found: If no member is found with the given uid.
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

    This method fetches all the members of a specific club.
    For CC and the club, it returns all the members with their current non-deleted, approved and pending roles.
    For public, it returns all the members with their current non-deleted and approved roles.

    Inputs:
        clubInput (SimpleClubInput): Contains the cid of the club.
        info (Info): Contains the logged in user's details.

    Returns:
        List[MemberType]: Contains a list of members.

    Accessibility:
        CC and the same club both have full access.
        Public has partial access.

    Raises Exception:
        No Member Result/s Found: If no member is found with the given cid.
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
    Returns the current members of a club.

    Returns all the members with their current non-deleted and approved roles for the given clubid.

    Input:
        clubInput (SimpleClubInput): Contains the cid of the club.
        info (Info): Contains the logged in user's details.

    Returns:
        List[MemberType]: Contains a list of members.

    Accessibility:
        Public.

    Raises Exception:
        No Member Result/s Found: If no member is found with the given cid.
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
    Returns the pending members of all clubs.

    Returns all the members with their current non-deleted and pending roles from all clubs.

    Input:
        info (Info): Contains the logged in user's details.

    Returns:
        List[MemberType]: Contains a list of members.

    Accessibility:
        Only CC has access.

    Raises Exception:
        No Member Result/s Found: If no member is found.
    
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
