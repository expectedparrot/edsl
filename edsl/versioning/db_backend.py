"""
SQLAlchemy backend for persistent storage of versioned objects.

Provides database-backed storage for repositories, commits, states, and refs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Literal
import json

from sqlalchemy import create_engine, Column, String, Text, DateTime, ForeignKey, LargeBinary, Index
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship
from sqlalchemy.pool import StaticPool

from .models import Commit, Ref
from .utils import _utcnow

Base = declarative_base()


# ----------------------------
# SQLAlchemy Models
# ----------------------------

class RepoModel(Base):
    """Repository table."""
    __tablename__ = 'repos'

    repo_id = Column(String(64), primary_key=True)
    alias = Column(String(256), unique=True, nullable=True, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    commits = relationship("CommitModel", back_populates="repo", cascade="all, delete-orphan")
    states = relationship("StateModel", back_populates="repo", cascade="all, delete-orphan")
    refs = relationship("RefModel", back_populates="repo", cascade="all, delete-orphan")


class CommitModel(Base):
    """Commit table."""
    __tablename__ = 'commits'

    id = Column(String(128), primary_key=True)  # repo_id + commit_id
    repo_id = Column(String(64), ForeignKey('repos.repo_id'), nullable=False, index=True)
    commit_id = Column(String(64), nullable=False, index=True)
    parents = Column(Text, nullable=False)  # JSON array
    timestamp = Column(DateTime, nullable=False)
    message = Column(Text, nullable=False)
    event_name = Column(String(128), nullable=False)
    event_payload = Column(Text, nullable=False)  # JSON
    author = Column(String(256), default="unknown")
    state_id = Column(String(64), nullable=False)

    repo = relationship("RepoModel", back_populates="commits")

    __table_args__ = (
        Index('ix_commits_repo_commit', 'repo_id', 'commit_id'),
    )


class StateModel(Base):
    """State (blob) table."""
    __tablename__ = 'states'

    id = Column(String(128), primary_key=True)  # repo_id + state_id
    repo_id = Column(String(64), ForeignKey('repos.repo_id'), nullable=False, index=True)
    state_id = Column(String(64), nullable=False, index=True)
    data = Column(LargeBinary, nullable=False)

    repo = relationship("RepoModel", back_populates="states")

    __table_args__ = (
        Index('ix_states_repo_state', 'repo_id', 'state_id'),
    )


class RefModel(Base):
    """Ref (branch/tag) table."""
    __tablename__ = 'refs'

    id = Column(String(320), primary_key=True)  # repo_id + name
    repo_id = Column(String(64), ForeignKey('repos.repo_id'), nullable=False, index=True)
    name = Column(String(256), nullable=False)
    commit_id = Column(String(64), nullable=False)
    kind = Column(String(16), default="branch")
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    repo = relationship("RepoModel", back_populates="refs")

    __table_args__ = (
        Index('ix_refs_repo_name', 'repo_id', 'name'),
    )


# ----------------------------
# Database-backed Repository Storage
# ----------------------------

class DBRepoStorage:
    """Database-backed storage for a single repository."""

    def __init__(self, session: Session, repo_id: str):
        self.session = session
        self.repo_id = repo_id

    def _make_id(self, suffix: str) -> str:
        return f"{self.repo_id}:{suffix}"

    # --- State operations ---

    def has_state(self, state_id: str) -> bool:
        return self.session.query(StateModel).filter_by(
            repo_id=self.repo_id, state_id=state_id
        ).first() is not None

    def get_state_bytes(self, state_id: str) -> bytes:
        state = self.session.query(StateModel).filter_by(
            repo_id=self.repo_id, state_id=state_id
        ).first()
        if not state:
            raise KeyError(f"State {state_id} not found")
        return state.data

    def put_state_bytes(self, state_id: str, data: bytes) -> None:
        existing = self.session.query(StateModel).filter_by(
            repo_id=self.repo_id, state_id=state_id
        ).first()
        if not existing:
            state = StateModel(
                id=self._make_id(state_id),
                repo_id=self.repo_id,
                state_id=state_id,
                data=data,
            )
            self.session.add(state)
            self.session.commit()

    # --- Commit operations ---

    def has_commit(self, commit_id: str) -> bool:
        return self.session.query(CommitModel).filter_by(
            repo_id=self.repo_id, commit_id=commit_id
        ).first() is not None

    def get_commit(self, commit_id: str) -> Commit:
        cm = self.session.query(CommitModel).filter_by(
            repo_id=self.repo_id, commit_id=commit_id
        ).first()
        if not cm:
            raise KeyError(f"Commit {commit_id} not found")
        return Commit(
            commit_id=cm.commit_id,
            parents=tuple(json.loads(cm.parents)),
            timestamp=cm.timestamp,
            message=cm.message,
            event_name=cm.event_name,
            event_payload=json.loads(cm.event_payload),
            author=cm.author,
        )

    def put_commit(self, commit: Commit, state_id: str) -> None:
        existing = self.session.query(CommitModel).filter_by(
            repo_id=self.repo_id, commit_id=commit.commit_id
        ).first()
        if not existing:
            cm = CommitModel(
                id=self._make_id(commit.commit_id),
                repo_id=self.repo_id,
                commit_id=commit.commit_id,
                parents=json.dumps(list(commit.parents)),
                timestamp=commit.timestamp,
                message=commit.message,
                event_name=commit.event_name,
                event_payload=json.dumps(commit.event_payload),
                author=commit.author,
                state_id=state_id,
            )
            self.session.add(cm)
            self.session.commit()

    def get_commit_state_id(self, commit_id: str) -> str:
        cm = self.session.query(CommitModel).filter_by(
            repo_id=self.repo_id, commit_id=commit_id
        ).first()
        if not cm:
            raise KeyError(f"Commit {commit_id} not found")
        return cm.state_id

    # --- Ref operations ---

    def has_ref(self, name: str) -> bool:
        return self.session.query(RefModel).filter_by(
            repo_id=self.repo_id, name=name
        ).first() is not None

    def get_ref(self, name: str) -> Ref:
        rm = self.session.query(RefModel).filter_by(
            repo_id=self.repo_id, name=name
        ).first()
        if not rm:
            raise KeyError(f"Ref {name} not found")
        return Ref(
            name=rm.name,
            commit_id=rm.commit_id,
            kind=rm.kind,
            updated_at=rm.updated_at,
        )

    def upsert_ref(self, name: str, commit_id: str, kind: str = "branch") -> None:
        rm = self.session.query(RefModel).filter_by(
            repo_id=self.repo_id, name=name
        ).first()
        if rm:
            rm.commit_id = commit_id
            rm.kind = kind
            rm.updated_at = datetime.now(timezone.utc)
        else:
            rm = RefModel(
                id=self._make_id(name),
                repo_id=self.repo_id,
                name=name,
                commit_id=commit_id,
                kind=kind,
            )
            self.session.add(rm)
        self.session.commit()

    def delete_ref(self, name: str) -> None:
        rm = self.session.query(RefModel).filter_by(
            repo_id=self.repo_id, name=name
        ).first()
        if rm:
            self.session.delete(rm)
            self.session.commit()

    def list_refs(self) -> List[Ref]:
        refs = self.session.query(RefModel).filter_by(repo_id=self.repo_id).all()
        return [
            Ref(name=r.name, commit_id=r.commit_id, kind=r.kind, updated_at=r.updated_at)
            for r in refs
        ]

    # --- Stats ---

    def refs_count(self) -> int:
        return self.session.query(RefModel).filter_by(repo_id=self.repo_id).count()

    def commits_count(self) -> int:
        return self.session.query(CommitModel).filter_by(repo_id=self.repo_id).count()

    def states_count(self) -> int:
        return self.session.query(StateModel).filter_by(repo_id=self.repo_id).count()


# ----------------------------
# Database Manager
# ----------------------------

class DatabaseManager:
    """Manages database connections and repository access."""

    def __init__(self, db_url: str = "sqlite:///object_versions.db"):
        """
        Initialize database manager.

        Args:
            db_url: SQLAlchemy database URL. Defaults to SQLite file.
                    Use "sqlite:///:memory:" for in-memory testing.
        """
        # For SQLite, we need special handling for concurrent access
        if db_url.startswith("sqlite"):
            self.engine = create_engine(
                db_url,
                connect_args={"check_same_thread": False, "timeout": 30},
                poolclass=StaticPool,
            )
        else:
            self.engine = create_engine(db_url)

        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()

    def create_repo(
        self,
        repo_id: str,
        alias: Optional[str] = None,
        description: Optional[str] = None,
    ) -> RepoModel:
        """Create a new repository."""
        session = self.get_session()
        try:
            repo = RepoModel(
                repo_id=repo_id,
                alias=alias,
                description=description,
            )
            session.add(repo)
            session.commit()
            session.refresh(repo)
            return repo
        finally:
            session.close()

    def get_or_create_repo(
        self,
        alias: str,
        repo_id: Optional[str] = None,
        description: Optional[str] = None,
    ) -> tuple[RepoModel, bool]:
        """
        Get existing repo by alias or create a new one.

        Returns:
            Tuple of (repo, created) where created is True if a new repo was created.
        """
        session = self.get_session()
        try:
            existing = session.query(RepoModel).filter_by(alias=alias).first()
            if existing:
                return existing, False

            import uuid
            new_repo_id = repo_id or uuid.uuid4().hex
            repo = RepoModel(
                repo_id=new_repo_id,
                alias=alias,
                description=description,
            )
            session.add(repo)
            session.commit()
            session.refresh(repo)
            return repo, True
        finally:
            session.close()

    def get_repo(self, repo_id: str) -> Optional[RepoModel]:
        """Get repository by ID."""
        session = self.get_session()
        try:
            return session.query(RepoModel).filter_by(repo_id=repo_id).first()
        finally:
            session.close()

    def get_repo_by_alias(self, alias: str) -> Optional[RepoModel]:
        """Get repository by alias."""
        session = self.get_session()
        try:
            return session.query(RepoModel).filter_by(alias=alias).first()
        finally:
            session.close()

    def list_repos(self) -> List[RepoModel]:
        """List all repositories."""
        session = self.get_session()
        try:
            return session.query(RepoModel).all()
        finally:
            session.close()

    def get_repo_storage(self, repo_id: str) -> DBRepoStorage:
        """Get storage interface for a repository."""
        session = self.get_session()
        return DBRepoStorage(session, repo_id)

    def set_alias(self, repo_id: str, alias: str) -> None:
        """Set or update repository alias."""
        session = self.get_session()
        try:
            repo = session.query(RepoModel).filter_by(repo_id=repo_id).first()
            if repo:
                repo.alias = alias
                session.commit()
        finally:
            session.close()

    def get_stats(self) -> Dict[str, int]:
        """Get overall statistics."""
        session = self.get_session()
        try:
            return {
                "repos_count": session.query(RepoModel).count(),
                "total_commits": session.query(CommitModel).count(),
                "total_states": session.query(StateModel).count(),
                "total_refs": session.query(RefModel).count(),
            }
        finally:
            session.close()

    def get_recent_commits(self, limit: int = 15) -> List[Dict[str, Any]]:
        """Get recent commits across all repos."""
        session = self.get_session()
        try:
            commits = (
                session.query(CommitModel, RepoModel)
                .join(RepoModel)
                .order_by(CommitModel.timestamp.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "repo_id": repo.repo_id,
                    "alias": repo.alias,
                    "commit_id": commit.commit_id,
                    "message": commit.message,
                    "event_name": commit.event_name,
                    "author": commit.author,
                    "timestamp": commit.timestamp,
                }
                for commit, repo in commits
            ]
        finally:
            session.close()
