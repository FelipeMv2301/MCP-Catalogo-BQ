from pydantic import BaseModel


class CatalogItem(BaseModel):
    sku: str
    nombre_comercial: str
    especificaciones_tecnicas: str
    precio_lista_neto: float
    disponible_para_venta: bool


class SearchResult(BaseModel):
    resultados: list[CatalogItem]
    total_encontrados: int
    mensaje: str
