import json
import boto3
import os

dynamodb = boto3.resource("dynamodb")

TABLE_NAME = os.environ.get(
    "USERS_TABLE",
    "GameConnectUsers"
)

table = dynamodb.Table(TABLE_NAME)


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(body)
    }


def lambda_handler(event, context):

    method = event.get("requestContext", {}).get(
        "http", {}
    ).get("method")

    if method == "GET":
        result = table.scan(
            ProjectionExpression="user_id, username, #email, #region",
            ExpressionAttributeNames={
                "#email": "email",
                "#region": "region"
            }
        )

        return response(
            200,
            {
                "users": result.get("Items", [])
            }
        )

    return response(
        405,
        {
            "message": "Method not supported"
        }
    )