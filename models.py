from datetime import datetime
from enum import Enum
from typing import Any, List

import pytz
import strawberry
from bson import ObjectId
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
)
from pydantic_core import core_schema


# for handling mongo ObjectIds
class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler):
        return core_schema.union_schema(
            [
                # check if it's an instance first before doing any further work
                core_schema.is_instance_schema(ObjectId),
                core_schema.no_info_plain_validator_function(cls.validate),
            ],
            serialization=core_schema.to_string_ser_schema(),
        )

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema):
        field_schema.update(type="string")


def get_ist_time():
    """
    Function to get the current time in IST
    """
    return datetime.now(pytz.timezone("Asia/Kolkata")).isoformat()


@strawberry.enum
class CertificateStates(Enum):
    pending_cc = "pending_cc"
    pending_slo = "pending_slo"
    approved = "approved"
    rejected = "rejected"


@strawberry.type
class Certificate_Status:
    requested_at: str = Field(default_factory=get_ist_time)

    cc_approved_at: str | None = None
    cc_approver: str | None = None

    slo_approved_at: str | None = None
    slo_approver: str | None = None

    def __init__(
        self,
        requested_at: str = get_ist_time(),
        cc_approved_at: str | None = None,
        cc_approver: str | None = None,
        slo_approved_at: str | None = None,
        slo_approver: str | None = None,
    ) -> None:
        self.requested_at = requested_at

        self.cc_approved_at = cc_approved_at
        self.cc_approver = cc_approver

        self.slo_approved_at = slo_approved_at
        self.slo_approver = slo_approver


class Certificate(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    user_id: str
    certificate_number: str
    status: Certificate_Status = Certificate_Status()
    state: CertificateStates = CertificateStates.pending_cc
    certificate_data: str
    key: str
    request_reason: str | None = None

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        str_strip_whitespace=True,
        str_max_length=3000,
        validate_assignment=True,
        validate_default=True,
        validate_return=True,
        extra="forbid",
        json_encoders={ObjectId: str},
        populate_by_name=True,
    )


class Roles(BaseModel):
    rid: str | None = Field(None, description="Unique Identifier for a role")
    name: str = Field(..., min_length=1, max_length=99)
    start_year: int = Field(..., ge=2010, le=2050)
    end_year: int | None = Field(None, gt=2010, le=2051)
    approved: bool = False
    rejected: bool = False
    deleted: bool = False

    # Validators
    @field_validator("end_year")
    def check_end_year(cls, value, info: ValidationInfo):
        if value is not None and value < info.data["start_year"]:
            return None
        return value

    @field_validator("rejected")
    def check_status(cls, value, info: ValidationInfo):
        if info.data["approved"] is True and value is True:
            raise ValueError("Role cannot be both approved and rejected")
        return value

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        str_max_length=100,
        validate_assignment=True,
        validate_default=True,
        validate_return=True,
        extra="forbid",
        str_strip_whitespace=True,
    )


class Member(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    cid: str = Field(..., description="Club ID")
    uid: str = Field(..., description="User ID")
    roles: List[Roles] = Field(
        ..., description="List of Roles for that specific person"
    )

    poc: bool = Field(default_factory=(lambda: 0 == 1), description="Club POC")
    certificates: List[Certificate] = Field(default_factory=list)

    @field_validator("uid", mode="before")
    @classmethod
    def transform_uid(cls, v):
        return v.lower()

    # TODO[pydantic]: The following keys were removed: `json_encoders`.
    # Check https://docs.pydantic.dev/dev-v2/migration/#changes-to-config for more information.  # noqa: E501
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        str_strip_whitespace=True,
        str_max_length=600,
        validate_assignment=True,
        validate_default=True,
        validate_return=True,
        extra="forbid",
        json_encoders={ObjectId: str},
        populate_by_name=True,
    )

    # Separate Coordinator & other members roles option in frontend,
    # for better filtering for all_members_query


# TODO: ADD Descriptions for non-direct fields
