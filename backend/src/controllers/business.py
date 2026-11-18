from src.services import batches, mappings, runs, sheets
from src.services.audit import log


def save_batch(data, user, item_id=None):
    row = batches.save(data, item_id)
    log(user.email, 'batch.save', row['name'])
    return row


def save_mapping(data, user, item_id=None):
    row = mappings.save(data, item_id)
    log(user.email, 'mapping.save', row['name'])
    return row


def start_run(data, user):
    row = runs.create(data)
    log(user.email, 'run.queue', row['name'])
    return row


def open_sheet(data, user):
    row = sheets.create_sheet(data, user)
    log(user.email, 'sheet.open', row['name'])
    return row


def open_sheet_version(sheet_id, user):
    row = sheets.open_version(sheet_id, user)
    log(user.email, 'sheet.version', str(sheet_id))
    return row


def set_review(enabled, reason, user):
    row = sheets.set_review_permission(enabled, reason, user.email)
    log(user.email, 'review.permission', f'enabled={enabled} reason={reason}')
    return row


def reclaim_version(sheet_id, version, user):
    row = sheets.reclaim(sheet_id, version, user.email)
    log(user.email, 'sheet.reclaim', f'{sheet_id} version={version}')
    return row
