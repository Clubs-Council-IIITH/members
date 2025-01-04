"""
MongoDB Initialization Module

This module sets up a connection to a MongoDB database and ensures that the required indexes are created.
This module connects to the MongoDB database using environment variables for authentication.
Ensures that a 'unique_members' index is present on the `cid` and 'uid' fields in the Members collection.
It specifically exports the members collection of the database.

Environment Variables:
    `MONGO_USERNAME` (str): MongoDB username. Defaults to "username".
    `MONGO_PASSWORD` (str): MongoDB password. Defaults to "password".
    `MONGO_PORT` (str): MongoDB port. Defaults to "27017".
    `MONGO_DATABASE` (str): MongoDB database name. Defaults to "default".

"""

from os import getenv

from pymongo import MongoClient

# get mongodb URI and database name from environment variale
MONGO_URI = "mongodb://{}:{}@mongo:{}/".format(
    getenv("MONGO_USERNAME", default="username"),
    getenv("MONGO_PASSWORD", default="password"),
    getenv("MONGO_PORT", default="27017"),
)
MONGO_DATABASE = getenv("MONGO_DATABASE", default="default")

# instantiate mongo client
client = MongoClient(MONGO_URI)

# get database
db = client[MONGO_DATABASE]
membersdb = db.members

try:
    # check if the members index exists
    if "unique_members" in membersdb.index_information():
        print("The members index exists.")
    else:
        # create the index
        membersdb.create_index(
            [("cid", 1), ("uid", 1)], unique=True, name="unique_members"
        )
        print("The members index was created.")

    print(membersdb.index_information())
except Exception:
    pass
