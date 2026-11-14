import copy
from uuid import uuid4
from sqlalchemy import select
from fastapi import HTTPException
from ..models.scenario import BlendScenario
from ..models.dataset import PulpDataset
from ..models.spec import QualitySpec

def create(db,body):
 dataset=db.get(PulpDataset,body.dataset_id)
 if dataset is None or not db.get(QualitySpec,body.spec_id):raise HTTPException(422,"原浆数据或质量规格不存在")
 if db.scalar(select(BlendScenario).where(BlendScenario.name==body.name)):raise HTTPException(409,"试算情景名称已存在")
 row=BlendScenario(id=str(uuid4()),**body.model_dump(),dataset_revision=dataset.revision,materials_snapshot=copy.deepcopy(dataset.materials));db.add(row);db.commit();return row
