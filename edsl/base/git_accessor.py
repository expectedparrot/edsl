"""Generic descriptor/accessor plumbing for Git-backed EDSL objects."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Type

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
        worktree_path = gitpkg.unpack_package_archive(
            path,
            package_suffix=self._spec.package_suffix,
            error_cls=self._spec.error_cls,
        )
        obj = self._spec.read(worktree_path, ref)
        obj.git.path = path
        obj.git.worktree_path = worktree_path
        obj.git.commit = gitpkg.resolve_commit(
            worktree_path, ref, error_cls=self._spec.error_cls
        )
        obj.git.current_branch = gitpkg.current_branch(
            worktree_path, error_cls=self._spec.error_cls
        )
        if hasattr(obj.git, "_after_load"):
            obj.git._after_load(obj)
        if ref == "HEAD":
            obj.git._coop_pull_if_remote_updated(
                message=f"Coop sync {self._spec.object_type}"
            )
        return obj

    def open(self, path):
        path = self._spec.normalize_path(path, for_load=True)
        worktree_path = gitpkg.unpack_package_archive(
            path,
            package_suffix=self._spec.package_suffix,
            error_cls=self._spec.error_cls,
        )
        package = self._spec.package_cls(worktree_path)
        package.public_path = path
        return package

    def clone(self, url: str, path, ref: str = "HEAD", token: Optional[str] = None):
        gitpkg.ensure_git_available()
        destination = gitpkg.clone_destination(
            path, package_suffix=self._spec.package_suffix
        )
        if destination.exists():
            raise self._spec.error_cls(
                ["git", "clone", url, str(destination)],
                stderr=f"Destination path already exists: {destination}",
            )
        worktree_path = gitpkg.new_package_worktree(destination)
        gitpkg.run_git(
            ["git", "clone", url, str(worktree_path)],
            error_cls=self._spec.error_cls,
            env=gitpkg.http_auth_git_env(url, token),
        )
        gitpkg.pack_package_archive(
            worktree_path, destination, package_suffix=self._spec.package_suffix
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

    def coop_clone(
        self,
        url_or_uuid,
        path,
        *,
        expected_parrot_url: Optional[str] = None,
        message: str = "",
    ) -> Any:
        if self._objtype is None:
            raise ValueError("coop_clone must be called on a Git-backed EDSL class.")
        destination = self._spec.normalize_path(path)
        if destination.exists():
            raise self._spec.error_cls(
                ["coop", "clone", str(url_or_uuid), str(destination)],
                stderr=f"Destination path already exists: {destination}",
            )

        from edsl.coop import Coop

        coop = Coop(url=expected_parrot_url)
        coop_info = _plain_dict(coop.get_metadata(url_or_uuid))
        obj = self._objtype.pull(url_or_uuid, expected_parrot_url=expected_parrot_url)
        obj.git._save_overwriting_package(
            destination,
            message=message or f"Coop clone {self._spec.object_type}",
            coop_info=coop_info,
        )
        return obj


class GitBackedInstanceAccessor(GitBackedClassAccessor):
    def __init__(self, spec: GitObjectSpec, instance: Any) -> None:
        super().__init__(spec, type(instance))
        self._instance = instance
        self.path: Optional[Path] = None
        self.worktree_path: Optional[Path] = None
        self.commit: Optional[str] = None
        self.current_branch: Optional[str] = None

    def save(self, path=None, message: str = "", **kwargs) -> dict:
        if path is None:
            path = self.path or self._spec.default_path()
        path = self._spec.normalize_path(path)
        gitpkg.ensure_git_available()
        if self.worktree_path is None or self.path != path:
            if path.exists():
                self.worktree_path = gitpkg.unpack_package_archive(
                    path,
                    package_suffix=self._spec.package_suffix,
                    error_cls=self._spec.error_cls,
                )
            else:
                self.worktree_path = gitpkg.new_package_worktree(path)
        worktree_path = self.worktree_path
        if (worktree_path / ".git").exists():
            gitpkg.ensure_clean(worktree_path, "save", error_cls=self._spec.error_cls)
            self.path = path
            self._coop_pull_if_remote_updated(
                message=f"Coop sync {self._spec.object_type}"
            )
        gitpkg.init_package(worktree_path, error_cls=self._spec.error_cls)

        extra_info = self._spec.write(worktree_path, self._instance, **kwargs)
        for key, value in extra_info.items():
            if key.isidentifier():
                setattr(self, key, value)
        gitpkg.git(
            worktree_path, "add", "-A", "--", ".", error_cls=self._spec.error_cls
        )
        if not gitpkg.has_staged_changes(worktree_path):
            commit = gitpkg.head_commit(worktree_path, error_cls=self._spec.error_cls)
            self.path = path
            self.commit = commit
            self.current_branch = gitpkg.current_branch(
                worktree_path, error_cls=self._spec.error_cls
            )
            gitpkg.pack_package_archive(
                worktree_path, path, package_suffix=self._spec.package_suffix
            )
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
            worktree_path,
            "-c",
            "user.name=EDSL",
            "-c",
            "user.email=edsl@example.invalid",
            "commit",
            "-m",
            commit_message,
            error_cls=self._spec.error_cls,
        )
        commit = gitpkg.head_commit(worktree_path, error_cls=self._spec.error_cls)
        self.path = path
        self.commit = commit
        self.current_branch = gitpkg.current_branch(
            worktree_path, error_cls=self._spec.error_cls
        )
        gitpkg.pack_package_archive(
            worktree_path, path, package_suffix=self._spec.package_suffix
        )
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
        self.current_branch = gitpkg.current_branch(
            self._bound_worktree_path(), error_cls=self._spec.error_cls
        )
        self._pack_archive()

    def checkout(self, ref: str) -> None:
        self._bound_package().checkout(ref)
        self.current_branch = gitpkg.current_branch(
            self._bound_worktree_path(), error_cls=self._spec.error_cls
        )
        self.commit = gitpkg.head_commit(
            self._bound_worktree_path(), error_cls=self._spec.error_cls
        )
        self._pack_archive()

    def switch(self, name: str) -> None:
        self._bound_package().switch(name)
        loaded = self._load_from_worktree()
        self._spec.refresh(self._instance, loaded)
        self._copy_loaded_accessor_state(loaded)
        self.current_branch = gitpkg.current_branch(
            self._bound_worktree_path(), error_cls=self._spec.error_cls
        )
        self.commit = gitpkg.head_commit(
            self._bound_worktree_path(), error_cls=self._spec.error_cls
        )
        self._pack_archive()

    def restore(self, ref: str = "HEAD") -> dict:
        loaded = self._load_from_worktree(ref=ref)
        self._spec.refresh(self._instance, loaded)
        self._copy_loaded_accessor_state(loaded)
        self.commit = loaded.git.commit
        self.current_branch = gitpkg.current_branch(
            self._bound_worktree_path(), error_cls=self._spec.error_cls
        )
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
        info = self._bound_package().tag(name, message=message)
        self._pack_archive()
        if self.path is not None:
            info["path"] = str(self.path)
        return info

    def status(self) -> dict:
        return self._bound_package().status()

    def remotes(self) -> dict[str, str]:
        return self._bound_package().remotes()

    def remote_add(self, name: str, url: str) -> dict:
        info = self._bound_package().remote_add(name, url)
        self._pack_archive()
        return info

    def remote_remove(self, name: str) -> dict:
        info = self._bound_package().remote_remove(name)
        self._pack_archive()
        return info

    def remote_set_url(self, name: str, url: str) -> dict:
        info = self._bound_package().remote_set_url(name, url)
        self._pack_archive()
        return info

    def fetch(
        self,
        remote: Optional[str] = None,
        branch: Optional[str] = None,
        token: Optional[str] = None,
    ) -> dict:
        info = self._bound_package().fetch(remote=remote, branch=branch, token=token)
        self._pack_archive()
        if self.path is not None:
            info["path"] = str(self.path)
        return info

    def validate(self) -> dict:
        return self._bound_package().validate()

    def ignore_in_parent(self) -> dict:
        if self.path is None:
            raise ValueError(
                f"This {self._spec.object_type} is not bound to a git package path."
            )
        outer_repo = gitpkg.outer_git_repo(self.path)
        if outer_repo is None:
            raise ValueError("This EDSL package is not inside another Git repo.")

        pattern = self.path.resolve().relative_to(outer_repo).as_posix()
        gitignore = outer_repo / ".gitignore"
        existing = gitignore.read_text().splitlines() if gitignore.exists() else []
        if pattern in existing:
            return {
                "status": "unchanged",
                "gitignore": str(gitignore),
                "pattern": pattern,
            }

        with gitignore.open("a") as f:
            if existing and existing[-1] != "":
                f.write("\n")
            f.write(pattern + "\n")
        return {"status": "ok", "gitignore": str(gitignore), "pattern": pattern}

    def push(
        self,
        remote: Optional[str] = None,
        branch: Optional[str] = None,
        token: Optional[str] = None,
        path=None,
    ) -> dict:
        if self.path is None:
            self.save(path or self._spec.default_path())
        info = self._bound_package().push(remote=remote, branch=branch, token=token)
        self.commit = info["commit"]
        self.current_branch = info["branch"]
        self._pack_archive()
        if self.path is not None:
            info["path"] = str(self.path)
        return info

    def coop_push(
        self,
        *,
        description: Optional[str] = None,
        alias: Optional[str] = None,
        visibility: Optional[str] = None,
        expected_parrot_url: Optional[str] = None,
        force: bool = False,
        path=None,
        message: str = "",
    ) -> dict:
        if self.path is None:
            self.save(path or self._spec.default_path())
        else:
            self.save(message=message or self._spec.default_commit_message)

        coop_info = self._read_coop_info()
        if coop_info is None:
            info = self._instance.push(
                description=description,
                alias=alias,
                visibility="private" if visibility is None else visibility,
                expected_parrot_url=expected_parrot_url,
                force=force,
            )
            coop_info = _plain_dict(info)
            coop_info.update(
                self._remote_coop_info(expected_parrot_url, coop_info=coop_info)
            )
        else:
            from edsl.coop import Coop

            identifier = self._coop_identifier(coop_info)
            patch_info = Coop(url=expected_parrot_url).patch(
                url_or_uuid=identifier,
                description=description,
                alias=alias,
                value=self._instance,
                visibility=visibility,
            )
            coop_info.update(_plain_dict(patch_info))
            coop_info.update(
                self._remote_coop_info(expected_parrot_url, coop_info=coop_info)
            )

        commit_info = self._write_coop_info_and_commit(
            coop_info,
            message=message or f"Update Coop info for {self._spec.object_type}",
        )
        return {"status": "ok", "coop_info": coop_info, **commit_info}

    def coop_pull(
        self,
        *,
        expected_parrot_url: Optional[str] = None,
        message: str = "",
    ) -> dict:
        coop_info = self._read_coop_info()
        if coop_info is None:
            raise ValueError(
                f"No coop_info.json found for this {self._spec.object_type} package."
            )
        identifier = self._coop_identifier(coop_info)
        coop_info.update(
            self._remote_coop_info(expected_parrot_url, coop_info=coop_info)
        )
        loaded = type(self._instance).pull(
            identifier, expected_parrot_url=expected_parrot_url
        )
        self._spec.refresh(self._instance, loaded)
        return self._save_overwriting_package(
            self.path,
            message=message or f"Coop pull {self._spec.object_type}",
            coop_info=coop_info,
        )

    def pull(
        self,
        remote: Optional[str] = None,
        branch: Optional[str] = None,
        token: Optional[str] = None,
    ) -> dict:
        info = self._bound_package().pull(remote=remote, branch=branch, token=token)
        loaded = self._load_from_worktree()
        self._spec.refresh(self._instance, loaded)
        self._copy_loaded_accessor_state(loaded)
        self.commit = info["commit"]
        self.current_branch = info["branch"]
        self._pack_archive()
        if self.path is not None:
            info["path"] = str(self.path)
        return info

    def _bound_package(self):
        package = self._spec.package_cls(self._bound_worktree_path())
        if self.path is not None:
            package.display_name = self._spec.display_name(self.path)
        return package

    def _load_from_worktree(self, ref: str = "HEAD"):
        worktree_path = self._bound_worktree_path()
        loaded = self._spec.read(worktree_path, ref)
        loaded.git.path = self.path
        loaded.git.worktree_path = worktree_path
        loaded.git.commit = gitpkg.resolve_commit(
            worktree_path, ref, error_cls=self._spec.error_cls
        )
        loaded.git.current_branch = gitpkg.current_branch(
            worktree_path, error_cls=self._spec.error_cls
        )
        return loaded

    def _bound_worktree_path(self) -> Path:
        if self.worktree_path is None:
            raise ValueError(
                f"This {self._spec.object_type} is not bound to a git package path."
            )
        return self.worktree_path

    def _pack_archive(self) -> None:
        if self.path is None:
            raise ValueError(
                f"This {self._spec.object_type} is not bound to a git package path."
            )
        gitpkg.pack_package_archive(
            self._bound_worktree_path(),
            self.path,
            package_suffix=self._spec.package_suffix,
        )

    def _coop_info_path(self) -> Path:
        if self.path is None:
            raise ValueError(
                f"This {self._spec.object_type} is not bound to a git package path."
            )
        return self._bound_worktree_path() / "coop_info.json"

    def _read_coop_info(self) -> dict | None:
        info_path = self._coop_info_path()
        if not info_path.exists():
            return None
        return json.loads(info_path.read_text(encoding="utf-8"))

    def _write_coop_info(self, coop_info: Mapping[str, Any]) -> None:
        self._coop_info_path().write_text(
            json.dumps(dict(coop_info), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _coop_identifier(self, coop_info: Mapping[str, Any]) -> str:
        identifier = (
            coop_info.get("uuid") or coop_info.get("url") or coop_info.get("alias_url")
        )
        if not identifier:
            raise ValueError("coop_info.json must contain a uuid, url, or alias_url.")
        return str(identifier)

    def _remote_coop_info(
        self,
        expected_parrot_url: Optional[str] = None,
        *,
        coop_info: Optional[Mapping[str, Any]] = None,
    ) -> dict:
        from edsl.coop import Coop

        coop_info = coop_info or self._read_coop_info()
        if coop_info is None:
            return {}
        return _plain_dict(
            Coop(url=expected_parrot_url).get_metadata(self._coop_identifier(coop_info))
        )

    def _coop_remote_is_newer(
        self, remote_info: Mapping[str, Any], local_info: Mapping[str, Any]
    ) -> bool:
        remote_updated = remote_info.get("last_updated_ts")
        if remote_updated is None:
            return False
        return remote_updated != local_info.get("last_updated_ts")

    def _coop_pull_if_remote_updated(
        self,
        *,
        expected_parrot_url: Optional[str] = None,
        message: str = "",
    ) -> dict | None:
        coop_info = self._read_coop_info()
        if coop_info is None:
            return None
        remote_info = self._remote_coop_info(
            expected_parrot_url=expected_parrot_url,
            coop_info=coop_info,
        )
        if not self._coop_remote_is_newer(remote_info, coop_info):
            return None
        coop_info.update(remote_info)
        identifier = self._coop_identifier(coop_info)
        loaded = type(self._instance).pull(
            identifier, expected_parrot_url=expected_parrot_url
        )
        self._spec.refresh(self._instance, loaded)
        return self._save_overwriting_package(
            self.path,
            message=message or f"Coop sync {self._spec.object_type}",
            coop_info=coop_info,
        )

    def _write_coop_info_and_commit(
        self, coop_info: Mapping[str, Any], *, message: str
    ) -> dict:
        self._write_coop_info(coop_info)
        return self._commit_package_changes(message)

    def _save_overwriting_package(
        self,
        path,
        *,
        message: str,
        coop_info: Optional[Mapping[str, Any]] = None,
    ) -> dict:
        path = self._spec.normalize_path(path)
        gitpkg.ensure_git_available()
        if self.worktree_path is None or self.path != path:
            self.worktree_path = (
                gitpkg.unpack_package_archive(
                    path,
                    package_suffix=self._spec.package_suffix,
                    error_cls=self._spec.error_cls,
                )
                if path.exists()
                else gitpkg.new_package_worktree(path)
            )
        worktree_path = self._bound_worktree_path()
        gitpkg.init_package(worktree_path, error_cls=self._spec.error_cls)
        extra_info = self._spec.write(worktree_path, self._instance)
        self.path = path
        for key, value in extra_info.items():
            if key.isidentifier():
                setattr(self, key, value)
        if coop_info is not None:
            self._write_coop_info(coop_info)
        return {**self._commit_package_changes(message), **extra_info}

    def _commit_package_changes(self, message: str) -> dict:
        if self.path is None:
            raise ValueError(
                f"This {self._spec.object_type} is not bound to a git package path."
            )
        worktree_path = self._bound_worktree_path()
        gitpkg.git(
            worktree_path, "add", "-A", "--", ".", error_cls=self._spec.error_cls
        )
        if not gitpkg.has_staged_changes(worktree_path):
            commit = gitpkg.head_commit(worktree_path, error_cls=self._spec.error_cls)
            self.commit = commit
            self.current_branch = gitpkg.current_branch(
                worktree_path, error_cls=self._spec.error_cls
            )
            self._pack_archive()
            return {
                "status": "unchanged",
                "path": str(self.path),
                "commit": commit,
                "branch": self.current_branch,
                "message": "no changes",
            }

        gitpkg.git(
            worktree_path,
            "-c",
            "user.name=EDSL",
            "-c",
            "user.email=edsl@example.invalid",
            "commit",
            "-m",
            message,
            error_cls=self._spec.error_cls,
        )
        commit = gitpkg.head_commit(worktree_path, error_cls=self._spec.error_cls)
        self.commit = commit
        self.current_branch = gitpkg.current_branch(
            worktree_path, error_cls=self._spec.error_cls
        )
        self._pack_archive()
        return {
            "status": "ok",
            "path": str(self.path),
            "commit": commit,
            "branch": self.current_branch,
            "message": message,
        }

    def _copy_loaded_accessor_state(self, loaded) -> None:
        loaded_accessor = loaded.git
        for key, value in vars(loaded_accessor).items():
            if key.startswith("_") or key in {
                "path",
                "worktree_path",
                "commit",
                "current_branch",
            }:
                continue
            setattr(self, key, value)


def _plain_dict(value: Any) -> dict:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "data") and isinstance(value.data, Mapping):
        return dict(value.data)
    if hasattr(value, "to_dict"):
        return dict(value.to_dict())
    return dict(value)
