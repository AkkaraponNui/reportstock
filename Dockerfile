# Portable image for hosts that build from a Dockerfile: Hugging Face Spaces
# (Docker SDK), Render, Fly.io, Railway, or your own machine.
#
# Streamlit Community Cloud does not use this file. It installs from
# requirements.txt directly.
#
#   docker build -t reportstock .
#   docker run -p 8501:8501 -e REPORTSTOCK_UA="you you@example.com" reportstock

FROM python:3.11-slim

# Hugging Face Spaces runs the container as uid 1000 and expects port 7860.
# Other hosts inject $PORT. The entrypoint below handles both.
ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app

# Dependencies first, so a code change does not reinstall the whole tree.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY tools/ ./tools/
COPY ui/ ./ui/
COPY config/ ./config/
COPY app.py ./
COPY .streamlit/ ./.streamlit/

# The snapshot tree. On a host with an ephemeral filesystem this starts empty
# after every restart and refills on demand, which turns the dated snapshots from
# an audit trail into a cache. Mount a volume here if you need them to survive.
RUN mkdir -p /app/data/raw /app/data/news /app/data/filings \
             /app/data/scores /app/data/reports \
    && chmod -R 777 /app/data

EXPOSE 7860 8501

# $PORT wins when the host sets one, then 7860 for Spaces, then 8501 locally.
CMD ["sh", "-c", "streamlit run app.py --server.port=${PORT:-7860} --server.address=0.0.0.0"]
