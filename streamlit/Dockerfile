# Use the official lightweight Python image
FROM python:3.11-slim

# Allow statements and log messages to immediately appear in the Knative logs
ENV PYTHONUNBUFFERED True

# Copy local code to the container image
ENV APP_HOME /app
WORKDIR $APP_HOME
COPY . ./

# Install production dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run the web service on container startup.
# Cloud Run injects the $PORT environment variable (usually 8080).
# We pass this port directly to Streamlit.
CMD streamlit run app.py --server.port=${PORT:-8080} --server.address=0.0.0.0
