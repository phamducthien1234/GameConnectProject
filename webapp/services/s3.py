import boto3
import json
import uuid
from datetime import datetime, timezone
from flask import current_app

def get_s3_client():
    return boto3.client(
        "s3",
        region_name=current_app.config["AWS_REGION"]
    )


def upload_profile_image(file, user_id):
    s3 = get_s3_client()
    bucket = current_app.config["S3_BUCKET"]

    extension = file.filename.rsplit(".", 1)[-1].lower()

    object_key = (
        f"uploads/profile-images/"
        f"{user_id}.{extension}"
    )

    s3.upload_fileobj(
        file,
        bucket,
        object_key,
        ExtraArgs={
            "ContentType": file.content_type
        }
    )

    return object_key


def create_profile_image_url(object_key):
    if not object_key:
        return None

    s3 = get_s3_client()
    bucket = current_app.config["S3_BUCKET"]

    return s3.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": bucket,
            "Key": object_key
        },
        ExpiresIn=3600
    )


def save_analytics_event(event_type, user_id, data=None):
    s3 = get_s3_client()
    bucket = current_app.config["S3_BUCKET"]

    event_id = str(uuid.uuid4())

    now = datetime.now(timezone.utc)

    event = {
        "event_id": event_id,
        "event_type": event_type,
        "user_id": user_id,
        "timestamp": now.isoformat(),
        "data": data or {}
    }

    object_key = (
        f"analytics/events/"
        f"{now.strftime('%Y/%m/%d')}/"
        f"{event_id}.json"
    )

    s3.put_object(
        Bucket=bucket,
        Key=object_key,
        Body=json.dumps(event),
        ContentType="application/json"
    )

    return object_key

def read_json_folder(prefix):
    s3 = get_s3_client()
    bucket = current_app.config["S3_BUCKET"]

    response = s3.list_objects_v2(
        Bucket=bucket,
        Prefix=prefix
    )

    results = []

    for item in response.get("Contents", []):
        key = item["Key"]

        if not key.endswith(".json"):
            continue

        obj = s3.get_object(
            Bucket=bucket,
            Key=key
        )

        content = obj["Body"].read().decode("utf-8")

        for line in content.splitlines():
            if line.strip():
                results.append(json.loads(line))

    return results