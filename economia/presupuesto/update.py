"""Update daily public-budget classifier datasets."""

from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


BASE_URL = "https://abierto.economiayfinanzas.gob.bo/api/diario"
OUTPUT_DIR = Path(__file__).parent / "data"
REQUEST_TIMEOUT = (10, 120)
MAX_RETRIES = 4

CLASSIFIERS = {
    "Entidades": {"filename": "entidades", "padre": "area", "hijo": "entidad"},
    "Finalidad y Función": {
        "filename": "finfun",
        "padre": "finalidad",
        "hijo": "funcion",
    },
    "Ubicación": {"filename": "ubigeo", "padre": "departamento", "hijo": "municipio"},
    "Actividad Económica": {
        "filename": "acteco",
        "padre": "sector",
        "hijo": "actividad",
    },
    "Objetos": {"filename": "objetos", "padre": "grupo", "hijo": "partida"},
}
ORDER = ["fecha", "padre", "hijo", "devengado"]


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


def get_json(session: requests.Session, url: str):
    response = session.get(url, timeout=REQUEST_TIMEOUT, verify=False)
    response.raise_for_status()
    return response.json()


def get_last_update(session: requests.Session) -> datetime:
    raw = get_json(session, f"{BASE_URL}?tipo=status")
    return datetime.fromisoformat(raw["fecha_actualizacion"])


def get_data(session: requests.Session) -> pd.DataFrame:
    raw = get_json(session, f"{BASE_URL}?tipo=clasificadores")
    return pd.DataFrame(raw)


def update() -> None:
    session = create_session()
    last_update = get_last_update(session)
    print(f"Last update: {last_update:%Y-%m-%d}")

    df = get_data(session)
    df["fecha"] = df["dias"].map(lambda days: last_update - timedelta(days=days))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for classifier, values in CLASSIFIERS.items():
        print(classifier)
        output = (
            df[df["clasificador"] == classifier][ORDER]
            .sort_values(ORDER)
            .rename(columns={"hijo": values["hijo"], "padre": values["padre"]})
        )
        output.to_csv(
            OUTPUT_DIR / f"{values['filename']}.csv", index=False, float_format="%.2f"
        )


if __name__ == "__main__":
    update()
