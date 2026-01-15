#!/usr/bin/env python3
"""
Migration script to add missing month fields to member roles.

- For roles without start_month, assign 1.
- For roles without end_month but with end_year, assign 1.
- If end_year is null, keep end_month as null.
"""

import asyncio
from db import membersdb

Month_to_be_assigned=1

async def migrate_month_fields() -> None:
    """
    Updates all member documents to ensure roles have month fields populated
    per the rules described above.
    """
    pipeline = [
        {
            "$set": {
                "roles": {
                    "$map": {
                        "input": "$roles",
                        "as": "role",
                        "in": {
                            "$mergeObjects": [
                                "$$role",
                                {
                                    "start_month": {"$ifNull": ["$$role.start_month", Month_to_be_assigned]},
                                    "end_month": {
                                        "$ifNull": [
                                            "$$role.end_month",
                                            {
                                                "$cond": [
                                                    {"$eq": ["$$role.end_year", None]},
                                                    None,
                                                    Month_to_be_assigned,
                                                ]
                                            },
                                        ]
                                    },
                                },
                            ]
                        },
                    }
                }
            }
        }
    ]

    result = await membersdb.update_many({}, pipeline)
    print(f"Number of modified documents: {result.modified_count}")

if __name__ == "__main__":
    asyncio.run(migrate_month_fields())
