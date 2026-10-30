from fastapi.testclient import TestClient
from app.main import app, store

client=TestClient(app)

def setup_function(): store.reset()
def test_health(): assert client.get('/api/health').json()['mode']=='simulation'
def test_robots_and_telemetry():
    assert client.get('/api/robots').json()['total']==5
    assert len(client.get('/api/robots/ATLAS-01/telemetry').json()['items'])==24
def test_estop_rejects_motion():
    assert client.post('/api/robots/ATLAS-01/commands',json={'command':'estop'}).status_code==200
    assert client.post('/api/robots/ATLAS-01/commands',json={'command':'forward'}).status_code==409
def test_mission_lifecycle_preflight():
    created=client.post('/api/missions',json={'name':'Test delivery','robot_id':'ATLAS-01','destination':'Storage A1'}).json()
    assert client.get(f"/api/missions/{created['id']}/preflight").json()['ready']
    assert client.post(f"/api/missions/{created['id']}/start").json()['status']=='executing'
    assert client.post(f"/api/missions/{created['id']}/pause").json()['status']=='paused'
def test_fault_alert_resolution_and_audit():
    response=client.post('/api/simulation/faults',json={'robot_id':'ATLAS-02','fault':'network_degradation'}).json()
    assert client.post(f"/api/alerts/{response['alert']['id']}/resolve").json()['status']=='resolved'
    assert any(x['action']=='fault_injected' for x in client.get('/api/audit').json()['items'])
def test_reset_and_readiness():
    client.post('/api/simulation/faults',json={'robot_id':'ATLAS-01','fault':'communication_loss'})
    assert client.post('/api/simulation/reset').json()['ok']
    assert len(client.get('/api/deployments/DEP-001/readiness').json()['checks'])==9
