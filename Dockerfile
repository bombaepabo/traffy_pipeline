# Use the official uv image built for Python 3.11
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

# Enable bytecode compilation for faster startup times
ENV UV_COMPILE_BYTECODE=1
ENV PYTHONUNBUFFERED=True

WORKDIR /app

# Step 1: Copy ONLY dependency files first (this caches the installation layer)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Step 2: Copy the rest of the project files
COPY . ./
# Sync again to install the project itself (if applicable)
RUN uv sync --frozen --no-dev

# Cloud Run injects the $PORT environment variable (usually 8080).
# We use 'uv run' to execute streamlit securely inside the isolated environment.
CMD uv run streamlit run streamlit/app.py --server.port=${PORT:-8080} --server.address=0.0.0.0
