# MCP Catálogo Bioquímica.cl

Servidor MCP que expone el catálogo de productos de [Bioquímica.cl](https://bioquimica.cl) como herramienta para modelos de lenguaje (Claude y otros clientes MCP compatibles).

Permite consultar el catálogo en lenguaje natural para evaluar licitaciones de Mercado Público, obtener precios de referencia y verificar stock disponible.

---

## Cómo funciona

El servidor expone una sola herramienta MCP: `consultar_compatibilidad_catalogo`.

### Flujo interno

```
Query del LLM
    │
    ▼
catalog.py ── GET /api/v1/stock/catalog (caché 15 min)
    │
    ▼
search.py ── fuzzy search sobre: nombre + woo_description
    │           (especificaciones técnicas desde WooCommerce)
    ▼
Retorna JSON con candidatos ordenados por afinidad técnica
```

### Búsqueda fuzzy

El score de cada producto combina:
- **60% token overlap** — cuántos términos del query aparecen en el texto del producto
- **40% sequence match** — similitud de secuencia completa (difflib)

El campo `woo_description` contiene la ficha técnica completa de WooCommerce (objetivos ópticos, NA, dimensiones, material, capacidad, etc.), lo que permite hacer matching técnico real, no solo por nombre.

---

## Herramienta disponible

### `consultar_compatibilidad_catalogo`

```
item_solicitado: str        # Nombre o descripción técnica del producto
limite_resultados: int = 3  # Máximo de candidatos a retornar
```

**Respuesta:**

```json
{
  "resultados": [
    {
      "sku": "EE000075",
      "nombre_comercial": "Microscopio Trinocular 1000x con Objetivos Plan",
      "especificaciones_tecnicas": "Cabezal trinocular 360°, objetivos acromáticos 4X 10X 40X 100X corrección al infinito, condensador NA 1.25, LED Koehler 3W, 220V...",
      "precio_lista_neto": 840000.0,
      "disponible_para_venta": true
    }
  ],
  "total_encontrados": 1,
  "mensaje": ""
}
```

`precio_lista_neto` es precio neto sin IVA en CLP. Precio con IVA = `precio × 1.19`.

---

## Configuración

### Variables de entorno

Copiar `.env.example` a `.env` y completar:

```env
# API del catálogo (Integraciones-BQ)
CATALOG_API_URL=https://TU-DOMINIO/api/v1/stock/catalog
CATALOG_API_KEY=TU_API_KEY
CACHE_TTL_SECONDS=900

# Solo para despliegue remoto
MCP_API_KEY=TU_CLAVE_SECRETA_MCP
MCP_TRANSPORT=stdio
PORT=8000
```

| Variable | Descripción | Default |
|---|---|---|
| `CATALOG_API_URL` | Endpoint del catálogo en Integraciones-BQ | — |
| `CATALOG_API_KEY` | API key para el endpoint | — |
| `CACHE_TTL_SECONDS` | Tiempo de vida del caché en memoria | `900` |
| `MCP_API_KEY` | Clave para proteger el servidor MCP remoto | sin auth |
| `MCP_TRANSPORT` | `stdio` (local) o `sse` (remoto) | `stdio` |
| `PORT` | Puerto del servidor SSE | `8000` |

---

## Uso local (Claude Code / Claude Desktop)

### Requisitos

```bash
python3 -m pip install -e .
```

### Configuración en `.mcp.json` (proyecto)

```json
{
  "mcpServers": {
    "catalogo-bioquimica": {
      "type": "stdio",
      "command": "python3",
      "args": ["server.py"],
      "env": {
        "PYTHONPATH": "/ruta/absoluta/al/proyecto"
      }
    }
  }
}
```

---

## Despliegue en DigitalOcean App Platform

### 1. Preparar repositorio

```bash
git init
git add .
git commit -m "initial commit"
git remote add origin https://github.com/TU-ORG/mcp-catalogo-bq.git
git push -u origin main
```

### 2. Crear el app en DO

1. DO App Platform → **New App** → From GitHub → seleccionar el repo
2. DO detecta el `Dockerfile` automáticamente
3. Configurar variables de entorno en la UI:

| Variable | Valor |
|---|---|
| `CATALOG_API_URL` | URL de Integraciones-BQ |
| `CATALOG_API_KEY` | API key del catálogo |
| `MCP_API_KEY` | Clave secreta (generar con `openssl rand -hex 32`) |
| `MCP_TRANSPORT` | `sse` |

4. Health check path: `/health`

### 3. URL resultante

```
https://TU-APP.ondigitalocean.app/sse
```

---

## Conexión con Claude.ai

### Desktop (recomendado)

Settings → Developer → MCP Servers → Add:

```json
{
  "url": "https://TU-APP.ondigitalocean.app/sse",
  "headers": {
    "Authorization": "Bearer TU_MCP_API_KEY"
  }
}
```

### Web (claude.ai)

Settings → Integrations → Add MCP Server → misma URL y header.

---

## Estructura del proyecto

```
mcp-catalogo-bq/
├── server.py          # Entrypoint — define herramienta MCP y servidor SSE
├── src/
│   ├── catalog.py     # Fetch del catálogo con caché en memoria
│   ├── search.py      # Búsqueda fuzzy + limpieza de woo_description
│   └── schemas.py     # Modelos Pydantic (CatalogItem, SearchResult)
├── Dockerfile         # Para despliegue en DO App Platform
├── pyproject.toml     # Dependencias del proyecto
└── .env.example       # Plantilla de variables de entorno
```

---

## Prerequisitos en Integraciones-BQ

El campo `woo_description` en el endpoint `/api/v1/stock/catalog` debe estar activo. Requiere:

```bash
# Ejecutar una vez en el servidor de Integraciones-BQ
docker compose exec app alembic upgrade head
```

Luego hacer un `POST /api/v1/stock/sap` para sincronizar las descripciones desde WooCommerce.
