import os
import time
import json
from datetime import datetime, timezone
from google.cloud import pubsub_v1
from google.cloud import storage

# Load environment variables
PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "scrimterz-bangkok-urban")
SUBSCRIPTION_NAME = "bangkok-urban-events-sub"
BUCKET_NAME = os.environ.get("RAW_BUCKET_NAME", "scrimterz-bangkok-urban-raw-lake")

BATCH_TIMEOUT_SEC = 30  # Flush buffer to GCS every 30 seconds
MAX_BATCH_SIZE = 10     # Or when we accumulate 10 messages

def main():
    # 1. Initialize Pub/Sub Subscriber Client
    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_NAME)
    
    # 2. Initialize GCS Storage Client
    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)
    
    print(f"Streaming Consumer active. Subscribed to: {subscription_path}")
    print(f"Writing micro-batches to GCS bucket: {BUCKET_NAME}")
    
    buffer = []
    ack_ids = []
    last_flush_time = time.time()
    
    while True:
        try:
            # Pull up to 10 messages at a time from Pub/Sub
            response = subscriber.pull(
                request={
                    "subscription": subscription_path,
                    "max_messages": 10,
                },
                timeout=5.0
            )
            
            for received_message in response.received_messages:
                message_data = json.loads(received_message.message.data.decode("utf-8"))
                buffer.append(message_data)
                ack_ids.append(received_message.ack_id)
                
            # Check if we should flush our buffer to GCS
            time_since_flush = time.time() - last_flush_time
            if (len(buffer) >= MAX_BATCH_SIZE) or (len(buffer) > 0 and time_since_flush >= BATCH_TIMEOUT_SEC):
                
                # Generate Hive-style partition path: stream/year=YYYY/month=MM/day=DD/hour=HH/
                now = datetime.now(timezone.utc)
                partition_path = f"stream/year={now.strftime('%Y')}/month={now.strftime('%m')}/day={now.strftime('%d')}/hour={now.strftime('%H')}"
                filename = f"events_{int(time.time())}.json"
                gcs_path = f"{partition_path}/{filename}"
                
                # Upload the micro-batch to GCS
                blob = bucket.blob(gcs_path)
                blob.upload_from_string(
                    data=json.dumps(buffer, ensure_ascii=False, indent=2),
                    content_type="application/json"
                )
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Flushed {len(buffer)} events to GCS: {gcs_path}")
                
                # Acknowledge messages in Pub/Sub so they are cleared from the queue
                subscriber.acknowledge(
                    request={
                        "subscription": subscription_path,
                        "ack_ids": ack_ids,
                    }
                )
                
                # Reset our buffer and timer
                buffer.clear()
                ack_ids.clear()
                last_flush_time = time.time()
                
        except Exception as e:
            # Ignore standard timeouts from empty subscription pulls to keep logs clean
            if "DeadlineExceeded" not in str(e) and "504 Gateway Timeout" not in str(e):
                print(f"Error in consumer loop: {e}")
                
        time.sleep(1)

if __name__ == "__main__":
    main()