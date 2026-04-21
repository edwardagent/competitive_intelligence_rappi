# Rappi Competitive Intelligence System

Sistema automatizado de Competitive Intelligence para Rappi que recolecta datos de competidores y genera insights accionables.

## 🎯 Objetivo

Construir un MVP que permita monitorear precios, fees y tiempos de entrega de Rappi vs competencia (Uber Eats, DiDi Food) en México.

## 📁 Estructura del Proyecto

```
competitive_intelligence_rappi/
├── src/
│   ├── scrapers/          # Scrapers para cada plataforma
│   ├── analysis/          # Análisis de datos
│   └── utils/             # Utilidades generales
├── data/
│   ├── raw/              # Datos crudos del scraping
│   └── processed/        # Datos procesados
├── reports/              # Informes y visualizaciones
├── config/              # Configuraciones
├── requirements.txt     # Dependencias
└── README.md
```

## 🚀 Getting Started

### 1. Instalación de Dependencias

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Configuración

```bash
cp config/config.example.yaml config/config.yaml
# Editar config.yaml con las direcciones a scrapear
```

### 3. Ejecutar el Scraper

```bash
python src/scrapers/run_all.py
```

### 4. Generar Informe

```bash
python src/analysis/generate_report.py
```

## 📊 Plataformas a Scrapear

- [x] Rappi (baseline)
- [ ] Uber Eats
- [ ] DiDi Food

## 📝 Métricas a Recolectar

- Precio de productos (Big Mac, Combo McDonald's, etc.)
- Delivery Fee
- Service Fee
- Tiempo estimado de entrega
- Descuentos activos
- Precio final total

## 🛠️ Stack Tecnológico

- **Scraping:** Playwright, BeautifulSoup, Requests
- **Análisis:** Pandas, Matplotlib, Plotly
- **Dashboard:** Streamlit
- **Automatización:** Cron jobs, GitHub Actions

## ⚠️ Consideraciones Éticas

- Respetamos robots.txt cuando es posible
- Rate limiting razonable (1 request cada 2-5 segundos)
- User-Agents apropiados
- No sobrecargamos los servidores

## 📄 Licencia

MIT
