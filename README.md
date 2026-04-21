# Rappi Competitive Intelligence System

Sistema automatizado de Competitive Intelligence para Rappi que recolecta datos de competidores y genera insights accionables.

## 🎯 Objetivo

Construir un MVP que permita monitorear precios, fees y tiempos de entrega de Rappi vs competencia (Uber Eats, DiDi Food) en México.

---

## 🐳 Uso con Docker (Recomendado)

### Requisitos
- Docker instalado
- Docker Compose

### Quick Start

```bash
# 1. Ir a la carpeta del proyecto
cd competitive_intelligence_rappi

# 2. Construir y ejecutar el scraper
docker compose -f container/docker-compose.yml up scraper

# 3. Ver los datos generados (en data/raw/)
```

### Servicios Disponibles

| Servicio | Descripción | Comando |
|----------|-------------|---------|
| `scraper` | Ejecuta todos los scrapers | `docker compose -f container/docker-compose.yml up scraper` |
| `analysis` | Genera informe de insights | `docker compose -f container/docker-compose.yml up analysis` |
| `dashboard` | Dashboard Streamlit (puerto 8501) | `docker compose -f container/docker-compose.yml up dashboard` |
| `jupyter` | Notebook Jupyter (puerto 8888) | `docker compose --profile jupyter up` |

### Ejemplo Completo

```bash
# Ejecutar scraper y análisis
docker compose -f container/docker-compose.yml up scraper analysis

# Abrir dashboard después
docker compose -f container/docker-compose.yml up dashboard
```

---

## 📁 Estructura del Proyecto

```
competitive_intelligence_rappi/
├── container/
│   ├── Dockerfile           # Imagen Docker
│   ├── docker-compose.yml  # Orquestación de servicios
│   └── requirements.txt     # Dependencias Python
├── config/
│   └── config.yaml         # Configuración (direcciones, productos)
├── src/
│   ├── scrapers/           # Scrapers para cada plataforma
│   │   ├── base_scraper.py
│   │   ├── rappi_scraper.py
│   │   └── run_all.py
│   ├── analysis/           # Análisis de datos
│   └── utils/
├── data/
│   ├── raw/               # Datos crudos del scraping
│   └── processed/         # Datos procesados
├── reports/               # Informes y visualizaciones
├── requirements.txt       # Dependencias (fuera de container)
└── README.md
```

---

## ⚙️ Configuración

Editar `config/config.yaml` para personalizar:

### Direcciones a Scrapear
```yaml
addresses:
  - name: "Polanco"
    zip_code: "11560"
    zone_type: "upscale"
```

### Productos de Referencia
```yaml
reference_products:
  fast_food:
    - name: "Big Mac"
      brand: "McDonald's"
```

---

## 🚀 Getting Started (Desarrollo Local)

### 1. Clonar el repositorio
```bash
git clone <repo-url>
cd competitive_intelligence_rappi
```

### 2. Crear .env (opcional)
```bash
cp .env.example .env
```

### 3. Ejecutar con Docker
```bash
docker compose -f container/docker-compose.yml up --build
```

---

## 📊 Plataformas a Scrapear

- [x] Rappi (baseline) - Implementado
- [ ] Uber Eats - Por implementar
- [ ] DiDi Food - Por implementar

## 📝 Métricas a Recolectar

- [x] Precio de productos
- [x] Delivery Fee
- [ ] Service Fee
- [ ] Tiempo estimado de entrega
- [ ] Descuentos activos
- [ ] Disponibilidad
- [x] Precio final total

## 🛠️ Stack Tecnológico

- **Scraping:** Playwright, BeautifulSoup, Requests
- **Análisis:** Pandas, Matplotlib, Plotly
- **Dashboard:** Streamlit
- **Contenedores:** Docker, Docker Compose

---

## ⚠️ Consideraciones Éticas

- Respetamos robots.txt cuando es posible
- Rate limiting razonable (1 request cada 2-5 segundos)
- User-Agents apropiados
- No sobrecargamos los servidores

---

## 📄 Licencia

MIT
