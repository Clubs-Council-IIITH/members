"""
Mutation resolvers
"""

from datetime import datetime
from os import getenv
from zoneinfo import ZoneInfo

import strawberry
from fastapi.encoders import jsonable_encoder

from db import membersdb
from models import Member

# import all models and types
from otypes import FullMemberInput, Info, MemberType, SimpleMemberInput
from utils import clubCategory, getUser, non_deleted_members, unique_roles_id

inter_communication_secret_global = getenv("INTER_COMMUNICATION_SECRET")
ist = ZoneInfo("Asia/Kolkata")


@strawberry.mutation
async def createMember(memberInput: FullMemberInput, info: Info) -> MemberType:
    """
    Mutation resolver to create a new member by a club or CC

    Args:
        memberInput (otypes.FullMemberInput): Contains details of the member.
        info (otypes.Info): Contains the logged in user's details.

    Returns:
        (otypes.MemberType): Contains the details of the member.

    Raises:
        Exception: Not Authenticated
        Exception: Not Authenticated to access this API
        Exception: A record with same uid and cid already exists
        Exception: Invalid User ID
        Exception: Roles cannot be empty
        Exception: Start Month must be provided
        Exception: End month must be provided
        Exception: Start date cannot be after end date
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

    if await membersdb.find_one(
        {
            "$and": [
                {"cid": member_input["cid"]},
                {"uid": member_input["uid"]},
            ]
        }
    ):
        raise Exception("A record with same uid and cid already exists")

    # Check whether this uid is valid or not
    userMember = await getUser(member_input["uid"], info.context.cookies)
    if userMember is None:
        raise Exception("Invalid User ID")

    if len(member_input["roles"]) == 0:
        raise Exception("Roles cannot be empty")

    for i in member_input["roles"]:
        if i["start_month"] is None:
            raise Exception("Start month must be provided")
        if i["end_year"] and i["end_month"] is None:
            raise Exception("End month must be provided")
        if i["end_year"] and i["end_month"] and i["start_month"]:
            sy, sm = i["start_year"], i["start_month"]
            ey, em = i["end_year"], i["end_month"]
            if (sy, sm) > (ey, em):
                raise Exception("Start date cannot be after end date")
        elif i["end_year"] and i["end_year"] < i["start_year"]:
            raise Exception("Start date cannot be after end date")
    
    club_category = await clubCategory(
        member_input["cid"], info.context.cookies
    )
    auto_approve = user["role"] == "cc" or club_category in ["body", "admin"]

    current_time = datetime.now(ist)
    time_str = current_time.strftime("%d-%m-%Y %I:%M %p IST")

    roles = []
    for role in member_input["roles"]:
        # Assign start_month if missing and start_year is present
        now_m, now_y = datetime.now().month, datetime.now().year
        sm, sy = role["start_month"], role["start_year"]
        if sm is None or (sy, sm) > (now_y, now_m):
            role["start_month"] = now_m
            role["start_year"] = now_y
            role["end_month"] = None
            role["end_year"] = None

        sm, sy = role["start_month"], role["start_year"]
        em, ey = role["end_month"], role["end_year"]
        if ey is None or em is None or (sy > ey or (sy==ey and sm>em)):
            role["end_month"] = None
            role["end_year"] = None
        if auto_approve:
            role["approved"] = True
            role["approval_time"] = time_str
        roles.append(role)

    member_input["roles"] = roles

    # add creation time of the user
    member_input["creation_time"] = time_str
    member_input["last_edited_time"] = time_str

    created_id = (await membersdb.insert_one(member_input)).inserted_id
    await unique_roles_id(member_input["uid"], member_input["cid"])

    created_sample = Member.model_validate(
        await membersdb.find_one({"_id": created_id}, {"_id": 0})
    )

    return MemberType.from_pydantic(created_sample)


@strawberry.mutation
async def editMember(memberInput: FullMemberInput, info: Info) -> MemberType:
    """
    Mutation resolver to edit a member by club and CC

    Args:
        memberInput (otypes.FullMemberInput): Contains details of the member.
        info (otypes.Info): Contains the logged in user's details.

    Returns:
        (otypes.MemberType): Contains the details of the member.

    Raises:
        Exception: Not Authenticated
        Exception: Not Authenticated to access this API
        Exception: No such Record!
        Exception: Roles cannot be empty
        Exception: Start Month must be provided
        Exception: End month must be provided
        Exception: Start date cannot be after end date
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
        if i["start_month"] is None:
            raise Exception("Start month must be provided")
        if i["end_year"] and i["end_month"] is None:
            raise Exception("End nonth must be provided")
        if i["end_year"] and i["end_month"] and i["start_month"]:
            sy, sm = i["start_year"], i["start_month"]
            ey, em = i["end_year"], i["end_month"]
            if (sy, sm) > (ey, em):
                raise Exception("Start date cannot be after end date")
        elif i["end_year"] and i["end_year"] < i["start_year"]:
            raise Exception("Start date cannot be after end date")

    member_ref = await membersdb.find_one(
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

    club_category = await clubCategory(
        member_input["cid"], info.context.cookies
    )
    auto_approve = user["role"] == "cc" or club_category in ["body", "admin"]

    roles = []
    for role in member_input["roles"]:
        now_m, now_y = datetime.now().month, datetime.now().year
        sm, sy = role["start_month"], role["start_year"]
        if sm is None or (sy, sm) > (now_y, now_m):
            role["start_month"] = now_m
            role["start_year"] = now_y
            role["end_month"] = None
            role["end_year"] = None

        em, ey = role["end_month"], role["end_year"]
        if ey is None or em is None:
            role["end_month"] = None
            role["end_year"] = None
        role_new = role.copy()

        # if role's start_my, end_my, name is same as existing role,
        # then keep the existing approved status
        found_existing_role = False
        for i in member_roles:
            if (
                i.start_year == role_new.get("start_year")
                and i.start_month == role_new.get("start_month")
                and i.end_year == role_new.get("end_year")
                and i.end_month == role_new.get("end_month")
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
            role_new["approved"] = auto_approve
            role_new["approval_time"] = time_str if auto_approve else None
            role_new["rejection_time"] = None
        roles.append(role_new)

    # DB STUFF
    await membersdb.update_one(
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

    await unique_roles_id(member_input["uid"], member_input["cid"])

    return await non_deleted_members(member_input)


@strawberry.mutation
async def deleteMember(
    memberInput: SimpleMemberInput, info: Info
) -> MemberType:
    """
    Mutation resolver to delete a member or member's role by club or CC

    Args:
        memberInput (otypes.SimpleMemberInput): Contains the cid and uid of the
                                         member, and rid when deleting role.
        info (otypes.Info): Contains the logged in user's details.

    Returns:
        (otypes.MemberType): Contains the details of the member.

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

    existing_data = await membersdb.find_one(
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
        await membersdb.delete_one(
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
    await membersdb.update_one(
        {
            "$and": [
                {"cid": member_input["cid"]},
                {"uid": member_input["uid"]},
            ]
        },
        {"$set": {"roles": roles}},
    )

    await unique_roles_id(member_input["uid"], member_input["cid"])

    return await non_deleted_members(member_input)


@strawberry.mutation
async def approveMember(
    memberInput: SimpleMemberInput, info: Info
) -> MemberType:
    """
    Mutation resolver to approve a member's role by CC

    Args:
        memberInput (otypes.SimpleMemberInput): Contains the details of the
                                         member's role, cid, uid and rid.
        info (otypes.Info): Contains the logged in user's details.

    Returns:
        (otypes.MemberType): Contains the details of the member.

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

    existing_data = await membersdb.find_one(
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
    await membersdb.update_one(
        {
            "$and": [
                {"cid": member_input["cid"]},
                {"uid": member_input["uid"]},
            ]
        },
        {"$set": {"roles": roles}},
    )

    await unique_roles_id(member_input["uid"], member_input["cid"])

    return await non_deleted_members(member_input)


@strawberry.mutation
async def rejectMember(
    memberInput: SimpleMemberInput, info: Info
) -> MemberType:
    """
    Mutation resolver to reject a member's role by CC

    Args:
        memberInput (otypes.SimpleMemberInput): Contains the details of the
                                         member.cid, uid and rid.
        info (otypes.Info): Contains the logged in user's details.

    Returns:
        (otypes.MemberType): Contains the details of the member.

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

    existing_data = await membersdb.find_one(
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
    await membersdb.update_one(
        {
            "$and": [
                {"cid": member_input["cid"]},
                {"uid": member_input["uid"]},
            ]
        },
        {"$set": {"roles": roles}},
    )

    await unique_roles_id(member_input["uid"], member_input["cid"])

    return await non_deleted_members(member_input)


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
#                 {"start_my": member_input["start_my"]},
#                 {"deleted": False},
#             ]
#         },
#         {"$set": {"end_my": datetime.now().year}},
#     )

#     created_sample = Member.model_validate(membersdb.find_one(
# {"_id": created_id}))
#     return MemberType.from_pydantic(created_sample)


@strawberry.mutation
async def updateMembersCid(
    info: Info,
    old_cid: str,
    new_cid: str,
    inter_communication_secret: str | None = None,
) -> int:
    """
    Update all members of a club from old_cid to new_cid when cid is changed,
    for CC

    Args:
        old_cid (str): the old cid
        new_cid (str): the new cid
        inter_communication_secret (str): The inter communication
                                                 secret. Defaults to None.

    Returns:
        (int): The number of updated members.

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

    upd_ref = await membersdb.update_many({"cid": old_cid}, updation)
    return upd_ref.modified_count


# register all mutations
mutations = [
    createMember,
    editMember,
    deleteMember,
    approveMember,
    rejectMember,
    updateMembersCid,
]
