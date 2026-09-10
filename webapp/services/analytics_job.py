from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count, avg
import json
from flask import current_app

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
                results.append(
                    json.loads(line)
                )

    return results

spark = SparkSession.builder.appName("GameConnectAnalytics").getOrCreate()

INPUT_PATH = "s3://gameconnect-s3994124-data/analytics/events/*/*/*/*.json"
OUTPUT_PATH = "s3://gameconnect-s3994124-data/analytics/results/summary"

df = spark.read.json(INPUT_PATH)

print("Total events:", df.count())

# --------------------------------------------------
# 1. Event type counts
# --------------------------------------------------

event_counts = (
    df.groupBy("event_type")
    .agg(count("*").alias("total"))
    .orderBy(col("total").desc())
)

event_counts.write.mode("overwrite").json(
    OUTPUT_PATH + "/event_counts"
)

# --------------------------------------------------
# 2. Most searched games
# --------------------------------------------------

teammate_searches = df.filter(
    col("event_type") == "teammate_search"
)

game_search_counts = (
    teammate_searches
    .groupBy("data.game_name")
    .agg(count("*").alias("search_count"))
    .orderBy(col("search_count").desc())
)

game_search_counts.write.mode("overwrite").json(
    OUTPUT_PATH + "/game_search_counts"
)

# --------------------------------------------------
# 3. Average recommendation count
# --------------------------------------------------

average_recommendations = (
    teammate_searches
    .agg(
        avg("data.recommendation_count")
        .alias("average_recommendations")
    )
)

average_recommendations.write.mode("overwrite").json(
    OUTPUT_PATH + "/average_recommendations"
)

# --------------------------------------------------
# 4. Active users
# --------------------------------------------------

active_users = (
    df.select("user_id")
    .distinct()
)

active_users.write.mode("overwrite").json(
    OUTPUT_PATH + "/active_users"
)

# --------------------------------------------------
# 5. Session creation count
# --------------------------------------------------

session_events = df.filter(
    col("event_type") == "session_created"
)

session_count = (
    session_events
    .agg(count("*").alias("sessions_created"))
)

session_count.write.mode("overwrite").json(
    OUTPUT_PATH + "/session_count"
)

# --------------------------------------------------
# 6. Invitation count
# --------------------------------------------------

invitation_events = df.filter(
    col("event_type") == "invitation_sent"
)

invitation_count = (
    invitation_events
    .agg(count("*").alias("invitations_sent"))
)

invitation_count.write.mode("overwrite").json(
    OUTPUT_PATH + "/invitation_count"
)

spark.stop()