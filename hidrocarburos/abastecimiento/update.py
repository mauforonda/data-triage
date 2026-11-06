#!/usr/bin/env python3

import json
import re
from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


URL = "https://consulta.ypfb.gob.bo/"
OUTPUT_DIR = Path(__file__).parent / "data"
REQUEST_TIMEOUT = (10, 60)
MAX_RETRIES = 4
TIPOS = ("programacion", "despachos")
DATE_FIELD = {
    "programacion": "fecha_programacion",
    "despachos": "fecha_despacho_efectivo",
}
DATA_PATTERN = re.compile(
    r'<script[^>]*id="datos-publicos"[^>]*>(.*?)</script>', re.DOTALL
)


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


def get_datos(session: requests.Session) -> dict:
    """Read the JSON embedded in the query page."""
    response = session.get(URL, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    match = DATA_PATTERN.search(response.text)
    if match is None:
        raise RuntimeError("No se encontró el JSON 'datos-publicos' en la página")
    return json.loads(match.group(1))


def extract_records(datos: dict, tipo: str) -> dict[str, list[dict]]:
    """Return the records of one type, grouped by district code."""
    distritos = {str(d["id"]): d for d in datos["distritos"]}
    records: dict[str, list[dict]] = {}
    for distrito_id, productos in datos["datos"].items():
        distrito = distritos[distrito_id]
        for bloque in productos.values():
            for item in bloque[tipo]:
                item = {**item, "distrito_nombre": distrito["nombre"]}
                records.setdefault(distrito["codigo"].lower(), []).append(item)
    return records


def save_data(output_file: Path, tipo: str, new_data: list[dict]) -> None:
    """Merge a snapshot into the history.

    The page only shows the current day and its records can change during
    the day (e.g. confirmations). Therefore, the snapshot replaces any
    stored record of the same dates.
    """
    current = pd.DataFrame(new_data)
    field = DATE_FIELD[tipo]
    if output_file.exists() and output_file.stat().st_size > 0:
        previous = pd.read_csv(output_file)
        previous = previous[~previous[field].isin(current[field].unique())]
        combined = pd.concat([previous, current], ignore_index=True)
    else:
        combined = current

    output_file.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(output_file, index=False)


def main() -> None:
    datos = get_datos(create_session())
    print(f"Datos al {datos['fecha_datos']} (generado {datos['generado_en']})")
    for tipo in TIPOS:
        for codigo, new_data in extract_records(datos, tipo).items():
            print(f"{tipo} / {codigo}: {len(new_data)}")
            save_data(OUTPUT_DIR / tipo / f"{codigo}.csv", tipo, new_data)


if __name__ == "__main__":
    main()
