import os
import uvicorn
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route
from src.catalog import get_catalog
from src.search import buscar
from src.schemas import SearchResult

_MCP_API_KEY = os.environ.get("MCP_API_KEY", "")

mcp = FastMCP(
    name="catalogo-bioquimica",
    host="0.0.0.0",
    instructions="""
    Servidor MCP del catálogo de productos de Bioquímica CL.

    Úsame para evaluar si Bioquímica CL puede participar en licitaciones
    de Mercado Público o Compras Ágiles, obtener precios base de referencia
    y verificar disponibilidad de stock antes de postular.

    El catálogo incluye reactivos químicos, equipos de laboratorio, materiales
    educativos de ciencias y consumibles para laboratorio.
    """,
)


@mcp.tool()
async def consultar_compatibilidad_catalogo(
    item_solicitado: str,
    limite_resultados: int = 3,
) -> str:
    """
    Busca en el catálogo interno de Bioquímica CL los productos con mayor
    afinidad técnica al ítem solicitado en una licitación de Mercado Público
    o Compra Ágil.

    Usa búsqueda fuzzy sobre el nombre comercial del producto. Retorna los
    candidatos con mayor compatibilidad técnica, su precio neto de lista en
    CLP (sin IVA) y disponibilidad de stock para venta.

    Úsala cuando necesites:
    - Evaluar si Bioquímica CL puede participar en una licitación
    - Obtener precio base para construir una oferta competitiva
    - Confirmar disponibilidad de stock antes de postular

    Args:
        item_solicitado: Nombre o descripción técnica del producto que el
                         Estado está solicitando. Puede incluir errores
                         ortográficos o abreviaciones.
        limite_resultados: Cantidad máxima de candidatos a retornar (default 3).

    Returns:
        JSON con array de productos candidatos ordenados por afinidad técnica.
    """
    try:
        items = await get_catalog()
    except Exception as e:
        result = SearchResult(
            resultados=[],
            total_encontrados=0,
            mensaje=f"Error al cargar el catálogo: {e}",
        )
        return result.model_dump_json()

    encontrados = buscar(item_solicitado, items, limite=limite_resultados)

    if not encontrados:
        result = SearchResult(
            resultados=[],
            total_encontrados=0,
            mensaje=f"No se encontraron productos compatibles con '{item_solicitado}' en el catálogo.",
        )
    else:
        result = SearchResult(
            resultados=encontrados,
            total_encontrados=len(encontrados),
            mensaje="",
        )

    return result.model_dump_json()


class _AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/health":
            return await call_next(request)
        if _MCP_API_KEY:
            auth = request.headers.get("Authorization", "")
            provided = (
                auth.removeprefix("Bearer ").strip()
                if auth.startswith("Bearer ")
                else request.query_params.get("api_key", "")
            )
            if provided != _MCP_API_KEY:
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return await call_next(request)


async def _health(request: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio")

    if transport == "sse":
        port = int(os.environ.get("PORT", 8000))
        app = Starlette(
            routes=[Route("/health", _health)],
            middleware=[Middleware(_AuthMiddleware)],
        )
        app.mount("/", mcp.sse_app())
        uvicorn.run(app, host="0.0.0.0", port=port)
    else:
        mcp.run(transport="stdio")
