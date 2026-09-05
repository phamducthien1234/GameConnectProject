import boto3
from config import Config


dynamodb = boto3.resource(
    "dynamodb",
    region_name=Config.AWS_REGION
)

table = dynamodb.Table(
    Config.GAMES_TABLE
)


games = [
    {
        "game_id": "G001",
        "game_name": "Valorant",
        "genre": "FPS"
    },
    {
        "game_id": "G002",
        "game_name": "League of Legends",
        "genre": "MOBA"
    },
    {
        "game_id": "G003",
        "game_name": "Counter-Strike 2",
        "genre": "FPS"
    },
    {
        "game_id": "G004",
        "game_name": "Dota 2",
        "genre": "MOBA"
    },
    {
        "game_id": "G005",
        "game_name": "Apex Legends",
        "genre": "Battle Royale"
    },
    {
        "game_id": "G006",
        "game_name": "Fortnite",
        "genre": "Battle Royale"
    },
    {
        "game_id": "G007",
        "game_name": "Rocket League",
        "genre": "Sports"
    },
    {
        "game_id": "G008",
        "game_name": "Overwatch 2",
        "genre": "FPS"
    },
    {
        "game_id": "G009",
        "game_name": "Minecraft",
        "genre": "Sandbox"
    },
    {
        "game_id": "G010",
        "game_name": "Teamfight Tactics",
        "genre": "Strategy"
    }
]


for game in games:

    table.put_item(
        Item=game
    )

    print(
        f"Added: {game['game_name']}"
    )


print("Finished seeding games.")