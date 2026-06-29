import os
from urllib.parse import parse_qs
import uvicorn
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send
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


class _AuthMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        if path == "/health" or not _MCP_API_KEY:
            await self.app(scope, receive, send)
            return

        query_string = scope.get("query_string", b"").decode()
        params = parse_qs(query_string)

        # /messages/ with session_id: session was already authenticated via SSE
        if path.startswith("/messages/") and params.get("session_id"):
            await self.app(scope, receive, send)
            return

        headers = {k: v for k, v in scope.get("headers", [])}
        auth_header = headers.get(b"authorization", b"").decode()
        if auth_header.startswith("Bearer "):
            provided = auth_header.removeprefix("Bearer ").strip()
        else:
            provided = params.get("api_key", [""])[0]

        if provided != _MCP_API_KEY:
            resp = Response('{"error":"Unauthorized"}', status_code=401, media_type="application/json")
            await resp(scope, receive, send)
            return

        await self.app(scope, receive, send)


async def _health(request: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio")

    if transport == "sse":
        port = int(os.environ.get("PORT", 8000))
        starlette_app = Starlette(routes=[Route("/health", _health)])
        starlette_app.mount("/", mcp.sse_app())
        app = _AuthMiddleware(starlette_app)
        uvicorn.run(app, host="0.0.0.0", port=port)
    else:
        mcp.run(transport="stdio")
