from ..services import scenario_service
from ..models.scenario import BlendScenario
from ..models.common import serialize
from .common import listing,require
def trim(data):data.pop("materials_snapshot",None);return data
def list_all(db):return [trim(r) for r in listing(db,BlendScenario)]
def detail(db,ident):return trim(serialize(require(db,BlendScenario,ident)))
def create(db,body):return trim(serialize(scenario_service.create(db,body)))
