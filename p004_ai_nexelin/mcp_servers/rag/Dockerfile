FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev build-essential && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /app/requirements.txt
COPY mcp_servers/rag/requirements.txt /app/mcp_requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r mcp_requirements.txt
COPY . /app
ENV DJANGO_SETTINGS_MODULE=MASTER.settings
EXPOSE 8010
CMD ["python", "-m", "mcp_servers.rag.server"]
