# 🏙️ Bangkok Urban Governance Data Pipeline

## 📖 Introduction
Welcome to the **Bangkok Urban Governance Data Pipeline**! This project is a modern, end-to-end Data Engineering portfolio piece. It simulates a smart-city infrastructure designed to ingest, process, and analyze citizen complaints across Bangkok (similar to platforms like Traffy Fondue).

By combining real-time streaming, cloud data warehousing, complex data transformations, and an interactive front-end dashboard, this project demonstrates how data engineering can directly drive civic improvements.

---

## 🎯 Purpose
City governments receive thousands of complaints daily—ranging from flooded streets to broken streetlights. The purpose of this project is to:
1. **Centralize Data:** Create a single source of truth for all urban issues.
2. **Protect Citizen Privacy:** Mask Personally Identifiable Information (PII) before it reaches analysts.
3. **Discover Causality:** Go beyond basic counting by joining complaint data with external factors like Weather APIs and Holiday calendars to predict *why* problems happen.
4. **Enable Real-Time Action:** Stream new complaints directly to a dashboard so field workers can respond instantly.

---

## 🏗️ Architecture & Concepts (Step-by-Step)

This project follows a modern **Medallion Architecture** (Bronze ➔ Silver ➔ Gold), executing the following steps:

### Step 1: Real-Time Ingestion (Google Pub/Sub)
Citizen complaints are generated and published into a message queue (Google Pub/Sub / Kafka). This allows the system to handle massive spikes in traffic (e.g., during a severe rainstorm) without dropping any tickets.

### Step 2: Cloud Storage (Google BigQuery)
Raw data lands in Google BigQuery, our highly scalable, serverless Data Warehouse.

### Step 3: Data Transformation & Enrichment (dbt)
We use **dbt (Data Build Tool)** to write modular SQL transformations:
* **Staging (Silver):** Raw JSON/Parquet files are cast into proper types, nulls are handled, and boolean NLP flags (e.g., `has_flooding_issue`) are extracted.
* **Privacy Masking:** A secure view is created (`mask_fact_complaints.sql`) that truncates specific street addresses and rounds GPS coordinates to 3 decimal places. This ensures analysts can see neighborhood clusters without identifying individual citizens' homes.
* **Enrichment (Gold):** We use `UNPIVOT` logic (`CROSS JOIN UNNEST`) to properly categorize tickets that contain multiple issues. Then, we join the complaints with the **Open-Meteo Weather API** and a **Thai Holiday Calendar** to create a rich, multidimensional dataset (`fact_complaints_enriched`).

### Step 4: Interactive Dashboard (Streamlit & Plotly)
The final Gold data is served to a **Streamlit** web application featuring:
* **Geographical Mapping:** 
  * A District-level Choropleth map for high-level management overview.
  * An interactive, zoomable Scatter Map plotting individual masked tickets for field workers.
* **Predictive Causality Analytics:** Beautiful area charts, density heatmaps, and donut charts proving how heavy rainfall and weekends impact specific types of complaints.
* **Live Event Feed:** A direct connection to the Pub/Sub stream, popping up real-time alerts as citizens submit new tickets.

---

## 🛠️ Tech Stack
* **Language:** Python, SQL
* **Data Warehouse:** Google BigQuery
* **Streaming:** Google Pub/Sub (Kafka)
* **Transformation:** dbt (Data Build Tool)
* **Frontend UI:** Streamlit, Plotly, PyDeck
* **Deployment:** Google Cloud Run / Docker

---

## 🚀 How to Run Locally

This project uses [uv](https://docs.astral.sh/uv/) for lightning-fast Python dependency management.

1. **Install Dependencies:**
   ```bash
   uv sync
   ```
2. **Authenticate with Google Cloud:**
   ```bash
   gcloud auth application-default login
   ```
3. **Run the Dashboard:**
   ```bash
   uv run streamlit run streamlit/app.py
   ```

## ☁️ How to Deploy (Cloud Run)
This app is completely Dockerized and ready for keyless, secure deployment on GCP:
```bash
gcloud run deploy bangkok-dashboard \
  --source . \
  --region asia-southeast1 \
  --allow-unauthenticated \
  --service-account="your-service-account-email@your-project.iam.gserviceaccount.com" \
  --memory 1024Mi
```
