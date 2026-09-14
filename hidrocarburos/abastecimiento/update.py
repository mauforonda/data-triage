#!/usr/bin/env python3

from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


BASE_URL = "https://nominac.kyros-tech.com/api"
OUTPUT_DIR = Path(__file__).parent / "data"
REQUEST_TIMEOUT = (10, 60)
MAX_RETRIES = 4
PAGE_SIZE = 100
TIPOS = ("programacion", "despachos")
IDENTITY_FIELDS = {
    "programacion": (
        "fecha_programacion",
        "volumen_programado",
        "producto",
        "cliente",
    ),
    "despachos": (
        "fecha_despacho_efectivo",
        "fecha_despacho_programado",
        "cantidad_despachada",
        "producto_despachado",
        "cliente",
    ),
}


def create_session() -> requests.Session:
    """Create an HTTP session with retries for transient failures."""
    retry = Retry(
        total=MAX_RETRIES,
        connect=MAX_RETRIES,
        read=MAX_RETRIES,
        status=MAX_RETRIES,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
    )
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def get_json(session: requests.Session, url: str, params: dict | None = None) -> dict:
    response = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()


def get_distritos(session: requests.Session) -> list[dict]:
    raw = get_json(session, f"{BASE_URL}/catalogos/distritos/publico")
    return raw


def identity(item: dict, tipo: str) -> tuple:
    """Return the fields that identify one record within a district/type file."""
    return tuple(
        None if pd.isna(item.get(field)) else item.get(field)
        for field in IDENTITY_FIELDS[tipo]
    )


def load_existing(output_file: Path, tipo: str) -> tuple[pd.DataFrame, set[tuple]]:
    if not output_file.exists() or output_file.stat().st_size == 0:
        return pd.DataFrame(), set()

    previous = pd.read_csv(output_file)
    known = {identity(row, tipo) for row in previous.to_dict(orient="records")}
    return previous, known


def get_abastecimiento(
    session: requests.Session,
    distrito: dict,
    tipo: str,
    known: set[tuple],
) -> list[dict]:
    """Fetch unseen records, stopping once a full page is already known.

    The reports are ordered from newest to oldest. Therefore, once a page
    contains no unseen records, later pages cannot contain new history.
    """
    page = 1
    fetched = 0
    new_data = []
    url = f"{BASE_URL}/reportes/{tipo}/publico"

    while True:
        print(f"{distrito['nombre']} / {tipo} / página {page}")
        raw = get_json(
            session,
            url,
            params={
                "distrito_id": distrito["id"],
                "page": page,
                "page_size": PAGE_SIZE,
            },
        )
        items = raw.get("items", [])
        if not items:
            break

        unseen = []
        for item in items:
            item = {**item, "distrito_nombre": distrito["nombre"]}
            item_identity = identity(item, tipo)
            if item_identity not in known:
                known.add(item_identity)
                unseen.append(item)
        new_data.extend(unseen)

        fetched += len(items)
        if fetched >= raw.get("total", fetched) or (known and not unseen):
            break
        page += 1

    return new_data


def save_data(
    output_file: Path,
    tipo: str,
    previous: pd.DataFrame,
    new_data: list[dict],
) -> None:
    current = pd.DataFrame(new_data)
    if previous.empty:
        combined = current
    elif current.empty:
        combined = previous
    else:
        combined = pd.concat([previous, current], ignore_index=True)

    if combined.empty:
        return

    combined = combined.drop_duplicates(subset=IDENTITY_FIELDS[tipo], keep="first")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(output_file, index=False)


def main() -> None:
    session = create_session()
    distritos = get_distritos(session)
    for tipo in TIPOS:
        print(f"Reporte de {tipo}")
        for distrito in distritos:
            output_file = OUTPUT_DIR / tipo / f"{distrito['codigo'].lower()}.csv"
            previous, known = load_existing(output_file, tipo)
            new_data = get_abastecimiento(session, distrito, tipo, known)
            save_data(output_file, tipo, previous, new_data)


if __name__ == "__main__":
    main()
