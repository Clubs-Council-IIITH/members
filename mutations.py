from datetime import datetime
from os import getenv

import strawberry
from fastapi.encoders import jsonable_encoder

from db import membersdb, certificatesdb
from models import Certificate, Member

# import all models and types
from otypes import (
    CertificateInput,
    CertificateType,
    FullMemberInput,
    Info,
    MemberType,
    SimpleMemberInput,
)
from enums import CertificateStatusType
from utils import getUser, non_deleted_members, unique_roles_id

inter_communication_secret_global = getenv("INTER_COMMUNICATION_SECRET")


@strawberry.mutation
def createMember(memberInput: FullMemberInput, info: Info) -> MemberType:
    """
    Mutation to create a new member by that specific 'club' or cc
    """
    user = info.context.user
    if user is None:
        raise Exception("Not Authenticated")

    role = user["role"]
    uid = user["uid"]
    member_input = jsonable_encoder(memberInput.to_pydantic())

    if (member_input["cid"] != uid or user["role"] != "club") and user["role"] != "cc":
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

    roles = []
    for role in roles0:
        role["approved"] = user["role"] == "cc"
        roles.append(role)

    member_input["roles"] = roles

    # DB STUFF
    created_id = membersdb.insert_one(member_input).inserted_id
    unique_roles_id(member_input["uid"], member_input["cid"])

    created_sample = Member.parse_obj(
        membersdb.find_one({"_id": created_id}, {"_id": 0})
    )

    return MemberType.from_pydantic(created_sample)


@strawberry.mutation
def editMember(memberInput: FullMemberInput, info: Info) -> MemberType:
    """
    Mutation to edit an already existing member+roles of that specific 'club'
    """
    user = info.context.user
    if user is None:
        raise Exception("Not Authenticated")

    uid = user["uid"]
    member_input = jsonable_encoder(memberInput.to_pydantic())

    if (member_input["cid"] != uid or user["role"] != "club") and user["role"] != "cc":
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
        member_ref = Member.parse_obj(member_ref)

    member_roles = member_ref.roles

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
        roles.append(role_new)

    # DB STUFF
    membersdb.update_one(
        {
            "$and": [
                {"cid": member_input["cid"]},
                {"uid": member_input["uid"]},
            ]
        },
        {"$set": {"roles": roles, "poc": member_input["poc"]}},
    )

    unique_roles_id(member_input["uid"], member_input["cid"])

    return non_deleted_members(member_input)


@strawberry.mutation
def deleteMember(memberInput: SimpleMemberInput, info: Info) -> MemberType:
    """
    Mutation to delete an already existing member (role) of that specific 'club'
    """  # noqa: E501
    user = info.context.user
    if user is None:
        raise Exception("Not Authenticated")

    uid = user["uid"]
    member_input = jsonable_encoder(memberInput)

    if (member_input["cid"] != uid or user["role"] != "club") and user["role"] != "cc":
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

        return MemberType.from_pydantic(Member.parse_obj(existing_data))

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
    Mutation to approve a member role by 'cc'
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

    roles = []
    for i in existing_data["roles"]:
        if not member_input["rid"] or i["rid"] == member_input["rid"]:
            i["approved"] = True
            i["rejected"] = False
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
    Mutation to reject a member role by 'cc'
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

    roles = []
    for i in existing_data["roles"]:
        if not member_input["rid"] or i["rid"] == member_input["rid"]:
            i["approved"] = False
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

#     created_sample = Member.parse_obj(membersdb.find_one(
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
    update all memberd of old_cid to new_cid
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

    count = certificatesdb.count_documents({}) + 1
    certificate_number = f"SLC/{year_code}/{count:04d}"

    # TODO: Generate certificate data (update template rendering logic here)
    certificate_data = f"Certificate data for {user['uid']}"  # Placeholder

    new_certificate = Certificate(
        user_id=user["uid"],
        certificate_number=certificate_number,
        certificate_data=certificate_data,
        request_reason=certificate_input.request_reason,
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
    user = info.context.user
    if user is None or user["role"] not in ["cc", "slo"]:
        raise Exception("Not Authenticated or Unauthorized")

    certificate = certificatesdb.find_one({"certificate_number": certificate_number})
    if not certificate:
        raise Exception("Certificate not found")

    current_status = certificate["status"]
    new_status = (
        CertificateStatusType.PENDING_SLO
        if current_status == CertificateStatusType.PENDING_CC
        else (
            CertificateStatusType.APPROVED
            if current_status == CertificateStatusType.PENDING_SLO
            else current_status
        )
    )

    if new_status == CertificateStatusType.APPROVED:
        certificatesdb.update_one(
            {"certificate_number": certificate_number},
            {
                "$set": {
                    "status": new_status,
                    "approved_at": datetime.now(),
                    "approver_id": user["uid"],
                }
            },
        )
    else:
        certificatesdb.update_one(
            {"certificate_number": certificate_number}, {"$set": {"status": new_status}}
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
]
