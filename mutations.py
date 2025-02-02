"""
Mutation resolvers
"""

from datetime import datetime
from os import getenv
import json
import pytz
import strawberry
from fastapi.encoders import jsonable_encoder

from db import membersdb, certificatesdb
from models import Member, Certificate, CertificateStates

# import all models and types
from otypes import (
        FullMemberInput,
        Info,
        MemberType,
        SimpleMemberInput,
        CertificateInput,
        CertificateType
    )
from queries import memberRolesHelper
from utils import getUser, non_deleted_members, unique_roles_id, generate_key, getClubs

inter_communication_secret_global = getenv("INTER_COMMUNICATION_SECRET")
key_length = int(getenv("KEY_LENGTH", 8))
ist = pytz.timezone("Asia/Kolkata")


@strawberry.mutation
def createMember(memberInput: FullMemberInput, info: Info) -> MemberType:
    """
    Mutation resolver to create a new member by a club or CC

    Args:
        memberInput (FullMemberInput): Contains the details of the member.
        info (Info): Contains the logged in user's details.

    Returns:
        MemberType: Contains the details of the member.

    Raises:
        Exception: Not Authenticated
        Exception: Not Authenticated to access this API
        Exception: A record with same uid and cid already exists
        Exception: Invalid User ID
        Exception: Roles cannot be empty
        Exception: Start year cannot be greater than end year
    """

    user = info.context.user
    if user is None:
        raise Exception("Not Authenticated")

    role = user["role"]
    uid = user["uid"]
    member_input = jsonable_encoder(memberInput.to_pydantic())

    if (member_input["cid"] != uid or user["role"] != "club") and user[
        "role"
    ] != "cc":
        raise Exception("Not Authenticated to access this API")

    if membersdb.find_one(
        {
            "$and": [
                {"cid": member_input["cid"]},
                {"uid": member_input["uid"]},
            ]
        }
    ):
        raise Exception("A record with same uid and cid already exists")

    # Check whether this uid is valid or not
    userMember = getUser(member_input["uid"], info.context.cookies)
    if userMember is None:
        raise Exception("Invalid User ID")

    if len(member_input["roles"]) == 0:
        raise Exception("Roles cannot be empty")

    for i in member_input["roles"]:
        if i["end_year"] and i["start_year"] > i["end_year"]:
            raise Exception("Start year cannot be greater than end year")

    roles0 = []
    for role in member_input["roles"]:
        if role["start_year"] > datetime.now().year:
            role["start_year"] = datetime.now().year
            role["end_year"] = None
        roles0.append(role)

    current_time = datetime.now(ist)
    time_str = current_time.strftime("%d-%m-%Y %I:%M %p IST")

    roles = []
    for role in roles0:
        if user["role"] == "cc":
            role["approved"] = True
            role["approval_time"] = time_str
        roles.append(role)

    member_input["roles"] = roles

    # add creation time of the user
    member_input["creation_time"] = time_str
    member_input["last_edited_time"] = time_str

    # DB STUFF
    created_id = membersdb.insert_one(member_input).inserted_id
    unique_roles_id(member_input["uid"], member_input["cid"])

    created_sample = Member.model_validate(
        membersdb.find_one({"_id": created_id}, {"_id": 0})
    )

    return MemberType.from_pydantic(created_sample)


@strawberry.mutation
def editMember(memberInput: FullMemberInput, info: Info) -> MemberType:
    """
    Mutation resolver to edit a member by club and CC

    Args:
        memberInput (FullMemberInput): Contains the details of the member.
        info (Info): Contains the logged in user's details.

    Returns:
        MemberType: Contains the details of the member.

    Raises:
        Exception: Not Authenticated
        Exception: Not Authenticated to access this API
        Exception: No such Record!
        Exception: Roles cannot be empty
        Exception: Start year cannot be greater than end year
    """

    user = info.context.user
    if user is None:
        raise Exception("Not Authenticated")

    uid = user["uid"]
    member_input = jsonable_encoder(memberInput.to_pydantic())

    if (member_input["cid"] != uid or user["role"] != "club") and user[
        "role"
    ] != "cc":
        raise Exception("Not Authenticated to access this API")

    if len(member_input["roles"]) == 0:
        raise Exception("Roles cannot be empty")

    for i in member_input["roles"]:
        if i["end_year"] and i["start_year"] > i["end_year"]:
            raise Exception("Start year cannot be greater than end year")

    member_ref = membersdb.find_one(
        {
            "$and": [
                {"cid": member_input["cid"]},
                {"uid": member_input["uid"]},
            ]
        }
    )

    if member_ref is None:
        raise Exception("No such Record!")
    else:
        member_ref = Member.model_validate(member_ref)

    member_roles = member_ref.roles

    current_time = datetime.now(ist)
    time_str = current_time.strftime("%d-%m-%Y %I:%M %p IST")

    roles = []
    for role in member_input["roles"]:
        if role["start_year"] > datetime.now().year:
            role["start_year"] = datetime.now().year
            role["end_year"] = None
        role_new = role.copy()

        # if role's start_year, end_year, name is same as existing role,
        # then keep the existing approved status
        found_existing_role = False
        for i in member_roles:
            if (
                i.start_year == role_new["start_year"]
                and i.end_year == role_new["end_year"]
                and i.name == role_new["name"]
            ):
                role_new["approved"] = i.approved
                role_new["rejected"] = i.rejected
                role_new["deleted"] = i.deleted

                found_existing_role = True

                # Remove the existing role from member_roles
                member_roles.remove(i)
                break

        if not found_existing_role:
            role_new["approved"] = user["role"] == "cc"
            role_new["approval_time"] = (
                time_str if user["role"] == "cc" else None
            )
            role_new["rejection_time"] = None
        roles.append(role_new)

    # DB STUFF
    membersdb.update_one(
        {
            "$and": [
                {"cid": member_input["cid"]},
                {"uid": member_input["uid"]},
            ]
        },
        {
            "$set": {
                "roles": roles,
                "poc": member_input["poc"],
                "last_edited_time": time_str,
            }
        },
    )

    unique_roles_id(member_input["uid"], member_input["cid"])

    return non_deleted_members(member_input)


@strawberry.mutation
def deleteMember(memberInput: SimpleMemberInput, info: Info) -> MemberType:
    """
    Mutation resolver to delete a member or member's role by club or CC

    Args:
        memberInput (SimpleMemberInput): Contains the cid and uid of the
                                         member, and rid when deleting role.
        info (Info): Contains the logged in user's details.

    Returns:
        MemberType: Contains the details of the member.

    Raises:
        Exception: Not Authenticated
        Exception: Not Authenticated to access this API
        Exception: No such Record
    """  # noqa: E501

    user = info.context.user
    if user is None:
        raise Exception("Not Authenticated")

    uid = user["uid"]
    member_input = jsonable_encoder(memberInput)

    if (member_input["cid"] != uid or user["role"] != "club") and user[
        "role"
    ] != "cc":
        raise Exception("Not Authenticated to access this API")

    existing_data = membersdb.find_one(
        {
            "$and": [
                {"cid": member_input["cid"]},
                {"uid": member_input["uid"]},
            ]
        },
        {"_id": 0},
    )
    if existing_data is None:
        raise Exception("No such Record")

    if "rid" not in member_input or not member_input["rid"]:
        membersdb.delete_one(
            {
                "$and": [
                    {"cid": member_input["cid"]},
                    {"uid": member_input["uid"]},
                ]
            }
        )

        return MemberType.from_pydantic(Member.model_validate(existing_data))

    roles = []
    for i in existing_data["roles"]:
        if i["rid"] == member_input["rid"]:
            i["deleted"] = True
        roles.append(i)

    # DB STUFF
    membersdb.update_one(
        {
            "$and": [
                {"cid": member_input["cid"]},
                {"uid": member_input["uid"]},
            ]
        },
        {"$set": {"roles": roles}},
    )

    unique_roles_id(member_input["uid"], member_input["cid"])

    return non_deleted_members(member_input)


@strawberry.mutation
def approveMember(memberInput: SimpleMemberInput, info: Info) -> MemberType:
    """
    Mutation resolver to approve a member's role by CC

    Args:
        memberInput (SimpleMemberInput): Contains the details of the member
                                         and member's role.cid, uid and rid.
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

    member_input = jsonable_encoder(memberInput)

    if user["role"] != "cc":
        raise Exception("Not Authenticated to access this API")

    existing_data = membersdb.find_one(
        {
            "$and": [
                {"cid": member_input["cid"]},
                {"uid": member_input["uid"]},
            ]
        },
        {"_id": 0},
    )
    if existing_data is None:
        raise Exception("No such Record")

    # if "rid" not in member_input:
    #     raise Exception("rid is required")

    current_time = datetime.now(ist)
    time_str = current_time.strftime("%d-%m-%Y %I:%M %p IST")

    # approves the role along with entering approval time
    roles = []
    for i in existing_data["roles"]:
        if not member_input["rid"] or i["rid"] == member_input["rid"]:
            i["approved"] = True
            i["approval_time"] = time_str
            i["rejected"] = False
            i["rejection_time"] = None
        roles.append(i)

    # DB STUFF
    membersdb.update_one(
        {
            "$and": [
                {"cid": member_input["cid"]},
                {"uid": member_input["uid"]},
            ]
        },
        {"$set": {"roles": roles}},
    )

    unique_roles_id(member_input["uid"], member_input["cid"])

    return non_deleted_members(member_input)


@strawberry.mutation
def rejectMember(memberInput: SimpleMemberInput, info: Info) -> MemberType:
    """
    Mutation resolver to reject a member's role by CC

    Args:
        memberInput (SimpleMemberInput): Contains the details of the
                                         member.cid, uid and rid.
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

    member_input = jsonable_encoder(memberInput)

    if user["role"] != "cc":
        raise Exception("Not Authenticated to access this API")

    existing_data = membersdb.find_one(
        {
            "$and": [
                {"cid": member_input["cid"]},
                {"uid": member_input["uid"]},
            ]
        },
        {"_id": 0},
    )
    if existing_data is None:
        raise Exception("No such Record")

    # if "rid" not in member_input:
    #     raise Exception("rid is required")

    current_time = datetime.now(ist)
    time_str = current_time.strftime("%d-%m-%Y %I:%M %p IST")

    roles = []
    for i in existing_data["roles"]:
        if not member_input["rid"] or i["rid"] == member_input["rid"]:
            i["approved"] = False
            i["approval_time"] = None
            i["rejection_time"] = time_str
            i["rejected"] = True
        roles.append(i)

    # DB STUFF
    membersdb.update_one(
        {
            "$and": [
                {"cid": member_input["cid"]},
                {"uid": member_input["uid"]},
            ]
        },
        {"$set": {"roles": roles}},
    )

    unique_roles_id(member_input["uid"], member_input["cid"])

    return non_deleted_members(member_input)


# @strawberry.mutation
# def leaveClubMember(memberInput: SimpleMemberInput, info: Info) ->
# MemberType:
#     user = info.context.user
#     if user is None:
#         raise Exception("Not Authenticated")

#     role = user["role"]
#     uid = user["uid"]
#     member_input = jsonable_encoder(memberInput.to_pydantic())

#     if member_input["cid"] != uid and role != "club":
#         raise Exception("Not Authenticated to access this API")

#     created_id = clubsdb.update_one(
#         {
#             "$and": [
#                 {"cid": member_input["cid"]},
#                 {"uid": member_input["uid"]},
#                 {"start_year": member_input["start_year"]},
#                 {"deleted": False},
#             ]
#         },
#         {"$set": {"end_year": datetime.now().year}},
#     )

#     created_sample = Member.model_validate(membersdb.find_one(
# {"_id": created_id}))
#     return MemberType.from_pydantic(created_sample)


@strawberry.mutation
def updateMembersCid(
    info: Info,
    old_cid: str,
    new_cid: str,
    inter_communication_secret: str | None = None,
) -> int:
    """
    Update all members of a club from old_cid to new_cid when cid is changed,
    for CC

    Args:
        old_cid: the old cid
        new_cid: the new cid
        inter_communication_secret (str | None): The inter communication
                                                 secret. Defaults to None.

    Returns:
        int: The number of updated members.

    Raises:
        Exception: Not Authenticated!
        Exception: Authentication Error! Invalid secret!
    """

    user = info.context.user

    if user is None or user["role"] not in ["cc"]:
        raise Exception("Not Authenticated!")

    if inter_communication_secret != inter_communication_secret_global:
        raise Exception("Authentication Error! Invalid secret!")

    updation = {
        "$set": {
            "cid": new_cid,
        }
    }

    upd_ref = membersdb.update_many({"cid": old_cid}, updation)
    return upd_ref.modified_count


@strawberry.mutation
def requestCertificate(
    certificate_input: CertificateInput, info: Info
) -> CertificateType:
    user = info.context.user
    if user is None:
        raise Exception("Not Authenticated")

    # Generate certificate number
    year = datetime.now().year
    next_year = year + 1
    year_code = f"{str(year)[2:]}{str(next_year)[2:]}"

    count = (
        certificatesdb.count_documents(
            {"certificate_number": {"$regex": f"^SLC/{year_code}/"}}
        )
        + 1
    )
    certificate_number = f"SLC/{year_code}/{count:04d}"

    user_memberships = memberRolesHelper(user["uid"], info)
    if not user_memberships:
        raise Exception("No Memberships Found")

    clubs = getClubs(info.context.cookies)
    club_name_map = {club["cid"]: club["name"] for club in clubs}
    memberships = []
    for m in user_memberships:
        roles = m.roles
        cid = m.cid
        for role in roles:
            memberships.append(
                {
                    "startYear": role.start_year,
                    "endYear": role.end_year,
                    "name": role.name,
                    "cid": cid,
                    "clubName": club_name_map.get(cid, "Unknown Club"),
                }
            )

    certificate_data = {
        "user_id": user["uid"],
        "memberships": memberships,
    }

    new_certificate = Certificate(
        user_id=user["uid"],
        certificate_number=certificate_number,
        certificate_data=json.dumps(certificate_data),
        request_reason=certificate_input.request_reason,
        key=generate_key(key_length),
    )

    created_id = certificatesdb.insert_one(
        jsonable_encoder(new_certificate)
    ).inserted_id

    created_certificate = Certificate.parse_obj(
        certificatesdb.find_one({"_id": created_id})
    )

    return CertificateType.from_pydantic(created_certificate)


@strawberry.mutation
def approveCertificate(certificate_number: str, info: Info) -> CertificateType:
    noaccess_error = Exception(
        "Can not access certificate. Either it does not exist or user does not have perms."  # noqa: E501
    )
    user = info.context.user

    if user is None or user["role"] not in ["cc", "slo"]:
        raise Exception("Not Authenticated or Unauthorized")

    certificate = certificatesdb.find_one(
        {"certificate_number": certificate_number}
    )

    if not certificate:
        raise noaccess_error

    current_status = certificate["state"]
    updation = {}

    current_time = datetime.now(pytz.timezone("Asia/Kolkata")).isoformat()  # Convert to ISO format string

    if (
        current_status == CertificateStates.pending_cc.value
        and user["role"] == "cc"
    ):
        new_status = CertificateStates.pending_slo.value
        updation = {
            "$set": {
                "state": new_status,
                "status.cc_approved_at": current_time,
                "status.cc_approver": user["uid"],
            }
        }
    elif (
        current_status == CertificateStates.pending_slo.value
        and user["role"] == "slo"
    ):
        new_status = CertificateStates.approved.value
        updation = {
            "$set": {
                "state": new_status,
                "status.slo_approved_at": current_time,
                "status.slo_approver": user["uid"],
            }
        }
    else:
        raise noaccess_error

    certificatesdb.update_one(
        {"certificate_number": certificate_number}, updation
    )

    updated_certificate = Certificate.parse_obj(
        certificatesdb.find_one({"certificate_number": certificate_number})
    )
    return CertificateType.from_pydantic(updated_certificate)


@strawberry.mutation
def rejectCertificate(certificate_number: str, info: Info) -> CertificateType:
    user = info.context.user
    if user is None or user["role"] not in ["cc", "slo"]:
        raise Exception("Not Authenticated or Unauthorized")

    certificate = certificatesdb.find_one(
        {"certificate_number": certificate_number}
    )

    if not certificate:
        raise Exception("No such certificate found")

    current_status = certificate["state"]
    updation = {}

    if (
        current_status == CertificateStates.pending_cc.value
        and user["role"] == "cc"
    ):
        new_status = CertificateStates.rejected.value
        updation = {
            "$set": {
                "state": new_status,
            }
        }
    elif (
        current_status == CertificateStates.pending_slo.value
        and user["role"] == "slo"
    ):
        new_status = CertificateStates.rejected.value
        updation = {
            "$set": {
                "state": new_status,
            }
        }
    else:
        raise Exception("Can not reject certificate")

    certificatesdb.update_one(
        {"certificate_number": certificate_number}, updation
    )

    updated_certificate = Certificate.parse_obj(
        certificatesdb.find_one({"certificate_number": certificate_number})
    )
    return CertificateType.from_pydantic(updated_certificate)

# register all mutations
mutations = [
    createMember,
    editMember,
    deleteMember,
    approveMember,
    rejectMember,
    updateMembersCid,
    requestCertificate,
    approveCertificate,
    rejectCertificate,
]
