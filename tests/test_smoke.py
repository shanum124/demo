from fastapi.testclient import TestClient
from ai_services.main import app, mock_generator
from ai_services.main import bridge
from ai_services.schemas.mcp_schemas import MarkdownWriteRequest

client = TestClient(app)

def test_health():
    assert client.get('/health').json()['status'] == 'ok'

def test_mock_generation_and_report(monkeypatch):
    monkeypatch.setattr(mock_generator, "model", None)
    response = client.post('/mock/generate', json={'user_id': 'test', 'mode': 'exam_replica', 'question_count': 2, 'time_limit_minutes': 10, 'target_node_ids': ['NODE.1'], 'node_weights': {'NODE.1': 1.0}})
    assert response.status_code == 503
    assert client.get('/report').status_code == 200

def test_markdown_patch_is_versioned():
    result = __import__('asyncio').run(bridge.markdown_store_write(MarkdownWriteRequest(doc_id='test', section='x', patch='content')))
    assert result.success
    assert result.version >= 1
