import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        "development-secret"
    )

    AWS_REGION = os.getenv(
        "AWS_REGION",
        "us-east-1"
    )

    S3_BUCKET = os.getenv("S3_BUCKET")

    RIOT_API_KEY = os.getenv("RIOT_API_KEY")

    USERS_TABLE = "Users"
    GAMES_TABLE = "Games"
    PLAYER_GAMES_TABLE = "PlayerGames"

    GROUPS_TABLE = "Groups"
    GROUP_MEMBERS_TABLE = "GroupMembers"

    INVITATIONS_TABLE = "Invitations"

    SESSIONS_TABLE = "Sessions"
    SESSION_MEMBERS_TABLE = "SessionMembers"