# 🏙️ Bangkok Urban Governance Data Pipeline

> An end-to-end Data Engineering project that ingests, transforms, and visualizes citizen complaint data across Bangkok — from raw streaming events to a live, interactive dashboard deployed on Google Cloud.

---

## 📖 Introduction

Every day, Bangkok residents submit thousands of complaints — flooded streets, broken streetlights, potholes, illegal dumping. But raw complaint data sitting in a database helps no one.

This project builds a **complete data pipeline** that turns messy, real-time complaint streams into actionable intelligence: clean data, privacy-safe views, weather-correlated analytics, and a live dashboard that city officials can use to allocate resources and respond faster.

---

## 🎯 What This Project Does

| Goal | How |
|------|-----|
| **Centralize** all urban complaints | Ingest via Google Pub/Sub → store in BigQuery |
| **Protect citizen privacy** | Mask addresses & round GPS coordinates before analyst access |
| **Discover causality** | Join complaints with Weather API + Thai Holiday calendar |
| **Enable real-time response** | Stream live alerts directly to the dashboard |
| **Automate everything** | CI/CD pipeline: `git push` → auto-deploy to Cloud Run |

---

## 🏗️ Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│  Pub/Sub     │────▶│  BigQuery     │────▶│  dbt         │────▶│  Streamlit   │
│  (Streaming) │     │  (Warehouse)  │     │  (Transform) │     │  (Dashboard) │
└─────────────┘     └──────────────┘     └─────────────┘     └──────────────┘
       │                    │                    │                    │
   Kafka-style         Raw Bronze           Silver → Gold        Cloud Run
   message queue       landing zone         Medallion Arch.      auto-deploy
```

This project follows a **Medallion Architecture** (Bronze → Silver → Gold):

### 🥉 Bronze — Raw Ingestion
- **`src/stream_producer.py`**: Simulates citizen complaints and publishes them to **Google Pub/Sub**
- **`src/stream_consumer.py`**: Subscribes to the Pub/Sub topic and writes raw data into **Google Cloud Storage** as Parquet files
- **`terraform/`**: All GCP infrastructure (BigQuery datasets, Pub/Sub topics, GCS buckets, Service Accounts) is provisioned via **Terraform** as Infrastructure-as-Code

### 🥈 Silver — Cleaning & Processing
- **`spark/apps/process_data.py`**: Apache Spark job that reads raw Parquet files, performs **NLP text classification** (using PyThaiNLP) to flag issues like flooding/potholes/garbage, and executes a **Spatial Join** against Bangkok district GeoJSON polygons to map each ticket to its district
- **`bangkok_urban_dbt/models/staging/`**: dbt models that cast raw types, handle nulls, and standardize column names

### 🥇 Gold — Enrichment & Privacy
- **`bangkok_urban_dbt/models/marts/core/`**: Core fact tables with clean, typed data
- **`bangkok_urban_dbt/models/marts/secure/mask_fact_complaints.sql`**: A privacy-safe view that truncates street addresses and rounds GPS to 3 decimal places (~100m precision)
- **`bangkok_urban_dbt/models/marts/fact_complaints_enriched.sql`**: Enriched dataset joining complaints with **Open-Meteo Weather API** data and **Thai Holiday Calendar** to enable causal analysis
- **`src/fetch_enrichment_data.py`**: Script that pulls weather data and holiday schedules from external APIs

### 📊 Dashboard — Visualization & Deployment
- **`streamlit/app.py`**: Interactive Streamlit dashboard with:
  - 🗺️ **District Choropleth Map** — "Which district has the most problems?"
  - 📍 **Ticket-Level Scatter Map** — Zoom to street level, filter by category
  - 📈 **Predictive Analytics** — Weather × complaints correlation, weekday vs weekend patterns
  - 🔴 **Live Pub/Sub Feed** — Real-time alerts as new tickets arrive
- **`Dockerfile`**: Containerized with the `uv` package manager for lightning-fast builds
- **`.github/workflows/deploy.yml`**: CI/CD pipeline — every `git push` auto-deploys to Cloud Run

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Infrastructure** | Terraform, Google Cloud Platform |
| **Ingestion** | Google Pub/Sub |
| **Storage** | Google BigQuery, Google Cloud Storage |
| **Processing** | Apache Spark, PyThaiNLP |
| **Transformation** | dbt (Data Build Tool) |
| **Enrichment** | Open-Meteo Weather API, Thai Holiday Calendar |
| **Dashboard** | Streamlit, Plotly, Mapbox |
| **Containerization** | Docker, uv |
| **CI/CD** | GitHub Actions → Google Cloud Run |
| **Language** | Python, SQL, HCL |

---

## 📁 Project Structure

```
thailand_governance_pipeline/
│
├── .github/workflows/
│   └── deploy.yml              # CI/CD: auto-deploy on git push
│
├── src/
│   ├── stream_producer.py      # Pub/Sub message publisher
│   ├── stream_consumer.py      # Pub/Sub subscriber → GCS writer
│   └── fetch_enrichment_data.py # Weather API & Holiday data fetcher
│
├── spark/apps/
│   └── process_data.py         # Spark NLP + Spatial Join pipeline
│
├── bangkok_urban_dbt/
│   └── models/
│       ├── staging/            # Silver: type casting, cleaning
│       └── marts/
│           ├── core/           # Gold: core fact tables
│           ├── secure/         # Gold: PII-masked views
│           └── fact_complaints_enriched.sql  # Weather + Holiday joins
│
├── streamlit/
│   └── app.py                  # Interactive dashboard
│
├── terraform/
│   ├── main.tf                 # GCP resource definitions
│   ├── variables.tf            # Configurable parameters
│   └── providers.tf            # GCP provider config
│
├── Dockerfile                  # uv-based container for Cloud Run
├── pyproject.toml              # Python dependencies (managed by uv)
├── docker-compose.yml          # Local Spark cluster setup
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) (`gcloud` CLI)
- A GCP project with BigQuery, Pub/Sub, and Cloud Storage enabled

### Run Locally

```bash
# 1. Clone the repository
git clone https://github.com/bombaepabo/traffy_pipeline.git
cd traffy_pipeline

# 2. Install all dependencies
uv sync

# 3. Authenticate with Google Cloud
gcloud auth application-default login

# 4. Launch the dashboard
uv run streamlit run streamlit/app.py
```

---

## ☁️ Deployment

### CI/CD (Automatic)
This project uses **GitHub Actions** for continuous deployment. Every push to the `master` branch automatically:
1. Builds the Docker container using `uv`
2. Pushes it to Google Artifact Registry
3. Deploys it to **Cloud Run** in `asia-southeast1` (Singapore)

No manual deployment commands needed — just `git push`!

### Manual Deploy
```bash
gcloud run deploy bangkok-dashboard \
  --source . \
  --region asia-southeast1 \
  --allow-unauthenticated \
  --memory 1024Mi
```

---

## 🔒 Security & Privacy

- **PII Masking**: Street addresses are truncated, GPS coordinates are rounded to 3 decimal places (~100m precision)
- **Keyless Authentication**: Cloud Run uses IAM Service Accounts — no credential files in containers
- **Secrets Management**: GCP Service Account keys are stored in GitHub Secrets, never committed to the repository
- **`.gitignore`**: All `.json` key files, `.env` files, and Terraform state files are excluded from version control
