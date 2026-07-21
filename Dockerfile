FROM python:3.11-slim

# git is needed to install the ccl_simplesnappy dependency from source.
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Drop anything that may have slipped past .dockerignore.
RUN rm -rf venv __pycache__ *.log

RUN mkdir -p /tmp/cache_viewer_uploads

EXPOSE 5000

ENV FLASK_APP=app.py \
    HOST=0.0.0.0 \
    PORT=5000 \
    FLASK_DEBUG=0

CMD ["python", "app.py"]
