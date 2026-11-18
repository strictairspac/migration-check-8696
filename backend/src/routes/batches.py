from fastapi import APIRouter,Depends
from src.middlewares.auth import current,writer
from src.schemas.business import BatchInput
from src.services import batches
from src.controllers.business import save_batch
router=APIRouter()
@router.get('/batches')
def listing(u=Depends(current)):return batches.list_items()
@router.post('/batches')
def create(data:BatchInput,u=Depends(writer)):return save_batch(data,u)
@router.put('/batches/{item_id}')
def update(item_id:int,data:BatchInput,u=Depends(writer)):return save_batch(data,u,item_id)
