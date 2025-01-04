"""
Data Models for Members Microservice

This file decides what and how a Members's information is stored in its MongoDB document.
One user could be a part of multiple clubs.
his membership in each club is stored in a separate document.

It defines 2 models:
    Member : Used for storing members information.
    Roles : Used for storing a member's roles within the same club. Used within Member model.
"""

from typing import Any, List

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
    """
    MongoDB ObjectId handler

    This class contains clasmethods to validate and serialize ObjectIds.
    ObjectIds of documents under the Clubs collection are stored under the 'id' field.
    """

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler):
        """
        Defines custom schema for Pydantic validation

        This method is used to define the schema for the Pydantic model.

        Args:
            source_type (Any): The source type.
            handler: The handler.

        Returns:
            dict: The schema for the Pydantic model.
        """

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
        """
        Validates the given ObjectId

        Args:
            v (Any): The value to validate.

        Returns:
            ObjectId: The validated ObjectId.

        Raises:
            ValueError: If the given value is not a valid ObjectId.
        """

        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema):
        """
        Generates JSON schema

        This method is used to generate the JSON schema for the Pydantic model.

        Args:
            field_schema (dict): The field schema.
        """

        field_schema.update(type="string")


class Roles(BaseModel):
    """
    Model for storing a member's roles

    This model defines the structure to store a member's roles.

    Attributes:
        rid (str): Unique Identifier for a role, a role id.
        name (str): Name of the role
        start_year (int): Year the role started
        end_year (Optional[int]): Year the role ended
        approved (bool): Whether the role is approved
        approval_time (Optional[str]): Time the role was approved
        rejected (bool): Whether the role was rejected
        rejection_time (Optional[str]): Time the role was rejected
        deleted (bool): Whether the role is deleted

    Field Validators:
        check_end_year: Validates the end_year field based on the start_year field.checks if the end_year is smaller than the start_year.
        check_status: Validates the status of the role based on the approved and rejected fields.

    Raises Errors:
        ValueError: If the end_year is smaller than the start_year.
        ValueError: If the status of the role is not valid.If both approved and rejeted are True.
        
    """

    rid: str | None = Field(None, description="Unique Identifier for a role")
    name: str = Field(..., min_length=1, max_length=99)
    start_year: int = Field(..., ge=2010, le=2050)
    end_year: int | None = Field(None, gt=2010, le=2051)
    approved: bool = False
    approval_time: str | None = None
    rejected: bool = False
    rejection_time: str | None = None
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
    """
    Model for storing a member's information

    This model defines the structure to store a member's information.

    Attributes:
        id (PyObjectId): Stores the ObjectId of the member's document.
        cid (str): Unique Identifier for a club, a club id.
        uid (str): Unique Identifier for a user, a user id.
        creation_time (str): Time the member was created.
        last_edited_time (str): Time the member's information was last edited.
        roles (List[Roles]): List of Roles for that specific person.
        poc (bool): Whether the member is a POC(Point of Contact) for the club.

    Field Validators:
        transform_uid: Transforms the uid field text to lowercase.
    """

    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    cid: str = Field(..., description="Club ID")
    uid: str = Field(..., description="User ID")
    creation_time: str | None = None
    last_edited_time: str | None = None
    roles: List[Roles] = Field(
        ..., description="List of Roles for that specific person"
    )

    poc: bool = Field(default_factory=(lambda: 0 == 1), description="Club POC")

    @field_validator("uid", mode="before")
    @classmethod
    def transform_uid(cls, v):
        return v.lower()

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        str_strip_whitespace=True,
        str_max_length=600,
        validate_assignment=True,
        validate_default=True,
        validate_return=True,
        extra="forbid",
        populate_by_name=True,
    )

    # Separate Coordinator & other members roles option in frontend,
    # for better filtering for all_members_query


# TODO: ADD Descriptions for non-direct fields
