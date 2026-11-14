import threading
import pytest
from fastapi import HTTPException
from conftest import make_dataset,correct,material,dataset_csv,Body
from src.config.database import Session
from src.models import PulpDataset,QualitySpec,BlendScenario,BlendRun
from src.services import dataset_service,scenario_service,run_service

def test_whole_batch_import_still_works(db):
 row=make_dataset(db)
 assert row.revision==1
 assert all(m["version"]==1 for m in row.materials) and len(row.materials)==3

def test_newer_version_applies(db):
 ident=make_dataset(db).id
 summary=correct(db,ident,[{"material_id":"M1","version":2,"cost":5300,"strength":90}])
 assert (summary["applied"],summary["ignored_stale"],summary["ignored_replay"],summary["rejected"])==(1,0,0,0)
 assert summary["revision"]==2 and summary["rows"][0]["disposition"]=="applied"
 m=material(db,ident,"M1")
 assert m["cost"]==5300 and m["strength"]==90 and m["version"]==2 and m["whiteness"]==89

def test_out_of_order_older_version_ignored(db):
 ident=make_dataset(db).id
 correct(db,ident,[{"material_id":"M1","version":3,"cost":5400}])
 summary=correct(db,ident,[{"material_id":"M1","version":2,"cost":9999}])
 assert summary["ignored_stale"]==1 and summary["applied"]==0 and summary["revision"]==2
 m=material(db,ident,"M1")
 assert m["cost"]==5400 and m["version"]==3

def test_same_version_same_value_replay_ignored(db):
 ident=make_dataset(db).id
 correct(db,ident,[{"material_id":"M1","version":2,"cost":5300}])
 summary=correct(db,ident,[{"material_id":"M1","version":2,"cost":5300}])
 assert summary["ignored_replay"]==1 and summary["applied"]==0 and summary["revision"]==2
 assert db.get(PulpDataset,ident).revision==2

def test_same_version_different_value_rejects_entire_batch(db):
 ident=make_dataset(db).id
 correct(db,ident,[{"material_id":"M1","version":2,"cost":5300}])
 with pytest.raises(HTTPException) as exc:
  correct(db,ident,[{"material_id":"M2","version":2,"cost":3999},{"material_id":"M1","version":2,"cost":5100}])
 assert exc.value.status_code==409 and "M1" in exc.value.detail and "同版本异值" in exc.value.detail
 fresh=db.get(PulpDataset,ident)
 assert fresh.revision==2
 assert material(db,ident,"M2")["cost"]==3900 and material(db,ident,"M2")["version"]==1

def test_bad_row_leaves_no_partial_update(db):
 ident=make_dataset(db).id
 with pytest.raises(HTTPException) as exc:
  correct(db,ident,[{"material_id":"M1","version":2,"cost":5300},{"material_id":"M9","version":2,"cost":100}])
 assert exc.value.status_code==422 and "M9" in exc.value.detail
 assert db.get(PulpDataset,ident).revision==1 and material(db,ident,"M1")["cost"]==5200

def test_merged_row_violating_physical_bounds_rejected(db):
 ident=make_dataset(db).id
 with pytest.raises(HTTPException) as exc:
  correct(db,ident,[{"material_id":"M1","version":2,"strength":99},{"material_id":"M2","version":2,"cost":3999}])
 assert exc.value.status_code==422
 fresh=db.get(PulpDataset,ident)
 assert fresh.revision==1 and material(db,ident,"M2")["cost"]==3900

def test_malformed_correction_csv_rejected(db):
 ident=make_dataset(db).id
 with pytest.raises(HTTPException) as exc:dataset_service.correct(db,ident,Body(csv_text="material_id,version,unknown_col\nM1,2,5"))
 assert exc.value.status_code==422 and "不可更正" in exc.value.detail
 with pytest.raises(HTTPException) as exc:dataset_service.correct(db,ident,Body(csv_text="material_id,version,cost\nM1,2.5,5300"))
 assert exc.value.status_code==422 and "正整数" in exc.value.detail
 with pytest.raises(HTTPException) as exc:dataset_service.correct(db,ident,Body(csv_text="material_id,version,cost\nM1,2,5300\nM1,3,5400"))
 assert exc.value.status_code==422 and "重复" in exc.value.detail
 assert db.get(PulpDataset,ident).revision==1

def test_concurrent_same_version_conflict_exactly_one_wins(db,monkeypatch):
 ident=make_dataset(db).id
 from src.services import dataset_service
 barrier=threading.Barrier(2)
 calls=[0];gate=threading.Lock()
 real=dataset_service.adjudicate
 def gated(rows,current):
  with gate:
   calls[0]+=1;first=calls[0]<=2
  if first:
   try:barrier.wait(timeout=10)
   except threading.BrokenBarrierError:pass
  return real(rows,current)
 monkeypatch.setattr(dataset_service,"adjudicate",gated)
 batches=[[{"material_id":"M1","version":2,"cost":6100},{"material_id":"M2","version":2,"cost":6100}],
  [{"material_id":"M1","version":2,"cost":6200},{"material_id":"M2","version":2,"cost":6200}]]
 outcomes=[None]*2
 def worker(i):
  with Session() as s:
   try:outcomes[i]=("ok",correct(s,ident,batches[i]))
   except HTTPException as e:outcomes[i]=("http",e.status_code)
 threads=[threading.Thread(target=worker,args=(i,)) for i in range(2)]
 for t in threads:t.start()
 for t in threads:t.join()
 assert sorted(o[0] for o in outcomes)==["http","ok"]
 assert [o[1] for o in outcomes if o[0]=="http"]==[409]
 winner=[o[1] for o in outcomes if o[0]=="ok"][0]
 assert winner["applied"]==2 and winner["revision"]==2
 applied_cost=6100 if outcomes[0][0]=="ok" else 6200
 assert (material(db,ident,"M1")["version"],material(db,ident,"M1")["cost"])==(2,applied_cost)
 assert (material(db,ident,"M2")["version"],material(db,ident,"M2")["cost"])==(2,applied_cost)
 assert db.get(PulpDataset,ident).revision==2

def test_concurrent_versions_highest_wins(db):
 ident=make_dataset(db).id
 batches=[[{"material_id":"M1","version":2,"cost":6100},{"material_id":"M2","version":2,"cost":6100}],
  [{"material_id":"M1","version":3,"cost":6300},{"material_id":"M2","version":3,"cost":6300}]]
 outcomes=[None]*2
 def worker(i):
  with Session() as s:
   try:outcomes[i]=("ok",correct(s,ident,batches[i]))
   except HTTPException as e:outcomes[i]=("http",e.status_code)
 threads=[threading.Thread(target=worker,args=(i,)) for i in range(2)]
 for t in threads:t.start()
 for t in threads:t.join()
 assert [o[0] for o in outcomes]==["ok","ok"]
 m1,m2=material(db,ident,"M1"),material(db,ident,"M2")
 assert (m1["version"],m1["cost"])==(3,6300) and (m2["version"],m2["cost"])==(3,6300)
 assert db.get(PulpDataset,ident).revision in (2,3)

def test_scenario_pins_dataset_version_and_isolates_runs(db):
 dataset=make_dataset(db)
 db.add(QualitySpec(id="spec-1",name="文化用纸窗口",strength_min=70,strength_max=100,whiteness_min=80,whiteness_max=100,recycled_min=0.0,recycled_max=1,description=""));db.commit()
 scenario=scenario_service.create(db,Body(name="基线情景",dataset_id=dataset.id,spec_id="spec-1",n_samples=20,seed=7,perturb_cost=True))
 assert scenario.dataset_revision==1 and len(scenario.materials_snapshot)==3
 correct(db,dataset.id,[{"material_id":"M1","version":2,"cost":9000},{"material_id":"M2","version":2,"cost":9000}])
 assert db.get(PulpDataset,dataset.id).revision==2
 run=BlendRun(id="run-1",scenario_id=scenario.id,status="queued",result={},error="");db.add(run);db.commit()
 run_service.compute(db,"run-1")
 db.expire_all();run=db.get(BlendRun,"run-1")
 assert run.status=="completed" and run.result["dataset_revision"]==1
 pinned={m["material_id"]:m for m in run.result["materials"]}
 assert pinned["M1"]["cost"]==5200 and pinned["M2"]["cost"]==3900
 later=scenario_service.create(db,Body(name="更正后情景",dataset_id=dataset.id,spec_id="spec-1",n_samples=20,seed=7,perturb_cost=True))
 assert later.dataset_revision==2
 run2=BlendRun(id="run-2",scenario_id=later.id,status="queued",result={},error="");db.add(run2);db.commit()
 run_service.compute(db,"run-2")
 db.expire_all();run2=db.get(BlendRun,"run-2")
 assert run2.result["dataset_revision"]==2
 assert run2.result["lp"]["nominal_cost"]>run.result["lp"]["nominal_cost"]
