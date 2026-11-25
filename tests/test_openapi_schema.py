import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from main import app  # noqa: E402


def test_openapi_documents_the_four_api_operations():
    response = TestClient(app).get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    operations = [
        ("/health", "get", "System", {"status"}),
        ("/info", "get", "Model", {"mode", "load_error", "species_catalog", "storage_backend"}),
        ("/predict", "post", "Inference", {"scientific_name", "confidence", "probabilities"}),
        ("/contribute", "post", "Citizen Science", {"saved", "backend", "sample_id", "location"}),
    ]

    for path, method, tag, fields in operations:
        operation = schema["paths"][path][method]
        assert operation["tags"] == [tag]
        assert operation["summary"]
        assert operation["description"]
        response_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
        model = schema["components"]["schemas"][response_schema["$ref"].rsplit("/", 1)[-1]]
        assert fields <= model["properties"].keys()
