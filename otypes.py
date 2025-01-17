"""
Types and Inputs
"""

import json
from functools import cached_property
from typing import Dict, Optional, Union

import strawberry
from strawberry.fastapi import BaseContext
from strawberry.types import Info as _Info
from strawberry.types.info import RootValueType

from models import Member, PyObjectId, Roles


# custom context class
class Context(BaseContext):
    """
    Class provides user metadata and cookies from request headers, has methods for doing this.
    """    
    @cached_property
    def user(self) -> Union[Dict, None]:
        if not self.request:
            return None

        user = json.loads(self.request.headers.get("user", "{}"))
        return user

    @cached_property
    def cookies(self) -> Union[Dict, None]:
        if not self.request:
            return None

        cookies = json.loads(self.request.headers.get("cookies", "{}"))
        return cookies


"""custom info Type for user metadata"""
Info = _Info[Context, RootValueType]

"""A scalar Type for serializing PyObjectId, used for id field"""
PyObjectIdType = strawberry.scalar(
    PyObjectId, serialize=str, parse_value=lambda v: PyObjectId(v)
)


# TYPES
@strawberry.experimental.pydantic.type(model=Roles, all_fields=True)
class RolesType:
    """
    Type used to return all the details regarding a role of a club member
    """
    pass


@strawberry.experimental.pydantic.type(
    model=Member,
    fields=[
        "id",
        "cid",
        "uid",
        "roles",
        "poc",
        "creation_time",
        "last_edited_time",
    ],
)
class MemberType:
    """
    Type used to return all the details of a club member
    """
    pass


# INPUTS
@strawberry.experimental.pydantic.input(
    model=Roles, fields=["name", "start_year", "end_year"]
)
class RolesInput:
    """
    Input used to take a role's name, start and end year
    """
    pass


@strawberry.experimental.pydantic.input(
    model=Member, fields=["cid", "uid", "roles"]
)
class FullMemberInput:
    """
    Input used to take a member's cid, uid, roles and poc(optional) fields
    """
    poc: Optional[bool] = strawberry.UNSET


@strawberry.input
class SimpleMemberInput:
    """
    Input used to take a member's cid, uid and rid(optional) fields
    """
    cid: str
    uid: str
    rid: Optional[str]


@strawberry.input
class SimpleClubInput:
    """
    Input used to take a club's cid
    """
    cid: str
