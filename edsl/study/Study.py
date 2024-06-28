import os
import platform
import socket
import copy
import time
import json
from typing import Optional, Generator, List, Dict
from datetime import datetime
import inspect

# from edsl.Base import Base
from edsl import Cache, set_session_cache, unset_session_cache
from edsl.utilities.utilities import dict_hash
from dataclasses import dataclass, field
from collections import UserDict

from edsl.study.ObjectEntry import ObjectEntry
from edsl.study.ProofOfWork import ProofOfWork


class SnapShot:
    def __init__(self):
        self.edsl_objects = dict(self._get_edsl_objects())
        self.edsl_classes = dict(self._get_edsl_classes())

    def _get_edsl_classes(
        self, namespace: Optional[dict] = None
    ) -> Generator[tuple[str, type], None, None]:
        """Get all EDSL classes in the namespace.

        :param namespace: The namespace to search for EDSL classes. The default is the global namespace.

        >>> sn = SnapShot()
        >>> list(sn._get_edsl_classes(namespace = {}))
        []

        >>> sn = SnapShot()
        >>> sn.edsl_classes
        {'Cache': <class 'edsl.data.Cache.Cache'>}
        """
        from edsl.Base import RegisterSubclassesMeta
        from edsl import QuestionBase

        if namespace is None:
            namespace = globals()
        for name, value in namespace.items():
            if (
                inspect.isclass(value)
                and name in RegisterSubclassesMeta.get_registry()
                and value != RegisterSubclassesMeta
            ):
                yield name, value
            if inspect.isclass(value) and issubclass(value, QuestionBase):
                yield name, value

    def _get_edsl_objects(self) -> Generator[tuple[str, type], None, None]:
        """Get all EDSL objects in the global namespace.

        >>> sn = SnapShot()
        >>> sn.edsl_objects
        {}

        """
        from edsl.Base import Base

        for name, value in globals().items():
            if (
                hasattr(value, "to_dict")
                and not inspect.isclass(value)
                and not isinstance(value, Study)
            ):
                yield name, value


class Study:
    """A study organizes a series of EDSL objects.

    ```python
    with Study(name = "cool_study") as study:
        q = QuestionFreeText.example()
        results = q.run()
    ```

    The `study` object is a context manager.
    It lets you group a series of events and objects together.

    >>> with Study(name = "cool_study") as study:
    ...     from edsl import QuestionFreeText
    ...     q = QuestionFreeText.example()
    >>> len(study.objects)
    1


    It records all the edsl objects that are created during the study.
    On exit, is saves them to a study file.

    """

    def __init__(
        self,
        name: str,
        description: Optional[str] = None,
        objects: Optional[Dict[str, ObjectEntry]] = None,
        cache: Optional[Cache] = None,
        file_path: Optional[str] = None,
        coop: bool = False,
        use_study_cache=True,
        overwrite_on_change=True,
        proof_of_work=None,
        proof_of_work_difficulty: int = None,
    ):
        """
        :param name: The name of the study.
        :param description: A description of the study.
        :param objects: A dictionary of objects to add to the study.
        :param cache: A cache object to (potentially) use for the study.
        :param file_path: The path to the study file.
        :param coop: Whether to push the study to coop.
        :param use_study_cache: Whether to use the study cache.
        :param overwrite_on_change: Whether to overwrite the study file if it has changed.
        """
        self.file_path = file_path or name
        if (
            self.file_path
            and os.path.exists(self.file_path + ".json")
            and os.path.getsize(self.file_path + ".json") > 0
        ):
            print(f"Using existing study file {file_path}.json")
            self._load_from_file()
        else:
            self.name = name
            self.description = description
            self.objects = objects or {}
            self.cache = cache or Cache()
            self.proof_of_work = proof_of_work or ProofOfWork()

        # These always overwrite the saved study
        self.coop = coop
        self.use_study_cache = use_study_cache
        self.overwrite_on_change = overwrite_on_change
        self.proof_of_work_difficulty = proof_of_work_difficulty

        self.starting_objects = copy.deepcopy(self.objects)

    def _load_from_file(self):
        """Load the study from a file.

        >>> import tempfile
        >>> file_path = tempfile.NamedTemporaryFile(delete=False)
        >>> study = Study(name = "poo", file_path = file_path.name)
        >>> study.save()
        Saving study to ...
        >>> study2 = Study(file_path = file_path.name)
        Using existing study file ...
        >>> study2.name
        'poo'
        """
        with open(self.file_path + ".json", "r") as f:
            d = json.load(f)
            d["cache"] = Cache.from_dict(d["cache"])
            d["proof_of_work"] = ProofOfWork.from_dict(d["proof_of_work"])
            d["objects"] = {
                hash: ObjectEntry.from_dict(obj_dict)
                for hash, obj_dict in d["objects"].items()
            }
            self.__dict__.update(d)

    def __enter__(self):
        """
        >>> s = Study(use_study_cache = True)
        >>> _ = s.__enter__()
        >>> from edsl.config import CONFIG
        >>> hasattr(CONFIG, "EDSL_SESSION_CACHE")
        True


        """

        snapshot = SnapShot()
        if self.use_study_cache:
            set_session_cache(self.cache)

        if snapshot.edsl_objects:
            raise ValueError(
                "You have EDSL objects in the global namespace. Please remove them before starting a study or put under the 'Study' context manager."
            )
        return self

    def __hash__(self) -> int:
        return dict_hash(list(self.objects.keys()))

    def study_diff(self):
        ## Need to also report missing.
        from edsl.BaseDiff import BaseDiff

    def print(self):
        from rich.console import Console
        from rich.table import Table

        console = Console()
        table = Table(title="Study")
        table.add_column("Variable Name")
        table.add_column("Class")
        table.add_column("Description")
        table.add_column("Hash")
        table.add_column("Coop info")
        for hash, obj in self.objects.items():
            url = (
                ""
                if not hasattr(obj, "coop_info") or obj.coop_info is None
                else obj.coop_info.get("url", "")
            )
            table.add_row(
                obj.variable_name, obj.edsl_class_name, obj.description, obj.hash, url
            )
        console.print(table)

    def __exit__(self, exc_type, exc_val, exc_tb):
        snapshot = SnapShot()
        if self.use_study_cache:
            unset_session_cache()

        for variable_name, object in snapshot.edsl_objects.items():
            self.add_edsl_object(object=object, variable_name=variable_name)

        if not self.starting_objects:
            print(f"New study saved to {self.file_path}.json")
            self.save()

        if self.starting_objects and list(self.starting_objects.keys()) == list(
            self.objects.keys()
        ):
            print("Study perfectly replicated.")
        else:
            print("Starting hashes:", self.starting_objects.keys())
            print("Current hashes:", self.objects.keys())
            if self.starting_objects:
                missing = set(self.starting_objects.keys()) - set(self.objects.keys())
                added = set(self.objects.keys()) - set(self.starting_objects.keys())
                print("Study did not perfectly replicate.")
                for hash in missing:
                    print(f"Missing object: {self.starting_objects[hash]!r}")
                for hash in added:
                    print(f"Added object: {self.objects[hash]!r}")
                if self.overwrite_on_change:
                    print("Overwriting study file.")
                    self.save()
                else:
                    print(
                        "Please save the study file with a new name or call study iwth 'overwrite_on_change=True' to overwrite the existing study file."
                    )

        if self.coop:
            self.push()
            if self.overwrite_on_change:
                self.save()
            else:
                raise ValueError(
                    "If you want to push to coop, you must save the study file with a new name or call study iwth 'overwrite_on_change=True' to overwrite the existing study file."
                )

        if self.proof_of_work_difficulty:
            print("Adding proof of work to study...")
            from edsl.study.ProofOfWork import ProofOfWork

            # TODO: Need to check if hashes are the same.
            if not self.proof_of_work.input_data:
                self.proof_of_work.add_input_data(str(self.__hash__()))
            self.proof_of_work.add_proof(self.proof_of_work_difficulty)
            print(
                "Proof of work added to study with difficulty ",
                self.proof_of_work_difficulty,
            )
            print(self.proof_of_work)
            self.save()

    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "objects": {hash: obj.to_dict() for hash, obj in self.objects.items()},
            "cache": self.cache.to_dict(),
            "use_study_cache": self.use_study_cache,
            "overwrite_on_change": self.overwrite_on_change,
            "proof_of_work": self.proof_of_work.to_dict(),
        }

    def versions(self):
        """Return a dictionary of objects grouped by variable name."""
        d = {}
        for hash, obj_entry in self.objects.items():
            if obj_entry.variable_name not in d:
                d[obj_entry.variable_name] = [obj_entry]
            else:
                d[obj_entry.variable_name].append(obj_entry)

        return d

    def diff(self, variable_name: str, index1: int, index2: int):
        """Return the difference between the versions of an object."""
        versions = self.versions()[variable_name]
        diff = versions[index2].object - versions[index1].object
        return diff

    @classmethod
    def example(cls):
        with cls(name="cool_study") as study:
            from edsl import QuestionFreeText

            q = QuestionFreeText.example()
        return study

    @classmethod
    def from_dict(cls, d):
        d["cache"] = Cache.from_dict(d["cache"])
        d["objects"] = {
            str(object_hash): ObjectEntry.from_dict(obj_dict)
            for object_hash, obj_dict in d["objects"].items()
        }
        d["proof_of_work"] = ProofOfWork.from_dict(d["proof_of_work"])
        return cls(**d)

    def save(self):
        print(f"Saving study to {self.file_path}.json")
        with open(self.file_path + ".json", "w") as f:
            json.dump(self.to_dict(), f, indent=4)

    def _get_system_info(self):
        return {
            "platform": platform.platform(),
            "system": platform.system(),
            "processor": platform.processor(),
            "hostname": socket.gethostname(),
        }

    def add_edsl_object(self, object, variable_name, description=None) -> None:
        oe = ObjectEntry(
            variable_name=variable_name, object=object, description=description
        )
        if oe.hash in self.objects:
            return
        else:
            self.objects[oe.hash] = oe

    def load_name_space(self):
        for variable_name, object in self.edsl_objects.items():
            globals()[variable_name] = object

    def push(self, refresh=False) -> None:
        """Push the objects to coop."""
        for obj_entry in self.objects.values():
            obj_entry.push(refresh=refresh)

    def _write_local(self):
        timestamp = datetime.fromtimestamp(self.start_time).strftime("%Y%m%d_%H%M%S")
        log_folder = os.path.join(self.log_dir, f"study_log_{timestamp}")
        os.makedirs(log_folder)
        for hash, obj in self.objects.items():
            # print(f"Now saving object of type {obj.__class__.__name__} with hash:", hash)
            obj.save(
                os.path.join(log_folder, f"{obj.__class__.__name__}_{hash}"),
                compress=False,
            )

    def __repr__(self):
        return f"""Study(name = {self.name}, description = {self.description}, objects = {self.objects}, cache = {self.cache}, file_path = {self.file_path}, coop = {self.coop}, use_study_cache = {self.use_study_cache}, overwrite_on_change = {self.overwrite_on_change})"""


# if __name__ == "__main__":
#     with Study(name = "cool_study") as study:
#         from edsl import QuestionFreeText
#         q = QuestionFreeText.example()

# len(study.objects)
# import doctest
# doctest.testmod(optionflags=doctest.ELLIPSIS)

if __name__ == "__main__":
    from edsl import Cache, QuestionFreeText, ScenarioList

    study = Study(
        name="kktv2",
        description="KKT replication",
        file_path="fhm_replication2",
        coop=False,
        proof_of_work_difficulty=4,
    )

    with study:
        q = QuestionFreeText.example()
        results = q.run()


# r0 = study.versions()['results'][0].object; r1 = study.versions()['results'][1].object; diff = r1 - r0; print(diff)

# c0 = study.versions()['c'][0].object
# c1 = study.versions()['c'][1].object
# diff = c1 - c0
# print(diff)

# d = study.to_dict()
# newd = Study.from_dict(d)
