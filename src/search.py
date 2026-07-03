import difflib
import html
import re
from unidecode import unidecode
from .schemas import CatalogItem

_RE_HTML_TAGS = re.compile(r"<[^>]+>")
_RE_ASTERISK_LINES = re.compile(r"\*[^\n]*")
_RE_WHITESPACE = re.compile(r"\s+")


def limpiar_descripcion(texto: str) -> str:
    texto = html.unescape(texto)
    texto = _RE_HTML_TAGS.sub(" ", texto)
    texto = _RE_ASTERISK_LINES.sub("", texto)
    texto = _RE_WHITESPACE.sub(" ", texto)
    return texto.strip()


def normalizar(texto: str) -> str:
    return unidecode(texto).lower().strip()


def tokenizar(texto: str) -> list[str]:
    # split on non-alphanumeric AND on digit↔letter boundaries ("100ml" → ["100","ml"])
    tokens = re.split(r"[\s\-\W]+|(?<=\d)(?=[a-zA-Z])|(?<=[a-zA-Z])(?=\d)", texto)
    return [t for t in tokens if len(t) >= 2]


def nombre_completo(item: dict) -> str:
    # SAP ItemName ("name") viene truncado a un campo corto; ForeignName
    # ("description") trae el nombre extendido. Usamos el más largo.
    name = (item.get("name") or "").strip()
    desc = (item.get("description") or "").strip()
    return desc if len(desc) > len(name) else name


def texto_busqueda(item: dict) -> str:
    woo = limpiar_descripcion(item.get("woo_description") or "")
    desc = (item.get("description") or "").strip()
    name = nombre_completo(item)
    partes = [p for p in (name, desc, woo) if p]
    return " ".join(partes)


def score_item(query_norm: str, query_tokens: list[str], texto_norm: str) -> float:
    texto_tokens = tokenizar(texto_norm)
    if not texto_tokens or not query_tokens:
        return 0.0

    comunes = sum(1 for t in query_tokens if t in texto_tokens)
    token_score = comunes / len(query_tokens)

    seq_score = difflib.SequenceMatcher(None, query_norm, texto_norm).ratio()

    return 0.6 * token_score + 0.4 * seq_score


def buscar(
    query: str,
    items: list[dict],
    limite: int = 3,
    umbral: float = 0.15,
) -> list[CatalogItem]:
    query_norm = normalizar(query)
    query_tokens = tokenizar(query_norm)

    scored: list[tuple[float, CatalogItem]] = []

    for raw in items:
        nombre = nombre_completo(raw)
        texto_norm = normalizar(texto_busqueda(raw))
        sc = score_item(query_norm, query_tokens, texto_norm)
        if sc < umbral:
            continue

        stock = (raw.get("stock_01") or 0) + (raw.get("stock_11") or 0)
        especificaciones = (
            limpiar_descripcion(raw.get("woo_description") or "")
            or (raw.get("description") or "").strip()
            or nombre
        )
        item = CatalogItem(
            sku=raw.get("sku", ""),
            nombre_comercial=nombre,
            especificaciones_tecnicas=especificaciones,
            precio_lista_neto=raw.get("price") or 0.0,
            disponible_para_venta=stock > 0,
        )
        scored.append((sc, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:limite]]
