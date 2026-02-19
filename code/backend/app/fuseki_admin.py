"""HTTP-клиент Fuseki Admin API: создание/удаление/список датасетов."""
import httpx

from app.config import get_settings


def _client() -> httpx.Client:
    """Клиент с basic auth из настроек."""
    s = get_settings()
    return httpx.Client(
        auth=(s.fuseki_user, s.fuseki_password),
        timeout=30.0,
    )


def create_dataset(name: str, db_type: str = "tdb2") -> None:
    """Создать датасет. Идемпотентно: 409 (уже существует) не считается ошибкой."""
    s = get_settings()
    url = f"{s.fuseki_url.rstrip('/')}/$/datasets"
    data = {"dbName": name, "dbType": db_type}
    with _client() as client:
        r = client.post(url, data=data)
        if r.status_code == 409:
            return
        r.raise_for_status()


def delete_dataset(name: str) -> None:
    """Удалить датасет по имени."""
    s = get_settings()
    base = s.fuseki_url.rstrip("/")
    url = f"{base}/$/datasets/{name}"
    with _client() as client:
        r = client.delete(url)
        r.raise_for_status()


def list_datasets() -> list[str]:
    """Список имён датасетов (без ведущего слэша)."""
    s = get_settings()
    url = f"{s.fuseki_url.rstrip('/')}/$/datasets"
    with _client() as client:
        r = client.get(url)
        r.raise_for_status()
    data = r.json()
    names = []
    for item in data.get("datasets", []):
        raw = item.get("ds.name", "")
        if isinstance(raw, str) and raw:
            names.append(raw.lstrip("/"))
    return names


# Именование датасетов Fuseki (соглашения плана)
def rag_prod_dataset(rag_id: int) -> str:
    """Prod-датасет RAG: ferag-00001, ferag-00002, ..."""
    return f"ferag-{rag_id:05d}"


def rag_staging_dataset(rag_id: int, cycle_n: int) -> str:
    """Staging-датасет цикла: ferag-00001-new-00001, ..."""
    return f"ferag-{rag_id:05d}-new-{cycle_n:05d}"


def rag_triples_dataset(rag_id: int, cycle_n: int) -> str:
    """Датасет триплетов цикла: ferag-00001-new-00001-triples, ..."""
    return f"ferag-{rag_id:05d}-new-{cycle_n:05d}-triples"


def rag_ontology_dataset(rag_id: int, cycle_n: int) -> str:
    """Датасет онтологии цикла: ferag-00001-new-00001-ontology, ..."""
    return f"ferag-{rag_id:05d}-new-{cycle_n:05d}-ontology"
