from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey, UniqueConstraint, Index, func
from src.config.database import Base


class SystemSetting(Base):
    """系统级开关，例如核对权限是否在有效期/授权内。"""
    __tablename__ = 'system_settings'
    id = Column(Integer, primary_key=True)
    key = Column(String(60), unique=True, nullable=False)
    value = Column(JSON, nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class HandoverSheet(Base):
    """按批次开的交班核对单；一份单冻结一个或多个不可变版本。"""
    __tablename__ = 'handover_sheets'
    id = Column(Integer, primary_key=True)
    name = Column(String(120), unique=True, nullable=False)
    batch_id = Column(Integer, ForeignKey('batches.id'), nullable=False)
    # active / revoked / expired / reclaimed
    status = Column(String(20), nullable=False, default='active')
    current_version = Column(Integer, nullable=False, default=1)
    created_by = Column(String(120), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked_reason = Column(String(500), nullable=True)
    last_revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class SheetVersion(Base):
    """开单/开新版本时刻的冻结快照；分页只读快照，不随并发落库变化。"""
    __tablename__ = 'handover_sheet_versions'
    __table_args__ = (UniqueConstraint('sheet_id', 'version'),)
    id = Column(Integer, primary_key=True)
    sheet_id = Column(Integer, ForeignKey('handover_sheets.id'), nullable=False)
    version = Column(Integer, nullable=False)
    # 批次与运行清单冻结证据（含开单时刻批次行）
    snapshot = Column(JSON, nullable=False)
    runs_snapshot = Column(JSON, nullable=False)
    targets_snapshot = Column(JSON, nullable=False)
    rejected_snapshot = Column(JSON, nullable=False)
    summary = Column(JSON, nullable=False)
    # 0 保留可续页；1 已回收（快照载荷清空，仅留摘要与翻页元数据）
    reclaimed = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now())
    reclaimed_at = Column(DateTime, nullable=True)


class SheetPage(Base):
    """已交付翻页游标：重启后据此续查，保证不漏不重。"""
    __tablename__ = 'handover_sheet_pages'
    __table_args__ = (
        UniqueConstraint('version_id', 'section', 'page'),
        Index('ix_sheet_pages_version_section', 'version_id', 'section'),
    )
    id = Column(Integer, primary_key=True)
    sheet_id = Column(Integer, ForeignKey('handover_sheets.id'), nullable=False)
    version_id = Column(Integer, ForeignKey('handover_sheet_versions.id'), nullable=False)
    # runs / targets / rejected
    section = Column(String(20), nullable=False)
    page = Column(Integer, nullable=False)
    page_size = Column(Integer, nullable=False)
    offset = Column(Integer, nullable=False)
    total = Column(Integer, nullable=False)
    next_offset = Column(Integer, nullable=False)
    finished = Column(Integer, nullable=False, default=0)
    delivered_key = Column(String(128), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
