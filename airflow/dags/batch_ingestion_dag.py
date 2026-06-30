from datetime import datetime, timedelta
import json
import requests
import os
from airflow.decorators import dag, task
from google.cloud import storage

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2026, 6, 20), # Backfills historical data from June 20, 2026
    'retries': 2,
    'retry_delay': timedelta(minutes=2),
}


def upload_json_to_gcs(bucket_name, destination_blob_name, data):
    """Utility to serialize and upload Python dictionary/list as JSON to GCS"""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_string(
        data=json.dumps(data, ensure_ascii=False, indent=2),
        content_type='application/json'
    )
    print(f"Successfully uploaded to gs://{bucket_name}/{destination_blob_name}")
@dag(
    default_args=default_args,
    schedule_interval='@daily',
    catchup=True, # Automatically backfills all days from start_date to yesterday!
    max_active_runs=3,
    tags=['bangkok_urban', 'ingestion', 'batch'],
)

def bangkok_urban_batch_ingestion():
    @task()
    def ingest_traffy_complaints(**context):
        """Fetch daily complaints from BMA Traffy API via pagination offset loop"""
        execution_date = context['ds'] # Format: YYYY-MM-DD
        dt = datetime.strptime(execution_date, '%Y-%m-%d')
        
        bucket_name = os.environ.get('RAW_BUCKET_NAME')
        destination_blob = f"batch/year={dt.strftime('%Y')}/month={dt.strftime('%m')}/day={dt.strftime('%d')}/complaints.json"
        
        url = "https://publicapi.traffy.in.th/share/teamchadchart/search"
        offset = 0
        limit = 1000
        all_tickets = []
        
        while True:
            params = {
                'start': execution_date,
                'end': execution_date,
                'offset': offset,
                'limit': limit
            }
            print(f"Polling API for date {execution_date} with offset {offset}...")
            response = requests.get(url, params=params, timeout=30)
            
            # Traffy API returns status 201 Created on successful query
            if response.status_code not in [200, 201]:
                raise ValueError(f"Traffy API failed with status {response.status_code}: {response.text}")
                
            data = response.json()
            tickets = data.get("results", [])
            
            if not tickets:
                print(f"No more tickets returned. Pagination complete. Total tickets: {len(all_tickets)}")
                break
                
            all_tickets.extend(tickets)
            offset += len(tickets)
            
        # Upload all tickets for the day to GCS Data Lake (Bronze Layer)
        upload_json_to_gcs(bucket_name, destination_blob, all_tickets)
        return len(all_tickets)
    @task()
    def ingest_daily_weather(**context):
        """Fetch daily weather logs (Rainfall, Temp) for Bangkok from Open-Meteo"""
        execution_date = context['ds']
        dt = datetime.strptime(execution_date, '%Y-%m-%d')
        
        bucket_name = os.environ.get('RAW_BUCKET_NAME')
        destination_blob = f"weather/year={dt.strftime('%Y')}/month={dt.strftime('%m')}/day={dt.strftime('%d')}/weather.json"
        
        # Coordinates for Bangkok Central (13.7563, 100.5018)
        url = "https://archive-api.open-meteo.com/v1/archive"
        params = {
            'latitude': 13.7563,
            'longitude': 100.5018,
            'start_date': execution_date,
            'end_date': execution_date,
            'daily': 'rain_sum,temperature_2m_max,temperature_2m_min,relative_humidity_2m_max',
            'timezone': 'Asia/Bangkok'
        }
        
        print(f"Fetching weather logs from Open-Meteo for {execution_date}...")
        response = requests.get(url, params=params, timeout=15)
        if response.status_code != 200:
            raise ValueError(f"Open-Meteo failed with status {response.status_code}: {response.text}")
            
        weather_data = response.json()
        upload_json_to_gcs(bucket_name, destination_blob, weather_data)
    @task()
    def ingest_bangkok_gis():
        """Download static GeoJSON polygon boundaries for Bangkok Khets (Districts)"""
        bucket_name = os.environ.get('RAW_BUCKET_NAME')
        destination_blob = "static/bangkok_districts.geojson"
        
        # Check if the reference file already exists in GCS to avoid downloading it every run
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_blob)
        
        if blob.exists():
            print("Bangkok GIS reference GeoJSON already exists. Skipping download.")
            return
            
        print("Downloading static Bangkok GIS GeoJSON...")
        geojson_url = "https://raw.githubusercontent.com/pcrete/gsvloader-demo/master/geojson/Bangkok-districts.geojson"
        response = requests.get(geojson_url, timeout=20)
        
        if response.status_code != 200:
            raise ValueError(f"Failed to fetch GeoJSON from repository. Status: {response.status_code}")
            
        geojson_data = response.json()
        upload_json_to_gcs(bucket_name, destination_blob, geojson_data)
    # Set up task dependencies (Ingesting GIS runs once, weather and complaints runs daily)
    ingest_bangkok_gis() >> [ingest_traffy_complaints(), ingest_daily_weather()]
# Instantiate the DAG
bangkok_urban_batch_ingestion()