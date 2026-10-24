"""Verify a provider outage never grades a learner or changes progress."""
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app import student_tracker
from app.main import app

with tempfile.TemporaryDirectory() as directory:
    student_tracker.STUDENTS_DIR = Path(directory)
    client = TestClient(app)
    response = client.post('/api/session/start', json=dict(student_id='failure_test', subject='science', level='year6', topic='03_microorganisms', mode='learning'))
    assert response.status_code == 200
    before = student_tracker.snapshot_student('failure_test')
    with patch('app.ai_orchestrator._chat_tutor_json', new=AsyncMock(side_effect=RuntimeError('Provider unavailable'))):
        response = client.post('/api/chat/message', json=dict(student_id='failure_test', message='tiny living things'))
    assert response.status_code == 503
    assert student_tracker.snapshot_student('failure_test') == before
    print('PASS: provider outage leaves session, history and progress unchanged.')
