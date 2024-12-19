import csv
import io
from typing import List

import strawberry
from fastapi.encoders import jsonable_encoder

from db import membersdb
from models import Member
from utils import getClubDetails, getUser

# import all models and types
from otypes import Info, MemberType, SimpleClubInput, SimpleMemberInput, MemberInputDataReportDetails, MemberCSVResponse

"""
Member Queries
"""


@strawberry.field
def member(memberInput: SimpleMemberInput, info: Info) -> MemberType:
    """
    Description:
        Returns member details for a specific club
    Scope: CC & Specific Club
    Return Type: MemberType
    Input: SimpleMemberInput (cid, uid)
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
    Description:
        Returns member roles from each club
    Scope: CC & Specific Club
    Return Type: uid (str)
    Input: SimpleMemberInput (cid, uid, roles)
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
    Description:
        For CC:
            Returns all the non-deleted members.
        For Specific Club:
            Returns all the non-deleted members of that club.
        For Public:
            Returns all the non-deleted and approved members.
    Scope: CC + Club (For All Members), Public (For Approved Members)
    Return Type: List[MemberType]
    Input: SimpleClubInput (cid)
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
    Description:
        For Everyone:
            Returns all the current non-deleted and approved members of the given clubid.

    Scope: Anyone (Non-Admin Function)
    Return Type: List[MemberType]
    Input: SimpleClubInput (cid)
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
    Description: Returns all the non-deleted and non-approved members.
    Scope: CC
    Return Type: List[MemberType]
    Input: None
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

@strawberry.field
def downloadMembersData(details: MemberInputDataReportDetails, info: Info) -> MemberCSVResponse:
    user = info.context.user
    if user is None:
        raise Exception("You do not have permission to access this resource.")

    results = membersdb.find({"cid": details.clubid}, {"_id": 0})

    allMembers = []
    for result in results:
        roles = result["roles"]
        roles_result = []

        for i in roles:
            if i["deleted"] is True:
                continue
            roles_result.append(i)

        if len(roles_result) > 0:
            result["roles"] = roles_result
            allMembers.append(
                result
            )

    headerMapping = {"clubid": "Club Name", "uid": "Name", "poc": "Is POC", "roles": "Roles"}

    # Prepare CSV content
    csvOutput = io.StringIO()
    fieldnames = [
        headerMapping.get(field.lower(), field)
        for field in details.fields
    ]
    csv_writer = csv.DictWriter(csvOutput, fieldnames=fieldnames)
    csv_writer.writeheader()
    clubName = getClubDetails(details.clubid, info.context.cookies)["name"]

    for member in allMembers:
        memberData = {}
        for field in details.fields:
            value = ""
            mappedField = headerMapping.get(field.lower())
            if field == "clubid":
                value = clubName
            elif field == "uid":
                userDetails = getUser(member[field], info.context.cookies)
                value = userDetails["firstName"] + " " +userDetails["lastName"]
            elif field == "roles":
                listOfRoles = []
                for i in member[field]:
                    roleFormatting = [i["name"], i["start_year"], i["end_year"]]
                    listOfRoles.append(roleFormatting)
                value = str(listOfRoles)
            else:
                value = member[field]
            memberData[mappedField] = value
        csv_writer.writerow(memberData)

    csv_content = csvOutput.getvalue()
    csvOutput.close()

    return MemberCSVResponse(
        csvFile=csv_content,
        successMessage="CSV file generated successfully",
        errorMessage="",
    )

# register all queries
queries = [
    member,
    memberRoles,
    members,
    currentMembers,
    pendingMembers,
    downloadMembersData,
]
