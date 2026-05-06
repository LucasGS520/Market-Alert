FROM python:3.12-slim

# Deps do sistema para Playwright + lxml
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl gcc libpq-dev \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
    libpango-1.0-0 libcairo2 libasound2 libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -e .

# Instalar browser Chromium para Playwright
RUN playwright install chromium

COPY . .

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
