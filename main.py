"""
Final Setup

This file is used to setup the final schema for the subgraph.
It imports the resolvers from the queries and mutations files and creates a final GraphQL schema.
It sets up the Fast API for the Members Microservice.
"""

from os import getenv

import strawberry
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter
from strawberry.tools import create_type

# override PyObjectId and Context scalars
from models import PyObjectId
from mutations import mutations
from otypes import Context, PyObjectIdType

# import all queries and mutations
from queries import queries

# create query types
Query = create_type("Query", queries)

# create mutation types
Mutation = create_type("Mutation", mutations)


# override context getter
async def get_context() -> Context:
    return Context()


# initialize federated schema
schema = strawberry.federation.Schema(
    query=Query,
    mutation=Mutation,
    enable_federation_2=True,
    scalar_overrides={PyObjectId: PyObjectIdType},
)

# check whether running in debug mode
DEBUG = getenv("GLOBAL_DEBUG", "False").lower() in ("true", "1", "t")

# serve API with FastAPI router
gql_app = GraphQLRouter(schema, graphiql=True, context_getter=get_context)
app = FastAPI(
    debug=DEBUG,
    title="CC Members Microservice",
    desciption="Handles Data of Members",
)
app.include_router(gql_app, prefix="/graphql")
