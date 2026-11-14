import os,sys,tempfile
os.environ["DATABASE_URL"]="sqlite:///"+os.path.join(tempfile.mkdtemp(prefix="pulp-test-"),"test.db")
os.environ["SEED_DEMO"]="false"
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from src import models
from src.config.database import Base,engine,Session

@pytest.fixture()
def db():
 Base.metadata.drop_all(engine);Base.metadata.create_all(engine)
 with Session() as session:yield session

HEADER="material_id,name,cost,min_share,max_share,strength,whiteness,recycled,strength_width,whiteness_width,recycled_width,cost_width"
ROWS=[
 "M1,北杉针叶浆,5200,0,0.65,91,89,0,3,1.5,0,200",
 "M2,南桉阔叶浆,3900,0,0.7,88,70,0,3,2,0,160",
 "M3,高白竹浆,4200,0,0.5,91,74,0,2.5,1.5,0,180",
]
def dataset_csv(rows=ROWS):return HEADER+"\n"+"\n".join(rows)

def correction_csv(rows):
 fields=[k for k in ["cost","min_share","max_share","strength","whiteness","recycled","strength_width","whiteness_width","recycled_width","cost_width"] if any(k in r for r in rows)]
 lines=[",".join(["material_id","version"]+fields)]
 for r in rows:lines.append(",".join([r["material_id"],str(r["version"])]+[str(r[f]) if f in r else "" for f in fields]))
 return "\n".join(lines)

class Body:
 def __init__(self,**kw):self.__dict__.update(kw)
 def model_dump(self):return dict(self.__dict__)

def make_dataset(db,name="十一月原浆批次"):
 from src.services import dataset_service
 return dataset_service.create(db,Body(name=name,csv_text=dataset_csv(),description=""))

def correct(db,ident,rows):
 from src.services import dataset_service
 return dataset_service.correct(db,ident,Body(csv_text=correction_csv(rows)))

def material(db,ident,mid):
 from src.models import PulpDataset
 return next(m for m in db.get(PulpDataset,ident).materials if m["material_id"]==mid)
