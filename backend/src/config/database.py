from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase,sessionmaker
from .settings import DATABASE_URL
class Base(DeclarativeBase): pass
connect_args={"timeout":30} if DATABASE_URL.startswith("sqlite") else {}
engine=create_engine(DATABASE_URL,pool_pre_ping=True,connect_args=connect_args)
Session=sessionmaker(bind=engine,expire_on_commit=False)
def get_db():
 with Session() as db: yield db
def initialize():
 from .. import models
 Base.metadata.create_all(engine)
