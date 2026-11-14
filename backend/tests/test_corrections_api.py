import pytest
from fastapi.testclient import TestClient
from conftest import dataset_csv
from src.main import app
from src.config.database import Base,engine
from src.models import User
from src.config.database import Session
from src.utils.security import hash_password

@pytest.fixture()
def client(db):
 for role in ["analyst","viewer"]:
  with Session() as s:
   s.add(User(id="user-"+role,email=role+"@pulp.demo",role=role,password_hash=hash_password("PulpDemo2026!")));s.commit()
 with TestClient(app) as c:yield c

def token(client,role):
 r=client.post("/auth/login",json={"email":role+"@pulp.demo","password":"PulpDemo2026!"})
 return {"Authorization":"Bearer "+r.json()["token"]}

def test_correction_endpoint_counts_and_conflicts(client):
 head=token(client,"analyst")
 r=client.post("/datasets",json={"name":"HTTP批次","csv_text":dataset_csv(),"description":""},headers=head)
 assert r.status_code==201,r.text
 ident=r.json()["id"]
 assert r.json()["revision"]==1 and all(m["version"]==1 for m in r.json()["materials"])
 r=client.post(f"/datasets/{ident}/corrections",json={"csv_text":"material_id,version,cost\nM1,2,5300\nM2,2,3950"},headers=head)
 assert r.status_code==200 and r.json()["applied"]==2 and r.json()["revision"]==2
 r=client.post(f"/datasets/{ident}/corrections",json={"csv_text":"material_id,version,cost\nM1,2,5300\nM2,1,3900"},headers=head)
 assert r.status_code==200 and r.json()["ignored_replay"]==1 and r.json()["ignored_stale"]==1 and r.json()["revision"]==2
 r=client.post(f"/datasets/{ident}/corrections",json={"csv_text":"material_id,version,cost\nM1,2,5100"},headers=head)
 assert r.status_code==409 and "同版本异值" in r.json()["detail"] and "M1" in r.json()["detail"]
 r=client.get(f"/datasets/{ident}",headers=head)
 assert r.json()["revision"]==2 and next(m for m in r.json()["materials"] if m["material_id"]=="M1")["cost"]==5300

def test_correction_endpoint_permissions(client):
 analyst=token(client,"analyst")
 r=client.post("/datasets",json={"name":"权限批次","csv_text":dataset_csv(),"description":""},headers=analyst)
 ident=r.json()["id"]
 body={"csv_text":"material_id,version,cost\nM1,2,5300"}
 assert client.post(f"/datasets/{ident}/corrections",json=body).status_code==401
 assert client.post(f"/datasets/{ident}/corrections",json=body,headers=token(client,"viewer")).status_code==403
 assert client.post("/datasets/no-such/corrections",json=body,headers=analyst).status_code==404
