"""HTTP-клиент Fuseki Admin API: создание/удаление/список датасетов, SPARQL Update, Graph Store."""
import httpx

from app.config import get_settings


def _client(timeout: float = 30.0) -> httpx.Client:
    """Клиент с basic auth из настроек."""
    s = get_settings()
    return httpx.Client(
        auth=(s.fuseki_user, s.fuseki_password),
        timeout=timeout,
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


def sparql_update(dataset_name: str, update_body: str) -> None:
    """Выполнить SPARQL Update (DELETE/INSERT) на датасете. POST /{dataset}/update."""
    s = get_settings()
    base = s.fuseki_url.rstrip("/")
    url = f"{base}/{dataset_name}/update"
    with _client(timeout=120.0) as client:
        r = client.post(
            url,
            content=update_body,
            headers={"Content-Type": "application/sparql-update"},
        )
        r.raise_for_status()


def get_dataset_ttl(dataset_name: str) -> str:
    """Экспорт default graph датасета в TTL. Пустой или 404 → пустая строка или минимальный TTL."""
    s = get_settings()
    base = s.fuseki_url.rstrip("/")
    url = f"{base}/{dataset_name}/query"
    query = "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }"
    with _client(timeout=120.0) as client:
        r = client.post(
            url,
            data={"query": query},
            headers={"Accept": "text/turtle"},
        )
        if r.status_code == 404:
            return "# Empty dataset\n"
        r.raise_for_status()
        return r.text or "# Empty\n"


def put_dataset_ttl(dataset_name: str, ttl_content: str) -> None:
    """Загрузить TTL в default graph (замена). Graph Store PUT /{dataset}/data?default."""
    s = get_settings()
    base = s.fuseki_url.rstrip("/")
    url = f"{base}/{dataset_name}/data?default"
    with _client(timeout=300.0) as client:
        r = client.put(
            url,
            content=ttl_content,
            headers={"Content-Type": "text/turtle; charset=utf-8"},
        )
        r.raise_for_status()


def post_dataset_ttl(dataset_name: str, ttl_content: str) -> None:
    """Добавить TTL в default graph. Graph Store POST /{dataset}/data?default."""
    s = get_settings()
    base = s.fuseki_url.rstrip("/")
    url = f"{base}/{dataset_name}/data?default"
    with _client(timeout=300.0) as client:
        r = client.post(
            url,
            content=ttl_content,
            headers={"Content-Type": "text/turtle; charset=utf-8"},
        )
        r.raise_for_status()
