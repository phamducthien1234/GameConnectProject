from pyspark.sql import SparkSession
from pyspark.sql.functions import count, desc, col

spark = SparkSession.builder \
    .appName("GameConnect Analytics") \
    .getOrCreate()

input_path = "s3://gameconnect-s3994124-data/analytics/player-games/AWSDynamoDB/01788659976725-d62d5b0e/data/"

raw_df = spark.read.json(input_path)

print("=== RAW DYNAMODB DATA ===")
raw_df.show(20, truncate=False)

df = raw_df.select(
    col("Item.user_id.S").alias("user_id"),
    col("Item.game_id.S").alias("game_id"),
    col("Item.role.S").alias("role"),
    col("Item.game_name.S").alias("game_name"),
    col("Item.rank.S").alias("rank"),
    col("Item.availability.S").alias("availability")
)

print("=== PLAYER GAME DATA ===")
df.show(20, truncate=False)

game_counts = (
    df.groupBy("game_name")
      .agg(count("*").alias("player_count"))
      .orderBy(desc("player_count"))
)

print("=== GAME POPULARITY ===")
game_counts.show(truncate=False)

output_path = "s3://gameconnect-s3994124-data/analytics/results/game-popularity/"

game_counts.write \
    .mode("overwrite") \
    .json(output_path)

spark.stop()