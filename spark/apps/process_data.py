import os
import sys

# Set HOME and PyThaiNLP directory to /tmp
os.environ["HOME"] = "/tmp"
os.environ["PYTHAINLP_DATA_DIR"] = "/tmp/pythainlp-data"

# Self-bootstrap: install required python libraries on the Spark cluster nodes
print("Installing Python dependencies on Spark node...")
os.system(f"{sys.executable} -m pip install --no-cache-dir pythainlp shapely geojson google-cloud-storage grpcio")

# Force Python to load our newly installed libraries FIRST by inserting them at the top of sys.path
user_site_paths = [
    "/.local/lib/python3.11/site-packages",
    os.path.expanduser("~/.local/lib/python3.11/site-packages")
]
for path in user_site_paths:
    if path not in sys.path:
        sys.path.insert(1, path)

# NOW import the installed libraries
import json
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, udf, explode, lit
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, BooleanType, IntegerType, ArrayType, TimestampType
from shapely.geometry import shape, Point
from pythainlp.tokenize import word_tokenize
from google.cloud import storage

# Retrieve bucket names from environment variables
PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "scrimterz-bangkok-urban")
RAW_BUCKET = os.environ.get("RAW_BUCKET_NAME", "scrimterz-bangkok-urban-raw-lake")
SILVER_BUCKET = os.environ.get("SILVER_BUCKET_NAME", "scrimterz-bangkok-urban-silver-lake")

def build_spark_session():
    """Build Spark Session configured to read/write directly from GCS using Service Account"""
    # Notice we removed the `.config("spark.jars.packages", ...)` here because we are using the Uber-JAR!
    return SparkSession.builder \
        .appName("BangkokUrbanDataProcessing") \
        .config("spark.hadoop.fs.gs.impl", "com.google.cloud.hadoop.fs.gcs.GoogleHadoopFileSystem") \
        .config("spark.hadoop.fs.gs.auth.service.account.enable", "true") \
        .config("spark.hadoop.fs.gs.auth.service.account.json.keyfile", "/opt/bitnami/spark/credentials.json") \
        .config("spark.executorEnv.PYTHAINLP_DATA_DIR", "/tmp/pythainlp-data") \
        .config("spark.executorEnv.HOME", "/tmp") \
        .getOrCreate()

# =======================================================
# 1. Load Geospatial Boundaries & Define Spatial UDF
# =======================================================
def load_district_polygons():
    """Load Bangkok district boundary GeoJSON from GCS Raw bucket"""
    print("Loading GIS boundary GeoJSON from GCS...")
    storage_client = storage.Client.from_service_account_json("/opt/bitnami/spark/credentials.json")
    bucket = storage_client.bucket(RAW_BUCKET)
    blob = bucket.blob("static/bangkok_districts.geojson")
    geojson_content = blob.download_as_text()
    
    geojson_data = json.loads(geojson_content)
    districts = []
    
    for feature in geojson_data.get("features", []):
        properties = feature.get("properties", {})
        district_name = properties.get("name", properties.get("dname", "Unknown"))
        district_shape = shape(feature.get("geometry"))
        districts.append((district_name, district_shape))
        
    return districts

# =======================================================
# 2. Define PySpark UDFs (User Defined Functions)
# =======================================================

# Thai NLP UDF: parses Thai text to check for specific categories
def extract_issue_flags(description):
    if not description:
        return (False, False, False, False)
    
    # Tokenize the description into Thai words
    words = set(word_tokenize(description, engine="newmm"))
    
    # Check for keyword matches
    has_flooding = any(w in words for w in ["น้ำท่วม", "ระบาย", "น้ำขัง", "ท่วม"])
    has_pothole = any(w in words for w in ["หลุม", "ขรุขระ", "พัง", "ถนนทรุด", "บ่อ"])
    has_dark_street = any(w in words for w in ["มืด", "ไฟดับ", "หลอดไฟ", "ไม่มีไฟ", "ไฟทาง"])
    has_garbage = any(w in words for w in ["ขยะ", "เหม็น", "กองขยะ", "ไม่เก็บ"])
    
    return (has_flooding, has_pothole, has_dark_street, has_garbage)

nlp_schema = StructType([
    StructField("has_flooding", BooleanType(), True),
    StructField("has_pothole", BooleanType(), True),
    StructField("has_dark_street", BooleanType(), True),
    StructField("has_garbage", BooleanType(), True),
])

def main():
    spark = build_spark_session()
    
    # Pre-download the PyThaiNLP corpus in the driver so parallel workers don't collide
    print("Pre-caching PyThaiNLP dictionaries...")
    word_tokenize("ทดสอบ", engine="newmm")
    
    # Load and broadcast the district shapes to all executor nodes
    districts = load_district_polygons()
    broadcast_districts = spark.sparkContext.broadcast(districts)
    
    # Spatial UDF: Check which district polygon a point falls inside
    def find_district(lon, lat):
        if lon is None or lat is None:
            return "Unknown"
        point = Point(lon, lat)
        for name, shape_polygon in broadcast_districts.value:
            if shape_polygon.contains(point):
                return name
        return "Unknown"
        
    find_district_udf = udf(find_district, StringType())
    nlp_udf = udf(extract_issue_flags, nlp_schema)
    
    # =======================================================
    # 3. Process Complaints Batch Data
    # =======================================================
    print("Reading raw complaints from GCS...")
    raw_complaints_path = f"gs://{RAW_BUCKET}/batch/*/*/*/*.json"
    
    df_complaints = spark.read.json(raw_complaints_path, multiLine=True)
    
    # Clean coordinate arrays, convert timestamps, and extract columns
    df_clean_complaints = df_complaints \
        .withColumn("lon", col("coords").getItem(0).cast(DoubleType())) \
        .withColumn("lat", col("coords").getItem(1).cast(DoubleType())) \
        .withColumn("parsed_timestamp", col("timestamp").cast(TimestampType())) \
        .withColumn("rating_star", col("star").cast(IntegerType())) \
        .withColumn("reopen_count", col("count_reopen").cast(IntegerType())) \
        .select(
            col("ticket_id").alias("ticket_id"),
            col("type").alias("category"),
            col("description").alias("description"),
            col("address").alias("address"),
            col("parsed_timestamp").alias("timestamp"),
            col("state").alias("state"),
            col("rating_star").alias("rating_star"),
            col("reopen_count").alias("reopen_count"),
            col("lon"),
            col("lat")
        )
        
    # Apply Spatial Join and NLP UDFs
    df_enriched_complaints = df_clean_complaints \
        .withColumn("district_khet", find_district_udf(col("lon"), col("lat"))) \
        .withColumn("nlp_flags", nlp_udf(col("description"))) \
        .select(
            "*",
            col("nlp_flags.has_flooding").alias("has_flooding_issue"),
            col("nlp_flags.has_pothole").alias("has_pothole_issue"),
            col("nlp_flags.has_dark_street").alias("has_dark_street_issue"),
            col("nlp_flags.has_garbage").alias("has_garbage_issue")
        ).drop("nlp_flags")
        
    # Write optimized Parquet files to GCS Silver Zone
    silver_complaints_path = f"gs://{SILVER_BUCKET}/complaints"
    print(f"Writing enriched complaints to Silver Zone: {silver_complaints_path}")
    df_enriched_complaints.write \
        .mode("overwrite") \
        .parquet(silver_complaints_path)

    # =======================================================
    # 4. Process Weather Data
    # =======================================================
    print("Reading raw weather from GCS...")
    raw_weather_path = f"gs://{RAW_BUCKET}/weather/*/*/*/*.json"
    
    df_weather = spark.read.json(raw_weather_path, multiLine=True)
    
    # Open-Meteo returns nested daily arrays, we unpack (explode) them
    df_flat_weather = df_weather \
        .select(
            explode(col("daily.time")).alias("date"),
            col("daily.rain_sum").getItem(0).cast(DoubleType()).alias("rainfall_mm"),
            col("daily.temperature_2m_max").getItem(0).cast(DoubleType()).alias("temp_max_c"),
            col("daily.temperature_2m_min").getItem(0).cast(DoubleType()).alias("temp_min_c"),
            col("daily.relative_humidity_2m_max").getItem(0).cast(DoubleType()).alias("humidity_max")
        )
        
    silver_weather_path = f"gs://{SILVER_BUCKET}/weather"
    print(f"Writing processed weather to Silver Zone: {silver_weather_path}")
    df_flat_weather.write \
        .mode("overwrite") \
        .parquet(silver_weather_path)
        
    print("PySpark Job Completed Successfully!")

if __name__ == "__main__":
    main()