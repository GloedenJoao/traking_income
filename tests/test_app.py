import os
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from app import create_app
from database import get_db


@pytest.fixture
def client():
    db_fd, db_path = tempfile.mkstemp()
    app = create_app({'TESTING': True, 'DATABASE': db_path, 'SECRET_KEY': 'test'})

    with app.test_client() as client:
        yield client

    os.close(db_fd)
    os.unlink(db_path)


def test_homepage_loads(client):
    response = client.get('/')
    assert response.status_code == 200


def test_add_and_delete_entry_updates_totals(client):
    payload = {
        'period': '2024-01',
        'description': 'Salário base',
        'entry_type': 'provento',
        'amount': '1000.00',
    }
    add_response = client.post('/details', data=payload, follow_redirects=True)
    assert add_response.status_code == 200

    totals_page = client.get('/totals')
    assert b'2024-01' in totals_page.data
    assert b'1000.00' in totals_page.data

    app = client.application
    with app.app_context():
        db = get_db(app)
        entry = db.execute('SELECT id, period FROM detail_entries WHERE description = ?', ('Salário base',)).fetchone()
        assert entry is not None
        entry_id = entry['id']

    delete_response = client.post(f'/details/{entry_id}/delete', follow_redirects=True)
    assert delete_response.status_code == 200

    with app.app_context():
        db = get_db(app)
        total_row = db.execute(
            'SELECT total_proventos, total_descontos, valor_liquido FROM monthly_totals WHERE period = ?',
            ('2024-01',),
        ).fetchone()
        assert total_row['valor_liquido'] == 0
