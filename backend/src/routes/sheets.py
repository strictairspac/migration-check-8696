from fastapi import APIRouter, Depends, Query

from src.middlewares.auth import current, writer, admin
from src.schemas.business import SheetInput, ReviewPermissionInput, ReclaimInput
from src.services import sheets
from src.controllers.business import open_sheet, open_sheet_version, set_review, reclaim_version

router = APIRouter()


@router.get('/sheets')
def listing(u=Depends(current)):
    return sheets.list_items()


@router.post('/sheets')
def create(data: SheetInput, u=Depends(writer)):
    return open_sheet(data, u)


@router.get('/sheets/{sheet_id}')
def detail(sheet_id: int, u=Depends(current)):
    return sheets.detail(sheet_id)


@router.post('/sheets/{sheet_id}/versions')
def new_version(sheet_id: int, u=Depends(writer)):
    return open_sheet_version(sheet_id, u)


@router.get('/sheets/{sheet_id}/pages/{section}')
def page(
    sheet_id: int,
    section: str,
    page_size: int = Query(default=50, ge=1, le=200),
    page: int | None = Query(default=None, ge=1),
    u=Depends(current),
):
    return sheets.read_page(sheet_id, section, page_size, page)


@router.get('/review/permission')
def review_permission(u=Depends(current)):
    return sheets.get_review_permission()


@router.put('/review/permission')
def set_review_permission(data: ReviewPermissionInput, u=Depends(admin)):
    return set_review(data.enabled, data.reason, u)


@router.post('/sheets/{sheet_id}/reclaim')
def reclaim(sheet_id: int, data: ReclaimInput, u=Depends(admin)):
    return reclaim_version(sheet_id, data.version, u)
