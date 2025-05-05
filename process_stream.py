from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, expr, when
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType, LongType, BooleanType
from pyspark.sql.functions import from_unixtime, to_timestamp
# --- Cấu hình ---
KAFKA_BROKER_URL = "kafka:9093"
KAFKA_TOPIC = "transactions"
ELASTICSEARCH_NODES = "elasticsearch" # Tên service của Elasticsearch trong Docker Compose
ELASTICSEARCH_PORT = "9200"
ELASTICSEARCH_INDEX = "transactions_index" # Tên index trong Elasticsearch
CHECKPOINT_LOCATION_ES = "/tmp/spark-checkpoint-es" # Thư mục checkpoint cho việc ghi vào ES

# --- Schema cho dữ liệu JSON từ Kafka ---
transaction_schema = StructType([
    StructField("transaction_id", StringType(), True),
    StructField("user_id", IntegerType(), True),
    StructField("amount", DoubleType(), True),
    StructField("currency", StringType(), True),
    StructField("timestamp", LongType(), True), # Giữ là LongType (milliseconds)
    StructField("location", StringType(), True),
    StructField("merchant_id", IntegerType(), True)
])

# --- Hàm xử lý chính ---
def process_transactions():
    print("Khởi tạo Spark Session...")

    # IMPORTANT: Điều chỉnh package versions cho phù hợp với phiên bản Spark và Elasticsearch/Kafka của bạn!
    # Ví dụ cho Spark 3.4, Kafka 2.8+, ES 7.x
    # Tham khảo: https://spark.apache.org/docs/latest/structured-streaming-kafka-integration.html
    # Tham khảo: https://www.elastic.co/guide/en/elasticsearch/hadoop/current/spark.html
    spark = SparkSession \
        .builder \
        .appName("RealtimeFraudDetection") \
        .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.0,org.elasticsearch:elasticsearch-spark-30_2.12:7.17.9") \
        .config("spark.sql.streaming.checkpointLocation", CHECKPOINT_LOCATION_ES) \
        .config("es.nodes", ELASTICSEARCH_NODES) \
        .config("es.port", ELASTICSEARCH_PORT) \
        .config("es.nodes.wan.only", "false") \
        .config("es.index.auto.create", "true") \
        .getOrCreate()

    spark.sparkContext.setLogLevel("WARN") # Giảm bớt log thừa
    print("Spark Session đã tạo.")

    # Đọc dữ liệu từ Kafka
    print(f"Đọc dữ liệu từ Kafka topic: {KAFKA_TOPIC}")
    kafka_stream_df = spark \
        .readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BROKER_URL) \
        .option("subscribe", KAFKA_TOPIC) \
        .option("startingOffsets", "latest") \
        .load()

    # Parse JSON data từ cột 'value' (dạng binary) của Kafka
    transaction_df = kafka_stream_df \
        .selectExpr("CAST(value AS STRING)") \
        .select(from_json(col("value"), transaction_schema).alias("data")) \
        .select("data.*")

    # Thêm cột timestamp chuẩn cho Elasticsearch và Grafana
    # Thêm cột timestamp chuẩn cho Elasticsearch và Grafana
    transaction_df = transaction_df.withColumn("@timestamp", 
        to_timestamp(from_unixtime(col("timestamp")/1000)))

    # --- Áp dụng Rule-based Detection Đơn Giản ---
    # Ví dụ: Đánh dấu giao dịch có giá trị > 30,000 là nghi ngờ
    RULE_THRESHOLD = 30000.0
    processed_df = transaction_df.withColumn(
        "is_suspicious_rule",
        when(col("amount") > RULE_THRESHOLD, True).otherwise(False)
    )

    # --- Ghi kết quả vào Elasticsearch ---
    print(f"Ghi dữ liệu vào Elasticsearch index: {ELASTICSEARCH_INDEX}")
    es_write_query = processed_df \
        .writeStream \
        .format("org.elasticsearch.spark.sql") \
        .outputMode("append") \
        .option("es.resource", f"{ELASTICSEARCH_INDEX}/_doc") \
        .option("es.mapping.id", "transaction_id") \
        .option("checkpointLocation", CHECKPOINT_LOCATION_ES) \
        .start()

    # (Tùy chọn) Ghi ra console để debug
    # console_query = processed_df \
    #     .writeStream \
    #     .outputMode("append") \
    #     .format("console") \
    #     .option("truncate", "false") \
    #     .start()

    print("Streaming query đã bắt đầu. Đang chờ termination...")
    # Chờ query kết thúc (sẽ không bao giờ kết thúc trong streaming)
    es_write_query.awaitTermination()
    # console_query.awaitTermination() # Nếu chạy console query

if __name__ == "__main__":
    process_transactions()