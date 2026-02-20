"""HTTP-клиент Fuseki Admin API: создание/удаление/список датасетов (обёртка для worker)."""
from pathlib import Path

import httpx

from worker.config import get_settings


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


def rag_prod_dataset(rag_id: int) -> str:
    """Prod-датасет RAG: ferag-00001, ferag-00002, ..."""
    return f"ferag-{rag_id:05d}"


def rag_staging_dataset(rag_id: int, cycle_n: int) -> str:
    """Staging-датасет цикла: ferag-00001-new-00001, ..."""
    return f"ferag-{rag_id:05d}-new-{cycle_n:05d}"


def rag_triples_dataset(rag_id: int, cycle_n: int) -> str:
    """Датасет триплетов цикла."""
    return f"ferag-{rag_id:05d}-new-{cycle_n:05d}-triples"


def rag_ontology_dataset(rag_id: int, cycle_n: int) -> str:
    """Датасет онтологии цикла."""
    return f"ferag-{rag_id:05d}-new-{cycle_n:05d}-ontology"


def export_dataset_to_ttl(dataset_name: str, out_path: Path) -> None:
    """
    Экспорт датасета Fuseki в TTL через SPARQL CONSTRUCT.
    Если датасет отсутствует или пуст — записывает пустой граф (минимальный TTL).
    """
    s = get_settings()
    base = s.fuseki_url.rstrip("/")
    url = f"{base}/{dataset_name}/query"
    query = "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }"
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with _client() as client:
        r = client.post(
            url,
            data={"query": query},
            headers={"Accept": "text/turtle"},
            timeout=120.0,
        )
        if r.status_code in (404, 405):
            # 404: датасет не существует; 405: Fuseki не распознаёт путь (датасет не создан)
            out_path.write_text("# Empty dataset (dataset not found)\n", encoding="utf-8")
            return
        r.raise_for_status()
        out_path.write_text(r.text or "# Empty dataset\n", encoding="utf-8")


def load_ttl_into_dataset(dataset_name: str, ttl_path: Path) -> None:
    """
    Загрузить TTL-файл в default graph датасета (Graph Store Protocol: PUT).
    URL по спецификации Fuseki: /{dataset}/data?default для целевого default graph.
    """
    s = get_settings()
    base = s.fuseki_url.rstrip("/")
    url = f"{base}/{dataset_name}/data?default"
    ttl_path = Path(ttl_path)
    content = ttl_path.read_text(encoding="utf-8")
    with _client() as client:
        r = client.put(
            url,
            content=content,
            headers={"Content-Type": "text/turtle; charset=utf-8"},
            timeout=300.0,
        )
        r.raise_for_status()
