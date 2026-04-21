# Competitive Intelligence Rappi - Dockerfile
# Usamos Python 3.12 para compatibilidad con Playwright

FROM python:3.12-slim

# Metadata
LABEL maintainer="Edward Sandoval"
LABEL description="Competitive Intelligence System for Rappi"

# Configuración de locale para español
ENV LANG=es_MX.UTF-8 \
    LC_ALL=es_MX.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Instalar dependencias del sistema para Playwright y Selenium
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    curl \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de trabajo
WORKDIR /app

# Copiar requirements primero para aprovechar cache de Docker
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Instalar Playwright browsers (chromium)
RUN playwright install chromium && \
    playwright install-deps chromium

# Copiar código de la aplicación
COPY .. .

# Crear directorios para datos
RUN mkdir -p /app/data/raw /app/data/processed /app/reports

# Exponer puerto para Streamlit (dashboard)
EXPOSE 8501

# Comando por defecto: ejecutar el scraper
CMD ["python", "src/scrapers/run_all.py"]
