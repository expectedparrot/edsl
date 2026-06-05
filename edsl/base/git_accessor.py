"""Generic descriptor/accessor plumbing for Git-backed EDSL objects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional, Type

from edsl.base import git_package as gitpkg


@dataclass(frozen=True)
class GitObjectSpec:
    object_type: str
    package_suffix: str
    default_name: str
    error_cls: Type[Exception]
    warning_cls: Type[Warning]
    warned_paths: set[Path]
    package_cls: Type[gitpkg.GitPackage]
    read: Callable[[Path, str], Any]
    write: Callable[[Path, Any], dict]
    refresh: Callable[[Any, Any], None]
    accessor_key: str
    default_commit_message: str
    clone_return: Callable[[Any], Any] | None = None

    def normalize_path(self, path, *, for_load: bool = False) -> Path:
        return gitpkg.normalize_package_path(
            path, package_suffix=self.package_suffix, for_load=for_load
        )

    def default_path(self) -> Path:
        return self.normalize_path(self.default_name)

    def display_name(self, path: Path) -> str:
        name = path.name
        if name.endswith(self.package_suffix):
            return name[: -len(self.package_suffix)]
        return path.stem


class GitBackedDescriptor:
    def __init__(self, spec_factory: Callable[[], GitObjectSpec]) -> None:
        self._spec_factory = spec_factory

    @property
    def spec(self) -> GitObjectSpec:
        return self._spec_factory()

    def __get__(self, obj, objtype=None):
        if obj is None:
            return GitBackedClassAccessor(self.spec, objtype)
        accessor = obj.__dict__.get(self.spec.accessor_key)
        if accessor is None:
            accessor = GitBackedInstanceAccessor(self.spec, obj)
            obj.__dict__[self.spec.accessor_key] = accessor
        return accessor


class GitBackedClassAccessor:
    def __init__(self, spec: GitObjectSpec, objtype=None):
        self._spec = spec
        self._objtype = objtype

    def load(self, path, ref: str = "HEAD"):
        path = self._spec.normalize_path(path, for_load=True)
        gitpkg.ensure_git_available()
        gitpkg.ensure_package_repo(path)
        obj = self._spec.read(path, ref)
        obj.git.path = path
        obj.git.commit = gitpkg.resolve_commit(path, ref, error_cls=self._spec.error_cls)
        obj.git.current_branch = gitpkg.current_branch(path, error_cls=self._spec.error_cls)
        if hasattr(obj.git, "_after_load"):
            obj.git._after_load(obj)
        return obj

    def open(self, path):
        return self._spec.package_cls(path)

    def clone(self, url: str, path, ref: str = "HEAD", token: Optional[str] = None):
        gitpkg.ensure_git_available()
        destination = gitpkg.clone_destination(path, package_suffix=self._spec.package_suffix)
        if destination.exists():
            raise self._spec.error_cls(
                ["git", "clone", url, str(destination)],
                stderr=f"Destination path already exists: {destination}",
            )
        gitpkg.run_git(
            ["git", *gitpkg.http_auth_git_args(url, token), "clone", url, str(destination)],
            error_cls=self._spec.error_cls,
        )
        loaded = self.load(destination.resolve(), ref=ref)
        return self._spec.clone_return(loaded) if self._spec.clone_return else loaded

    def objects(
        self,
        token: Optional[str] = None,
        server_url: Optional[str] = None,
        object_type: Optional[str] = None,
    ) -> dict:
        return gitpkg.server_objects(
            token=token,
            server_url=server_url,
            object_type=object_type or self._spec.object_type,
            error_cls=self._spec.error_cls,
        )


class GitBackedInstanceAccessor(GitBackedClassAccessor):
    def __init__(self, spec: GitObjectSpec, instance: Any) -> None:
        super().__init__(spec, type(instance))
        self._instance = instance
        self.path: Optional[Path] = None
        self.commit: Optional[str] = None
        self.current_branch: Optional[str] = None

    def save(self, path=None, message: str = "", **kwargs) -> dict:
        if path is None:
            path = self.path or self._spec.default_path()
        path = self._spec.normalize_path(path)
        gitpkg.ensure_git_available()
        gitpkg.warn_if_nested_in_outer_repo(
            path,
            warned_paths=self._spec.warned_paths,
            warning_cls=self._spec.warning_cls,
        )
        if (path / ".git").exists():
            gitpkg.ensure_clean(path, "save", error_cls=self._spec.error_cls)
        gitpkg.init_package(path, error_cls=self._spec.error_cls)

        extra_info = self._spec.write(path, self._instance, **kwargs)
        for key, value in extra_info.items():
            if key.isidentifier():
                setattr(self, key, value)
        gitpkg.git(path, "add", "-A", "--", ".", error_cls=self._spec.error_cls)
        if not gitpkg.has_staged_changes(path):
            commit = gitpkg.head_commit(path, error_cls=self._spec.error_cls)
            self.path = path
            self.commit = commit
            self.current_branch = gitpkg.current_branch(path, error_cls=self._spec.error_cls)
            for key, value in extra_info.items():
                if key.isidentifier():
                    setattr(self, key, value)
            return {
                "status": "unchanged",
                "path": str(path),
                "commit": commit,
                "branch": self.current_branch,
                "message": "no changes",
                **extra_info,
            }

        commit_message = message or self._spec.default_commit_message
        gitpkg.git(
            path,
            "-c",
            "user.name=EDSL",
            "-c",
            "user.email=edsl@example.invalid",
            "commit",
            "-m",
            commit_message,
            error_cls=self._spec.error_cls,
        )
        commit = gitpkg.head_commit(path, error_cls=self._spec.error_cls)
        self.path = path
        self.commit = commit
        self.current_branch = gitpkg.current_branch(path, error_cls=self._spec.error_cls)
        for key, value in extra_info.items():
            if key.isidentifier():
                setattr(self, key, value)
        return {
            "status": "ok",
            "path": str(path),
            "commit": commit,
            "branch": self.current_branch,
            "message": commit_message,
            **extra_info,
        }

    def _after_load(self, obj) -> None:
        pass

    def log(self) -> list[dict]:
        return self._bound_package().log()

    def history(self) -> list[dict]:
        return self.log()

    def branches(self) -> list[str]:
        return self._bound_package().branches()

    def branch(self, name: str) -> None:
        self._bound_package().branch(name)
        self.current_branch = gitpkg.current_branch(self.path, error_cls=self._spec.error_cls)

    def checkout(self, ref: str) -> None:
        self._bound_package().checkout(ref)
        self.current_branch = gitpkg.current_branch(self.path, error_cls=self._spec.error_cls)
        self.commit = gitpkg.head_commit(self.path, error_cls=self._spec.error_cls)

    def switch(self, name: str) -> None:
        self._bound_package().switch(name)
        loaded = type(self._instance).git.load(self.path)
        self._spec.refresh(self._instance, loaded)
        self._copy_loaded_accessor_state(loaded)
        self.current_branch = gitpkg.current_branch(self.path, error_cls=self._spec.error_cls)
        self.commit = gitpkg.head_commit(self.path, error_cls=self._spec.error_cls)

    def restore(self, ref: str = "HEAD") -> dict:
        loaded = type(self._instance).git.load(self.path, ref=ref)
        self._spec.refresh(self._instance, loaded)
        self._copy_loaded_accessor_state(loaded)
        self.commit = loaded.git.commit
        self.current_branch = gitpkg.current_branch(self.path, error_cls=self._spec.error_cls)
        return {
            "status": "ok",
            "path": str(self.path),
            "ref": ref,
            "commit": self.commit,
            "message": f"restored {self._spec.object_type} from {ref}",
        }

    def diff(self, *refs: str) -> str:
        return self._bound_package().diff(*refs)

    def tags(self) -> list[str]:
        return self._bound_package().tags()

    def tag(self, name: str, message: Optional[str] = None) -> dict:
        return self._bound_package().tag(name, message=message)

    def status(self) -> dict:
        return self._bound_package().status()

    def remotes(self) -> dict[str, str]:
        return self._bound_package().remotes()

    def remote_add(self, name: str, url: str) -> dict:
        return self._bound_package().remote_add(name, url)

    def remote_remove(self, name: str) -> dict:
        return self._bound_package().remote_remove(name)

    def remote_set_url(self, name: str, url: str) -> dict:
        return self._bound_package().remote_set_url(name, url)

    def fetch(self, remote: Optional[str] = None, branch: Optional[str] = None, token: Optional[str] = None) -> dict:
        return self._bound_package().fetch(remote=remote, branch=branch, token=token)

    def validate(self) -> dict:
        return self._bound_package().validate()

    def ignore_in_parent(self) -> dict:
        return self._bound_package().ignore_in_parent()

    def push(self, remote: Optional[str] = None, branch: Optional[str] = None, token: Optional[str] = None, path=None) -> dict:
        if self.path is None:
            self.save(path or self._spec.default_path())
        info = self._bound_package().push(remote=remote, branch=branch, token=token)
        self.commit = info["commit"]
        self.current_branch = info["branch"]
        return info

    def pull(self, remote: Optional[str] = None, branch: Optional[str] = None, token: Optional[str] = None) -> dict:
        info = self._bound_package().pull(remote=remote, branch=branch, token=token)
        loaded = type(self._instance).git.load(self.path)
        self._spec.refresh(self._instance, loaded)
        self._copy_loaded_accessor_state(loaded)
        self.commit = info["commit"]
        self.current_branch = info["branch"]
        return info

    def _bound_package(self):
        if self.path is None:
            raise ValueError(f"This {self._spec.object_type} is not bound to a git package path.")
        return self._spec.package_cls(self.path)

    def _copy_loaded_accessor_state(self, loaded) -> None:
        loaded_accessor = loaded.git
        for key, value in vars(loaded_accessor).items():
            if key.startswith("_") or key in {"path", "commit", "current_branch"}:
                continue
            setattr(self, key, value)
