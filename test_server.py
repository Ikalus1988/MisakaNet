import pytest
import requests

@pytest.fixture
def client():
    return requests.Session()

def test_post_danmaku(client):
    response = client.post('http://localhost:3000/api/danmaku', json={'text': 'Hello World'})
    assert response.status_code == 200
    assert response.json()['message'] == 'Danmaku posted successfully'

def test_get_danmaku(client):
    response = client.get('http://localhost:3000/api/danmaku')
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_filter_danmaku(client):
    response = client.post('http://localhost:3000/api/danmaku', json={'text': 'This is an attack'})
    assert response.status_code == 400
    assert response.json()['message'] == 'Danmaku contains forbidden content'