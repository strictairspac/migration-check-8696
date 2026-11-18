from sqlalchemy import Column,Integer,String,JSON,ForeignKey
from src.config.database import Base
class Mapping(Base):
 __tablename__='mappings'
 id=Column(Integer,primary_key=True)
 name=Column(String(120),unique=True,nullable=False)
 batch_id=Column(Integer,ForeignKey('batches.id'),nullable=False)
 rules=Column(JSON,nullable=False)
 chunk_size=Column(Integer,nullable=False,default=50)
 note=Column(String(500),nullable=False,default='')
