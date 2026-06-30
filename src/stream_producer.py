import os
import time
import json
from datetime import datetime, timezone
import requests
from google.cloud import pubsub_v1

# Load environment variables (fallback to defaults if run outside Docker)
PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "scrimterz-bangkok-urban")
TOPIC_NAME = "bangkok-urban-events"
STATE_FILE = "producer_state.json"
MAX_STATE_SIZE = 1000  # Number of recent ticket IDs to remember

def load_published_state():
    """Load previously published ticket IDs from local state file to survive restarts"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return set(json.load(f))
        except Exception as e:
            print(f"Error reading state file: {e}. Starting fresh.")
    return set()

def save_published_state(state):
    """Save the set of published ticket IDs to a local state file"""
    try:
        # Save only the last MAX_STATE_SIZE elements to keep state file bounded
        state_list = list(state)[-MAX_STATE_SIZE:]
        with open(STATE_FILE, "w") as f:
            json.dump(state_list, f)
    except Exception as e:
        print(f"Failed to save state file: {e}")

def main():
    # 1. Initialize Google Pub/Sub Publisher Client
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(PROJECT_ID, TOPIC_NAME)
    print(f"Streaming Producer active. Publishing to topic: {topic_path}")

    # Load deduplication state
    published_tickets = load_published_state()
    print(f"Loaded {len(published_tickets)} ticket IDs from state for deduplication.")
    url = "https://publicapi.traffy.in.th/share/teamchadchart/search"

    while True:
        try:
            # Query the current day's tickets (today in Bangkok / UTC+7)
            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            
            params = {
                "start": today_str,
                "end": today_str,
                "limit": 100,  # Grab the 100 most recent tickets
                "offset": 0
            }
            response = requests.get(url, params=params, timeout=10)
            if response.status_code in [200, 201]:
                data = response.json()
                tickets = data.get("results", [])
                new_tickets_count = 0
                
                for ticket in tickets:
                    ticket_id = ticket.get("ticket_id")
                    
                    # Deduplication check: only publish if we haven't sent this ID yet
                    if ticket_id and ticket_id not in published_tickets:
                        # Publish message to Google Pub/Sub
                        data_bytes = json.dumps(ticket, ensure_ascii=False).encode("utf-8")
                        
                        future = publisher.publish(topic_path, data_bytes)
                        message_id = future.result() # Wait for Pub/Sub confirmation
                        
                        # Update state
                        published_tickets.add(ticket_id)
                        new_tickets_count += 1
                if new_tickets_count > 0:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Published {new_tickets_count} new tickets.")
                    save_published_state(published_tickets)
            else:
                print(f"API Error: Status {response.status_code}")
        except Exception as e:
            print(f"Unexpected error in loop: {e}")
        # Sleep for 15 seconds before polling again
        time.sleep(15)


if __name__ == "__main__":
    main()