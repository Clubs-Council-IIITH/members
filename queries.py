"""
Query resolvers
"""

import csv
import io
from typing import List
import math
import strawberry
from fastapi.encoders import jsonable_encoder

from db import membersdb, certificatesdb
from models import Member, Certificate, CertificateStates

# import all models and types
from otypes import (
    Info,
    MemberCSVResponse,
    MemberInputDataReportDetails,
    MemberType,
    SimpleClubInput,
    SimpleMemberInput,
    CertificateType,
)
from utils import (
    getClubDetails,
    getClubs,
    getUsersByBatch,
    getUsersByList,
)


@strawberry.field
def member(memberInput: SimpleMemberInput, info: Info) -> MemberType:
    """
    Fetches details of a club member using the cid and uid given,
    for club and CC

    Args:
        memberInput (SimpleMemberInput): Contains the cid and
                                         uid of the member.
        info (Info): Contains the logged in user's details.

    Returns:
        (MemberType): Contains the details of the member.

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


def memberRolesHelper(uid: str, info: Info) -> List[MemberType]:
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
        (List[MemberType]): Contains a list of member with their current roles.

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
def memberRoles(uid: str, info: Info) -> List[MemberType]:
    return memberRolesHelper(uid, info)

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
        (List[MemberType]): Contains a list of members.

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
        (List[MemberType]): Contains a list of members.

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
                if i["deleted"] or i["end_year"] is not None:
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
        (List[MemberType]): Contains a list of members.

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


@strawberry.field
def getUserCertificates(info: Info) -> List[CertificateType]:
    user = info.context.user
    if user is None:
        raise Exception("Not Authenticated")

    certificates = certificatesdb.find({"user_id": user["uid"]})
    return [
        CertificateType.from_pydantic(Certificate.parse_obj(cert))
        for cert in certificates
    ]


@strawberry.field
def getPendingCertificates(info: Info) -> List[CertificateType]:
    """
    Description: Returns all pending certificates for CC and SLO roles.
    Scope: CC, SLO
    Return Type: List[CertificateType]
    Input: None
    """
    user = info.context.user
    if user is None:
        raise Exception("Not Authenticated")

    if user["role"] == "cc":
        pending_statuses = [CertificateStates.pending_cc.value]
    elif user["role"] == "slo":
        pending_statuses = [CertificateStates.pending_slo.value]
    else:
        raise Exception("You do not have permission to access this resource.")

    results = certificatesdb.find({"state": {"$in": pending_statuses}})

    if results:
        return [
            CertificateType.from_pydantic(Certificate.parse_obj(cert))
            for cert in results
        ]
    else:
        return []


@strawberry.field
def verifyCertificate(certificate_number: str, key: str) -> CertificateType:
    certificate = certificatesdb.find_one(
        {"certificate_number": certificate_number}
    )

    if not certificate:
        raise Exception("Certificate not found")

    if certificate["state"] == CertificateStates.rejected.value:
        raise Exception("Certificate has been rejected")

    if certificate["key"] != key:
        raise Exception("Wrong key provided")

    if certificate["state"] != CertificateStates.approved.value:
        raise Exception("Certificate approval is pending")

    return CertificateType.from_pydantic(Certificate.parse_obj(certificate))


@strawberry.field
def getCertificateByNumber(
    info: Info, certificate_number: str
) -> CertificateType:
    user = info.context.user
    if user is None:
        raise Exception("Not Authenticated")
    role = user["role"]

    certificate = certificatesdb.find_one(
        {"certificate_number": certificate_number}
    )
    if not certificate:
        raise Exception("Certificate not found")

    if (
        role not in ["cc", "slo"]
        and certificate["state"] != CertificateStates.approved.value
    ):
        raise Exception("You do not have permission to access this resource.")

    return CertificateType.from_pydantic(Certificate.parse_obj(certificate))


@strawberry.field
def getAllCertificates(
    info: Info
) -> List[CertificateType]:
    user = info.context.user
    if user is None:
        raise Exception("Not Authenticated")

    if user["role"] not in ["cc", "slo"]:
        raise Exception("You do not have permission to access this resource.")


    certificates = list(certificatesdb.find())    

    if certificates:
        return [
        CertificateType.from_pydantic(Certificate.parse_obj(cert))
        for cert in certificates
    ]
    else:
        return []

@strawberry.field
def downloadMembersData(
    details: MemberInputDataReportDetails, info: Info
) -> MemberCSVResponse:
    """
    It returns the data of all members specific to the
    requested fields like batch and status in a CSV format at once.

    Args:
        details (MemberInputDataReportDetails): Contains the
                                                details of the report.
        info (Info): Contains the logged in user's details.

    Returns:
        (MemberCSVResponse): Contains the data of all members specific to the
            requested fields like batch and status in a CSV format.

    Raises:
        Exception: You do not have permission to access this resource.
    """
    user = info.context.user
    if user is None:
        raise Exception("You do not have permission to access this resource.")

    if "allclubs" not in details.clubid:
        clubList = details.clubid
    else:
        allClubs = getClubs(info.context.cookies)
        clubList = [club["cid"] for club in allClubs]
        details.typeMembers = "current"

    results = membersdb.find({"cid": {"$in": clubList}}, {"_id": 0})

    allMembers = []
    if "allBatches" not in details.batchFiltering:
        batchDetails = dict()
        for batch in details.batchFiltering:
            batchDetails.update(
                getUsersByBatch(int(batch), info.context.cookies)
            )
    userDetailsList = dict()
    userIds = []
    for result in results:
        roles = result["roles"]
        roles_result = []
        currentMember = False
        withinTimeframe = False

        for i in roles:
            if i["deleted"] is True:
                continue
            if details.typeMembers == "current" and i["end_year"] is None:
                currentMember = True
            elif details.typeMembers == "past" and (
                (
                    details.dateRoles[1]
                    >= (2024 if i["end_year"] is None else int(i["end_year"]))
                    and details.dateRoles[0]
                    <= (2024 if i["end_year"] is None else int(i["end_year"]))
                )
                or (
                    details.dateRoles[1] >= int(i["start_year"])
                    and details.dateRoles[0] <= int(i["start_year"])
                )
            ):
                withinTimeframe = True

            roles_result.append(i)

        if len(roles_result) > 0:
            append = False
            result["roles"] = roles_result
            if details.typeMembers == "current" and currentMember:
                append = True
            elif details.typeMembers == "past" and withinTimeframe:
                append = True
            elif details.typeMembers == "all":
                append = True

            if "allBatches" not in details.batchFiltering and append:
                userDetails = batchDetails.get(result["uid"], None)
                if userDetails is not None:
                    userDetailsList[result["uid"]] = userDetails
                else:  # Member is not in specified batch
                    append = False

            if append:
                allMembers.append(result)
                userIds.append(result["uid"])

    # Get details of all members
    if "allBatches" in details.batchFiltering:
        userDetailsList = getUsersByList(userIds, info.context.cookies)

    headerMapping = {
        "clubid": "Club Name",
        "uid": "Name",
        "rollno": "Roll No",
        "batch": "Batch",
        "email": "Email",
        "partofclub": "Is Part of Club",
        "roles": "Roles [Role, Start Year, End Year]",
        "poc": "Is POC",
    }

    # Prepare CSV content
    csvOutput = io.StringIO()

    fieldnames = []
    for field in (
        headerMapping
    ):  # Add fields in the order specified in the headerMapping
        if field in details.fields:
            fieldnames.append(headerMapping.get(field.lower(), field))

    csv_writer = csv.DictWriter(csvOutput, fieldnames=fieldnames)
    csv_writer.writeheader()

    # So that we don't have to query the club name for each member
    clubNames = dict()

    for member in allMembers:
        memberData = {}
        userDetails = userDetailsList.get(member["uid"])
        if userDetails is None:
            continue
        if clubNames.get(member["cid"]) is None:
            clubNames[member["cid"]] = getClubDetails(
                member["cid"], info.context.cookies
            )["name"]

        clubName = clubNames.get(member["cid"])

        for field in details.fields:
            value = ""
            mappedField = headerMapping.get(field.lower())
            if field == "clubid":
                value = clubName
            elif field == "uid":
                value = (
                    userDetails["firstName"] + " " + userDetails["lastName"]
                )
            elif field == "rollno":
                value = userDetails["rollno"]
            elif field == "batch":
                value = userDetails["batch"]
            elif field == "email":
                value = userDetails["email"]
            elif field == "partofclub":
                value = "No"
                for role in member["roles"]:
                    if role["end_year"] is None:
                        value = "Yes"
                        break
            elif field == "roles":
                listOfRoles = []
                for i in member["roles"]:
                    roleFormatting = [
                        i["name"],
                        int(i["start_year"]),
                        int(i["end_year"])
                        if i["end_year"] is not None
                        else None,
                    ]
                    if details.typeRoles == "all":
                        listOfRoles.append(roleFormatting)
                    elif details.typeRoles == "current":
                        if roleFormatting[2] is None:
                            listOfRoles.append(roleFormatting)
                value = str(listOfRoles)
            elif field == "poc":
                value = "Yes" if member["poc"] else "No"

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
    getUserCertificates,
    getPendingCertificates,
    verifyCertificate,
    getCertificateByNumber,
    getAllCertificates,
    downloadMembersData,
]
