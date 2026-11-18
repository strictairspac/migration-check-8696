from fastapi import HTTPException
from src.config.database import Session
from src.models.mapping import Mapping
from src.utils.serialization import record
from src.models.batch import Batch

def list_items():
 with Session() as s:return [record(r) for r in s.query(Mapping).order_by(Mapping.id.desc()).all()]
def save(data,item_id=None):
 with Session() as s:
  if not s.get(Batch,data.batch_id):raise HTTPException(404,'未找到迁移批次')
  row=s.get(Mapping,item_id) if item_id else Mapping()
  if not row:raise HTTPException(404,'未找到记录')
  for k,v in data.model_dump().items():setattr(row,k,v)
  s.add(row);s.commit();s.refresh(row);return record(row)
