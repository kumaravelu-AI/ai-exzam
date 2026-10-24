"""Run the real tutor against isolated student data."""
import tempfile
import time
from pathlib import Path
from fastapi.testclient import TestClient
from app import student_tracker
from app.main import app

def run():
    with tempfile.TemporaryDirectory() as directory:
        student_tracker.STUDENTS_DIR = Path(directory)
        client = TestClient(app)
        start = client.post('/api/session/start', json=dict(student_id='regression', student_name='Test', subject='science', level='year6', topic='03_microorganisms', mode='learning'))
        assert start.status_code == 200, start.text
        original = start.json()['session']['current_question_id']
        for message, should_advance in [('i dont know', False), ('a small living thing that we cannot see from eye', True)]:
            response = client.post('/api/chat/message', json=dict(student_id='regression', message=message, mode='learning'))
            assert response.status_code == 200, response.text
            data = response.json()
            print(message, '\n', data['message'], '\n', data.get('analysis'), flush=True)
            assert (data['session']['current_question_id'] != original) == should_advance
        print('PASS: confusion teaches; correct paraphrase advances.', flush=True)
        for message, expected in [
            ('They are not living things', 'stay'),
            ('small', 'stay'),
            ('Why do we need a microscope?', 'stay'),
            ('skip this question please', 'skip'),
            ('நுண்ணுயிரிகள் மிகச் சிறிய உயிரினங்கள். வெறும் கண்களால் பார்க்க முடியாது.', 'advance'),
        ]:
            time.sleep(20)  # Exercise normal learner pacing, within the provider's token quota.
            start = client.post('/api/session/start', json=dict(student_id='regression', student_name='Test', subject='science', level='year6', topic='03_microorganisms', mode='learning')).json()
            response = client.post('/api/chat/message', json=dict(student_id='regression', message=message, mode='learning'))
            assert response.status_code == 200, response.text
            data = response.json()
            moved = data['session']['current_question_id'] != start['session']['current_question_id']
            assert moved == (expected != 'stay'), (message, data)
            if expected == 'skip':
                assert data['analysis']['score_delta'] == 0
            print('PASS:', message, data['analysis']['intent'], flush=True)

if __name__ == '__main__':
    run()
