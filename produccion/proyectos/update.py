"""Update the public projects dataset."""

from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


URL = (
    "https://datos-test.produccion.gob.bo/api_mapa.php"
    "?action=datos&departamento=&municipio=&sector=&subsector="
    "&viceministerio=&ejecutora="
)
OUTPUT_FILE = Path(__file__).parent / "proyectos.csv"
REQUEST_TIMEOUT = (10, 120)
MAX_RETRIES = 4


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


def main() -> None:
    session = create_session()
    response = session.get(URL, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    raw = response.json()

    if "proyectos" not in raw:
        raise KeyError(f"The response for {URL} has no 'proyectos' field")

    df = pd.DataFrame(raw["proyectos"])
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"{OUTPUT_FILE.name} : {len(df)} registros")


if __name__ == "__main__":
    main()
