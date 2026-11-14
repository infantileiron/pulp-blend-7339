from uuid import uuid4
from sqlalchemy import select,update
from fastapi import HTTPException
from ..models.dataset import PulpDataset
from .materials import parse_csv,parse_corrections,validate_item

MAX_ATTEMPTS=8

def create(db,body):
 if db.scalar(select(PulpDataset).where(PulpDataset.name==body.name)):raise HTTPException(409,"原浆批次名称已存在")
 try:materials=parse_csv(body.csv_text)
 except ValueError as e:raise HTTPException(422,str(e))
 row=PulpDataset(id=str(uuid4()),name=body.name,materials=[dict(m,version=1) for m in materials],description=body.description,revision=1);db.add(row);db.commit();return row

def adjudicate(rows,current):
 applied=[];stale=[];replay=[];conflicts=[]
 for r in rows:
  m=current[r["material_id"]];version=int(m.get("version",1))
  if r["version"]>version:applied.append(r)
  elif r["version"]<version:stale.append(r)
  else:
   diffs=[key for key,value in r["changes"].items() if m.get(key)!=value]
   (conflicts if diffs else replay).append((r,m,diffs) if diffs else r)
 return applied,stale,replay,conflicts

def correct(db,ident,body):
 try:rows=parse_corrections(body.csv_text)
 except ValueError as e:raise HTTPException(422,str(e))
 for _ in range(MAX_ATTEMPTS):
  dataset=db.get(PulpDataset,ident)
  if dataset is None:raise HTTPException(404,"记录不存在")
  revision=dataset.revision
  current={m["material_id"]:dict(m) for m in dataset.materials}
  unknown=[r["material_id"] for r in rows if r["material_id"] not in current]
  if unknown:raise HTTPException(422,"更正行引用了不存在的原浆，整批已拒绝："+",".join(unknown))
  applied,stale,replay,conflicts=adjudicate(rows,current)
  if conflicts:
   parts=[f"{r['material_id']}版本{r['version']}字段{','.join(diffs)}：当前{[m.get(k) for k in diffs]}≠更正{[r['changes'][k] for k in diffs]}" for r,m,diffs in conflicts]
   raise HTTPException(409,"同版本异值冲突，整批已拒绝："+"；".join(parts))
  if applied:
   merged={mid:dict(m) for mid,m in current.items()}
   for r in applied:merged[r["material_id"]].update(r["changes"],version=r["version"])
   for m in merged.values():m.setdefault("version",1)
   bad=[]
   for r in applied:
    try:validate_item(merged[r["material_id"]])
    except ValueError as e:bad.append(f"{r['material_id']}：{e}")
   if bad:raise HTTPException(422,"更正后数值非法，整批已拒绝："+"；".join(bad))
   materials=[merged[m["material_id"]] for m in dataset.materials]
   result=db.execute(update(PulpDataset).where(PulpDataset.id==ident,PulpDataset.revision==revision).values(materials=materials,revision=revision+1))
   if result.rowcount!=1:db.rollback();continue
   db.commit()
  disposition={r["material_id"]:"applied" for r in applied}|{r["material_id"]:"ignored_stale" for r in stale}|{r["material_id"]:"ignored_replay" for r in replay}
  return {"dataset_id":ident,"revision":revision+(1 if applied else 0),"applied":len(applied),"ignored_stale":len(stale),"ignored_replay":len(replay),"rejected":0,"rows":[{"material_id":r["material_id"],"version":r["version"],"disposition":disposition[r["material_id"]]} for r in rows]}
 raise HTTPException(409,"并发更正过密，版本裁决多次重试仍未落定，请重新提交")
