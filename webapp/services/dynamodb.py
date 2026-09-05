import boto3
from flask import current_app


def get_dynamodb():
    return boto3.resource(
        "dynamodb",
        region_name=current_app.config["AWS_REGION"]
    )


def get_table(table_name):
    dynamodb = get_dynamodb()
    return dynamodb.Table(table_name)