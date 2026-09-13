"""Update the SIMAT administrative conflict-management datasets."""

from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


URL_BASE = "https://simat-api-test.produccion.gob.bo/"
OUTPUT_DIR = Path(__file__).parent / "data"
REQUEST_TIMEOUT = (10, 60)
MAX_RETRIES = 4

TABLES = (
    "principal",
    "actor",
    "demandapunto",
    "conveniopunto",
    "demandaseguimiento",
    "convenioseguimiento",
    "institucion",
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


def get_data(
    session: requests.Session,
    url: str,
    limit: int,
    field: str,
    filename: str,
) -> None:
    response = session.get(url, params={"limit": limit}, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    raw = response.json()

    if field not in raw:
        raise KeyError(f"The response for {url} has no {field!r} field")

    df = pd.DataFrame(raw[field])
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_DIR / filename, index=False)
    print(f"{filename} : {len(df)} registros")


def main() -> None:
    session = create_session()
    for table in TABLES:
        get_data(
            session=session,
            url=f"{URL_BASE}reportes/tabla/{table}",
            limit=2000,
            field="data",
            filename=f"{table}.csv",
        )

    get_data(
        session=session,
        url=f"{URL_BASE}reportes/casos",
        limit=2000,
        field="items",
        filename="casos.csv",
    )


if __name__ == "__main__":
    main()
