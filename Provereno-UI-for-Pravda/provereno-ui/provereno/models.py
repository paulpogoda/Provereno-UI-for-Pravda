from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

def _utcnow():
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = "users"
    id            = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    github_id     = Column(Integer, unique=True, nullable=False)
    github_login  = Column(String(128), unique=True, nullable=False)
    role          = Column(String(16), default="editor", nullable=False)
    created_at    = Column(DateTime(timezone=True), default=_utcnow)
    last_login_at = Column(DateTime(timezone=True))

class Snapshot(Base):
    __tablename__ = "snapshots"
    id               = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    url              = Column(Text, nullable=False)
    final_url        = Column(Text)
    http_status      = Column(Integer)
    headers          = Column(JSON)
    mhtml_path       = Column(Text)
    mhtml_sha256     = Column(String(64))
    screenshot_path  = Column(Text)
    lifecycle_events = Column(JSON)
    condition_type   = Column(String(32), default="load")
    condition        = Column(Text)
    condition_met    = Column(Boolean, default=False)
    note             = Column(Text)
    captured_at      = Column(DateTime(timezone=True), default=_utcnow)
    creator          = Column(String(128))
    is_public        = Column(Boolean, default=False)
    url_status       = Column(String(16), default="unknown")
    job_id           = Column(String(36), ForeignKey("jobs.id"), nullable=True)

class Job(Base):
    __tablename__ = "jobs"
    id             = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    batch_id       = Column(String(36), nullable=True, index=True)
    url            = Column(Text, nullable=False)
    condition_type = Column(String(32))
    condition      = Column(Text)
    note           = Column(Text)
    tags           = Column(JSON)
    status         = Column(String(16), default="queued", index=True)
    snapshot_id    = Column(String(36), nullable=True)
    created_by     = Column(String(128))
    created_at     = Column(DateTime(timezone=True), default=_utcnow)
    started_at     = Column(DateTime(timezone=True))
    finished_at    = Column(DateTime(timezone=True))
    retry_count    = Column(Integer, default=0)
    error_message  = Column(Text)

class Tag(Base):
    __tablename__ = "tags"
    name = Column(String(64), primary_key=True)

class SnapshotTag(Base):
    __tablename__ = "snapshot_tags"
    snapshot_id = Column(String(36), ForeignKey("snapshots.id", ondelete="CASCADE"), primary_key=True)
    tag_name    = Column(String(64), ForeignKey("tags.name",     ondelete="CASCADE"), primary_key=True)

class Collection(Base):
    __tablename__ = "collections"
    id          = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name        = Column(String(128), nullable=False)
    description = Column(Text)
    created_by  = Column(String(128))
    created_at  = Column(DateTime(timezone=True), default=_utcnow)

class CollectionSnapshot(Base):
    __tablename__ = "collection_snapshots"
    collection_id = Column(String(36), ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True)
    snapshot_id   = Column(String(36), ForeignKey("snapshots.id",   ondelete="CASCADE"), primary_key=True)
    added_at      = Column(DateTime(timezone=True), default=_utcnow)

class UrlCheck(Base):
    __tablename__ = "url_checks"
    id          = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    snapshot_id = Column(String(36), ForeignKey("snapshots.id", ondelete="CASCADE"), nullable=False, index=True)
    status      = Column(String(16), nullable=False)
    http_status = Column(Integer)
    checked_at  = Column(DateTime(timezone=True), default=_utcnow)

class AuditLog(Base):
    __tablename__ = "audit_log"
    id                = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event             = Column(String(64), nullable=False, index=True)
    user_github_login = Column(String(128), index=True)
    ip                = Column(String(64))
    resource_type     = Column(String(32))
    resource_id       = Column(String(36))
    metadata_         = Column("metadata", JSON)
    created_at        = Column(DateTime(timezone=True), default=_utcnow, index=True)
