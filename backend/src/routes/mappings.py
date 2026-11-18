from fastapi import APIRouter,Depends
from src.middlewares.auth import current,writer
from src.schemas.business import MappingInput
from src.services import mappings
from src.controllers.business import save_mapping
router=APIRouter()
@router.get('/mappings')
def listing(u=Depends(current)):return mappings.list_items()
@router.post('/mappings')
def create(data:MappingInput,u=Depends(writer)):return save_mapping(data,u)
@router.put('/mappings/{item_id}')
def update(item_id:int,data:MappingInput,u=Depends(writer)):return save_mapping(data,u,item_id)
