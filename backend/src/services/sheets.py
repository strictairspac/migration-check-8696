"""交班核对单：按批次开单、版本冻结、游标续页、权限失效与旧版本回收。

设计要点：
- 开单/开新版本时把批次、运行清单、目标行、拒绝行复制进不可变 JSON 快照；
  此后新迁移与备份恢复继续并发落库，均不影响已开版本，同一张单始终读开单时的版本。
- 续页游标持久化在 handover_sheet_pages，进程重启后仍可续查；按 (版本, 分区, 页号)
  唯一约束 + 单据行锁串行分配，翻页不漏不重，且无须为整单长占事务。
- 权限撤回/到期/回收均让续页显式失效并返回原因；重新授权不复活旧单。
"""
import time
import random
from datetime import datetime, timezone, timedelta

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from src.config.database import Session
from src.constants.enums import (
    SHEET_SECTIONS,
    DEFAULT_SHEET_TTL_MINUTES,
    MIN_SHEET_TTL_MINUTES,
    MAX_SHEET_TTL_MINUTES,
    MAX_PAGE_SIZE,
)
from src.models.batch import Batch
from src.models.run import Run, TargetRow
from src.models.sheet import HandoverSheet, SheetVersion, SheetPage, SystemSetting
from src.services.migration import digest
from src.utils.serialization import record


def _now():
    return datetime.now(timezone.utc)


def _aware(dt):
    # PG 无时区时间列读回为 naive，统一按 UTC 解释，避免与 aware 的 now 比较报错
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _iso(value):
    return _aware(value).isoformat() if value is not None else None


def _review_setting(s):
    row = s.query(SystemSetting).filter_by(key='review_enabled').first()
    if not row:
        row = SystemSetting(key='review_enabled', value={'enabled': True})
        s.add(row)
        s.flush()
    return row


def review_enabled(s):
    return bool(_review_setting(s).value.get('enabled', True))


def _run_view(run):
    result = run.result or {}
    return {
        'id': run.id,
        'name': run.name,
        'status': run.status,
        'created_at': _iso(run.created_at),
        'error': run.error,
        'source_count': result.get('source_count'),
        'accepted_count': result.get('accepted_count'),
        'rejected_count': result.get('rejected_count'),
        'checksum': result.get('checksum'),
    }


def _collect(s, batch):
    """在同一事务内读取开单时刻的已提交数据并拷贝为普通 JSON 结构。"""
    runs = s.query(Run).filter_by(batch_id=batch.id).order_by(Run.id).all()
    run_ids = [r.id for r in runs]
    if run_ids:
        target_rows = [
            row.payload
            for row in s.query(TargetRow)
            .filter(TargetRow.run_id.in_(run_ids))
            .order_by(TargetRow.run_id, TargetRow.ordinal)
            .all()
        ]
    else:
        target_rows = []
    rejected = []
    for run in runs:
        if run.status == 'completed' and run.result:
            for item in run.result.get('rejected_rows', []):
                rejected.append({'run_id': run.id, **item})
    rejected.sort(key=lambda x: (x['run_id'], x['row_number']))
    runs_view = [_run_view(r) for r in runs]
    return runs_view, target_rows, rejected


def _build_version(s, sheet, version_no):
    batch = s.get(Batch, sheet.batch_id)
    if not batch:
        raise HTTPException(404, '未找到源批次')
    runs_view, targets, rejected = _collect(s, batch)
    summary = {
        'runs': len(runs_view),
        'targets': len(targets),
        'rejected': len(rejected),
        'batch_rows': len(batch.rows),
        'batch_checksum': digest(batch.rows),
        'targets_checksum': digest(targets),
        'rejected_checksum': digest(rejected),
    }
    return SheetVersion(
        sheet_id=sheet.id,
        version=version_no,
        snapshot={'batch': record(batch), 'opened_at': _iso(_now()), 'version': version_no},
        runs_snapshot=runs_view,
        targets_snapshot=targets,
        rejected_snapshot=rejected,
        summary=summary,
    )


def _invalid_reason(sheet, now):
    """返回单据当前失效原因；生效中返回 None。"""
    if sheet.status == 'revoked':
        return {
            'code': 'sheet_revoked',
            'message': '管理员已撤回核对权限，旧单不能继续续页，重新授权也不启用本单',
            'reason': sheet.revoked_reason or '管理员撤回核对权限',
            'at': _iso(sheet.last_revoked_at),
        }
    if sheet.status == 'expired' or (sheet.status == 'active' and _aware(sheet.expires_at) <= now):
        return {
            'code': 'sheet_expired',
            'message': '核对单已到期，请重新开单',
            'expires_at': _iso(sheet.expires_at),
        }
    if sheet.status == 'reclaimed':
        return {
            'code': 'sheet_reclaimed',
            'message': '核对单版本已回收，请重新开单',
        }
    return None


def _sweep_expired(s, now):
    # 列为无时区时间，绑定 naive UTC；Python 侧比较仍用 aware
    naive = now.replace(tzinfo=None)
    due = s.query(HandoverSheet).filter_by(status='active').filter(HandoverSheet.expires_at <= naive).all()
    for sheet in due:
        sheet.status = 'expired'
    return due


def _payload(version, section):
    return {
        'runs': version.runs_snapshot or [],
        'targets': version.targets_snapshot or [],
        'rejected': version.rejected_snapshot or [],
    }[section]


def list_items():
    with Session() as s:
        now = _now()
        _sweep_expired(s, now)
        s.commit()
        sheets = s.query(HandoverSheet).order_by(HandoverSheet.id.desc()).all()
        return [_summary(s, sheet, now) for sheet in sheets]


def _summary(s, sheet, now=None):
    now = now or _now()
    version = (
        s.query(SheetVersion)
        .filter_by(sheet_id=sheet.id, version=sheet.current_version)
        .first()
    )
    return {
        **record(sheet),
        'expires_at': _iso(sheet.expires_at),
        'invalid': _invalid_reason(sheet, now),
        'current_summary': version.summary if version else None,
    }


def detail(sheet_id):
    with Session() as s:
        sheet = s.query(HandoverSheet).filter_by(id=sheet_id).with_for_update().first()
        if not sheet:
            raise HTTPException(404, '未找到交班核对单')
        now = _now()
        _sweep_expired(s, now)
        versions = (
            s.query(SheetVersion).filter_by(sheet_id=sheet.id).order_by(SheetVersion.version).all()
        )
        version_views = []
        for version in versions:
            pages = s.query(SheetPage).filter_by(version_id=version.id).all()
            progress = {}
            for section in SHEET_SECTIONS:
                section_pages = [p for p in pages if p.section == section]
                last = section_pages[-1] if section_pages else None
                progress[section] = {
                    'delivered_pages': len(section_pages),
                    'last_page': last.page if last else 0,
                    'finished': bool(last.finished) if last else False,
                    'total': version.summary.get(section if section != 'runs' else 'runs'),
                }
            version_views.append({
                'version': version.version,
                'current': version.version == sheet.current_version,
                'reclaimed': bool(version.reclaimed),
                'reclaimed_at': _iso(version.reclaimed_at),
                'created_at': _iso(version.created_at),
                'summary': version.summary,
                'progress': progress,
            })
        s.commit()
        return {
            **_summary(s, sheet, now),
            'review_enabled': review_enabled(s),
            'versions': version_views,
        }


def create_sheet(data, user):
    ttl = data.ttl_minutes
    if not MIN_SHEET_TTL_MINUTES <= ttl <= MAX_SHEET_TTL_MINUTES:
        raise HTTPException(422, f'有效期需在 {MIN_SHEET_TTL_MINUTES}-{MAX_SHEET_TTL_MINUTES} 分钟之间')
    with Session() as s:
        if not review_enabled(s):
            raise HTTPException(403, {'code': 'review_disabled', 'message': '核对权限已被撤回，不能新开核对单'})
        batch = s.get(Batch, data.batch_id)
        if not batch:
            raise HTTPException(404, '未找到源批次')
        now = _now()
        sheet = HandoverSheet(
            name=data.name,
            batch_id=batch.id,
            status='active',
            current_version=1,
            created_by=user.email,
            expires_at=now + timedelta(minutes=ttl),
        )
        s.add(sheet)
        s.flush()
        s.add(_build_version(s, sheet, 1))
        s.commit()
        s.refresh(sheet)
        return _summary(s, sheet, now)


def open_version(sheet_id, user):
    with Session() as s:
        sheet = s.query(HandoverSheet).filter_by(id=sheet_id).with_for_update().first()
        if not sheet:
            raise HTTPException(404, '未找到交班核对单')
        now = _now()
        _sweep_expired(s, now)
        invalid = _invalid_reason(sheet, now)
        if invalid:
            raise HTTPException(409, invalid)
        if not review_enabled(s):
            raise HTTPException(403, {'code': 'review_disabled', 'message': '核对权限已被撤回，不能开新版本'})
        next_no = sheet.current_version + 1
        s.add(_build_version(s, sheet, next_no))
        sheet.current_version = next_no
        s.commit()
        return detail(sheet_id)


def set_review_permission(enabled, reason, actor):
    with Session() as s:
        setting = _review_setting(s)
        now = _now()
        setting.value = {
            'enabled': enabled,
            'reason': reason,
            'actor': actor,
            'at': _iso(now),
        }
        if not enabled:
            # 撤回：所有生效中的单立即失效；到期/已回收单保持原终态
            for sheet in s.query(HandoverSheet).filter_by(status='active').all():
                sheet.status = 'revoked'
                sheet.revoked_reason = reason or '管理员撤回核对权限'
                sheet.last_revoked_at = now
        # 重新授权不改动任何旧单：revoked/expired/reclaimed 均不复活
        s.commit()
        return {'enabled': enabled, 'reason': reason, 'at': _iso(now)}


def get_review_permission():
    with Session() as s:
        setting = _review_setting(s)
        s.commit()
        return setting.value


def reclaim(sheet_id, version_no, actor):
    with Session() as s:
        sheet = s.query(HandoverSheet).filter_by(id=sheet_id).with_for_update().first()
        if not sheet:
            raise HTTPException(404, '未找到交班核对单')
        now = _now()
        _sweep_expired(s, now)
        if sheet.status == 'active':
            raise HTTPException(409, {
                'code': 'sheet_active',
                'message': '核对单仍在有效期内，到期或撤回后才能回收旧版本',
                'expires_at': _iso(sheet.expires_at),
            })
        target_no = version_no or sheet.current_version
        version = (
            s.query(SheetVersion)
            .filter_by(sheet_id=sheet.id, version=target_no)
            .with_for_update()
            .first()
        )
        if not version:
            raise HTTPException(404, '未找到该版本')
        if not version.reclaimed:
            version.reclaimed = 1
            version.reclaimed_at = now
            # 仅清空载荷，保留摘要与翻页元数据作为失效凭据
            version.runs_snapshot, version.targets_snapshot, version.rejected_snapshot = [], [], []
            if version.version == sheet.current_version:
                sheet.status = 'reclaimed'
            s.commit()
        return detail(sheet_id)


def read_page(sheet_id, section, page_size=None, page_no=None):
    if section not in SHEET_SECTIONS:
        raise HTTPException(404, '分区只支持 runs / targets / rejected')
    # 并发续页：PostgreSQL 行锁先串行化；唯一约束冲突作为兜底整体重试。
    # 每次重试使用全新 Session，避免回滚后的陈旧瞬态对象被当作结果返回。
    # 指数退避 + 抖动，缓解无行锁存储（如本地 SQLite）下的惊群。
    max_attempts = 20
    for attempt in range(max_attempts):
        try:
            with Session() as s:
                return _read_page_once(s, sheet_id, section, page_size, page_no)
        except IntegrityError:
            if attempt == max_attempts - 1:
                raise
            time.sleep(min(0.1, 0.002 * (2 ** attempt)) + random.uniform(0, 0.003))
        except HTTPException:
            raise


def _read_page_once(s, sheet_id, section, page_size=None, page_no=None):
    # 锁单据行使并发续页串行分配游标；锁仅在单次请求内持有，不长占事务
    sheet = s.query(HandoverSheet).filter_by(id=sheet_id).with_for_update().first()
    if not sheet:
        raise HTTPException(404, '未找到交班核对单')
    now = _now()
    _sweep_expired(s, now)
    invalid = _invalid_reason(sheet, now)
    if invalid:
        s.commit()
        raise HTTPException(409, invalid)
    version = (
        s.query(SheetVersion)
        .filter_by(sheet_id=sheet.id, version=sheet.current_version)
        .with_for_update()
        .first()
    )
    if not version:
        raise HTTPException(409, {'code': 'version_missing', 'message': '当前版本缺失，请重新开单'})
    if version.reclaimed:
        s.commit()
        raise HTTPException(409, {
            'code': 'version_reclaimed',
            'message': '当前版本已回收，续页无法补读，请重新开单',
            'reclaimed_at': _iso(version.reclaimed_at),
        })
    pages = (
        s.query(SheetPage)
        .filter_by(version_id=version.id, section=section)
        .order_by(SheetPage.page)
        .all()
    )
    if pages:
        # 页幅以首页为准，中途改页幅不会打乱游标
        page_size = pages[0].page_size
    else:
        page_size = min(max(page_size or 50, 1), MAX_PAGE_SIZE)
    data = _payload(version, section)
    total = len(data)

    if page_no is not None:
        existing = next((p for p in pages if p.page == page_no), None)
        if existing:
            rows = data[existing.offset:existing.offset + existing.page_size]
            s.commit()
            return _envelope(sheet, version, section, existing, rows, now, replay=True)
        expected = pages[-1].page + 1 if pages else 1
        if page_no != expected:
            s.commit()
            raise HTTPException(409, {
                'code': 'page_out_of_order',
                'message': f'请从第 {expected} 页续查，不能跳页',
                'expected_page': expected,
            })

    if pages:
        last = pages[-1]
        if last.finished:
            # 已读完后的重复请求幂等返回，不重复分配
            s.commit()
            return _done_envelope(sheet, version, section, last, now)
        offset, page = last.next_offset, last.page + 1
    else:
        offset, page = 0, 1

    rows = data[offset:offset + page_size]
    next_offset = offset + len(rows)
    finished = next_offset >= total
    delivered = SheetPage(
        sheet_id=sheet.id,
        version_id=version.id,
        section=section,
        page=page,
        page_size=page_size,
        offset=offset,
        total=total,
        next_offset=next_offset,
        finished=1 if finished else 0,
        delivered_key=digest(rows),
    )
    s.add(delivered)
    s.commit()
    return _envelope(sheet, version, section, delivered, rows, now, replay=False)


def _envelope(sheet, version, section, page_row, rows, now, replay):
    remaining = max(int((_aware(sheet.expires_at) - now).total_seconds()), 0)
    return {
        'sheet_id': sheet.id,
        'sheet_name': sheet.name,
        'sheet_status': sheet.status,
        'version': version.version,
        'section': section,
        'page': page_row.page,
        'page_size': page_row.page_size,
        'offset': page_row.offset,
        'next_offset': page_row.next_offset,
        'total': page_row.total,
        'count': len(rows),
        'finished': bool(page_row.finished),
        'replay': replay,
        'delivered_key': page_row.delivered_key,
        'rows': rows,
        'expires_at': _iso(sheet.expires_at),
        'remaining_seconds': remaining,
    }


def _done_envelope(sheet, version, section, last, now):
    return {
        'sheet_id': sheet.id,
        'sheet_name': sheet.name,
        'sheet_status': sheet.status,
        'version': version.version,
        'section': section,
        'page': last.page,
        'page_size': last.page_size,
        'offset': last.next_offset,
        'next_offset': last.next_offset,
        'total': last.total,
        'count': 0,
        'finished': True,
        'replay': False,
        'delivered_key': last.delivered_key,
        'rows': [],
        'expires_at': _iso(sheet.expires_at),
        'remaining_seconds': max(int((_aware(sheet.expires_at) - now).total_seconds()), 0),
        'message': '该分区已全部读完',
    }
