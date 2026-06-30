# =======================================================
# 1. Google Cloud Storage (Data Lakehouse Buckets)
# =======================================================
# Raw Bucket (Bronze Layer) - Stores raw, unstructured JSON
resource "google_storage_bucket" "raw_bucket" {
  name          = "${var.project_id}-raw-lake"
  location      = var.region
  storage_class = var.storage_class
  force_destroy = true # Deletes contents if we destroy the bucket (handy for testing)
  uniform_bucket_level_access = true
  # Auto-cleanup rule: delete files after 30 days to guarantee $0 cost
  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age = 30
    }
  }
}
# Silver Bucket (Staging Layer) - Stores cleaned Parquet files from Spark
resource "google_storage_bucket" "silver_bucket" {
  name          = "${var.project_id}-silver-lake"
  location      = var.region
  storage_class = var.storage_class
  force_destroy = true
  uniform_bucket_level_access = true
  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age = 30
    }
  }
}
# =======================================================
# 2. BigQuery Datasets (Analytical Data Warehouse)
# =======================================================
# Staging Dataset (Bronze/Silver External Reference)
resource "google_bigquery_dataset" "staging_dataset" {
  dataset_id                 = "raw_staging"
  friendly_name              = "Raw Staging Tables"
  description                = "Bronze/Silver schemas mapped to GCS storage layers"
  location                   = var.region
  delete_contents_on_destroy = true
}
# Production Warehouse Dataset (Gold)
resource "google_bigquery_dataset" "gold_dataset" {
  dataset_id                 = "warehouse_gold"
  friendly_name              = "Analytical Gold Warehouse"
  description                = "Gold layer hosting final Facts, Dimensions, and Masked Views"
  location                   = var.region
  delete_contents_on_destroy = true
}
# =======================================================
# 3. Pub/Sub (Real-Time Messaging Broker)
# =======================================================
# Pub/Sub Topic to receive live city complaints
resource "google_pubsub_topic" "stream_topic" {
  name = "bangkok-urban-events"
}
# Pub/Sub Pull Subscription for our Python/Spark listener
resource "google_pubsub_subscription" "pull_subscription" {
  name  = "bangkok-urban-events-sub"
  topic = google_pubsub_topic.stream_topic.name
  message_retention_duration = "604800s" # Keep unacknowledged messages for 7 days
  retain_acked_messages      = false
  ack_deadline_seconds       = 20
}
# =======================================================
# 4. BigQuery External Tables (Data Lakehouse)
# =======================================================
# External table pointing to the Silver Parquet Complaints
resource "google_bigquery_table" "ext_complaints" {
  dataset_id = google_bigquery_dataset.staging_dataset.dataset_id
  table_id   = "ext_complaints"
  
  external_data_configuration {
    autodetect    = true
    source_format = "PARQUET"
    # Points to any file in the complaints folder of our silver bucket
    source_uris   = ["gs://${google_storage_bucket.silver_bucket.name}/complaints/*"]
  }
}
# External table pointing to the Silver Parquet Weather
resource "google_bigquery_table" "ext_weather" {
  dataset_id = google_bigquery_dataset.staging_dataset.dataset_id
  table_id   = "ext_weather"
  
  external_data_configuration {
    autodetect    = true
    source_format = "PARQUET"
    source_uris   = ["gs://${google_storage_bucket.silver_bucket.name}/weather/*"]
  }
}