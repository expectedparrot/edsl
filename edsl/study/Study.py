import os
import platform
import socket
import time
import json
from typing import Optional, Generator, List, Dict
from datetime import datetime
import inspect
#from edsl.Base import Base
from edsl import Cache, set_session_cache, unset_session_cache

from dataclasses import dataclass, field
from collections import UserDict

from edsl.study.ObjectEntry import ObjectEntry

class SnapShot:

    def __init__(self):
        self.edsl_objects = dict(self._get_edsl_objects())
        self.edsl_classes = dict(self._get_edsl_classes())

    def _get_edsl_classes(self) -> Generator[tuple[str, type], None, None]:
        "Get all EDSL classes in the global namespace."
        from edsl.Base import RegisterSubclassesMeta
        from edsl import QuestionBase
        for name, value in globals().items():
            if inspect.isclass(value) and name in RegisterSubclassesMeta.get_registry() and value != RegisterSubclassesMeta:
                yield name, value
            if inspect.isclass(value) and issubclass(value, QuestionBase):
                yield name, value
               
    def _get_edsl_objects(self) -> Generator[tuple[str, type], None, None]:
        from edsl.Base import Base
        for name, value in globals().items():
            if hasattr(value, "to_dict") and not inspect.isclass(value) and not isinstance(value, Study):
                yield name, value


class Study:
    """A class for logging and tracking EDSL studies.
    It lets you group a series of events and objects together. 

    It records all the edsl objects that are created during the study. 
    On exit, is saves them to a study file. 

    How it works:
    - if there is a filename and that file exists, it will load the study from that file. 
    - if there is no filename, it will create a new study, and then save it to the filename.
    - if there is a descrepancy between the passed parameters and the savved parameters, an error will be raised. 
    """
    def __init__(self,
                 name: Optional[str] = None,
                 description: Optional[str] = None, 
                 objects: Optional[Dict[str, ObjectEntry]] = None,
                 cache: Optional[Cache] = None, 
                 file_path: Optional[str] = None,
                 coop: bool = False,
                 use_study_cache = True,
                 overwrite_on_change = True
                ):

        if file_path and os.path.exists(file_path + ".json") and os.path.getsize(file_path + ".json") > 0:
            print("Using existing study file")
            #import gzip
            with open(file_path + ".json", 'r') as f:
                d = json.load(f)
            old_study = Study.from_dict(d)
            self.__dict__.update(old_study.__dict__)
        else:                
            self.name = name
            self.description = description
            self.objects = objects or {}
            self.file_path = file_path
            self.cache = cache or Cache()

        # These always overwrite the saved study    
        self.coop = coop
        self.use_study_cache = use_study_cache
        self.overwrite_on_change = overwrite_on_change

        self.starting_hashes = list(self.objects.keys())
     
    def __enter__(self):
        snapshot = SnapShot()
        if self.use_study_cache:
            set_session_cache(self.cache)
        
        if snapshot.edsl_objects:
            raise ValueError("You have EDSL objects in the global namespace. Please remove them before starting a study or put under the 'Study' context manager.")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        snapshot = SnapShot()
        if self.use_study_cache:
            unset_session_cache()
            
        for variable_name, object in snapshot.edsl_objects.items():
            #print(f"Adding object of type {object.__class__.__name__} with variable name {variable_name}")
            self.add_edsl_object(object = object, variable_name = variable_name)      

        if not self.starting_hashes:
            print("New study saved.")
            self.save()

        if self.starting_hashes and self.starting_hashes == list(self.objects.keys()):
            print("Study perfectly replicated.")
        else:
            print("Study not perfectly replicated.")
            print("Starting hashes", self.starting_hashes)
            print("Ending hashes", list(self.objects.keys()))  
            if self.overwrite_on_change:
                print("Overwriting study file.")
                self.save()
            else:
                print("Please save the study file with a new name or call study iwth 'overwrite_on_change=True' to overwrite the existing study file.")

        if self.coop:
            self.push()
            if self.overwrite_on_change:
                self.save()
            else:
                raise ValueError("If you want to push to coop, you must save the study file with a new name or call study iwth 'overwrite_on_change=True' to overwrite the existing study file.")

    def to_dict(self):
        return {
            'name': self.name,
            'description': self.description,
            'objects': {hash: obj.to_dict() for hash, obj in self.objects.items()},
            'cache': self.cache.to_dict(), 
            'use_study_cache': self.use_study_cache, 
            'overwrite_on_change': self.overwrite_on_change
            }

    def versions(self):
        d = {}
        for hash, obj_entry in self.objects.items():
            if obj_entry.variable_name not in d:
                d[obj_entry.variable_name] = [obj_entry]
            else:
                d[obj_entry.variable_name].append(obj_entry)

        return d

    
    @classmethod
    def from_dict(cls, d):
        name = d['name']
        description = d['description']
        cache = Cache.from_dict(d['cache'])
        use_study_cache = d['use_study_cache']
        overwrite_on_change = d['overwrite_on_change']
        objects = {str(object_hash): ObjectEntry.from_dict(obj_dict) for object_hash, obj_dict in d['objects'].items()}
        return cls(**{'objects': objects, 'name': name, 'description': description, 'cache': cache, 'use_study_cache': use_study_cache, 'overwrite_on_change': overwrite_on_change})
    
    def save(self, file_path: Optional[str] = None):
        print("Saving study")
        #import gzip
        if file_path is None:
            file_path = f"{self.file_path}"
        # if compress:
        #     with gzip.open(file_path + ".json.gz", "wb") as f:
        #         f.write(json.dumps(self.to_dict()).encode("utf-8"))
        # else:
        with open(file_path + ".json", 'w') as f:
            json.dump(self.to_dict(), f, indent=4)

    def _get_system_info(self):
        return {
            "platform": platform.platform(),
            "system": platform.system(),
            "processor": platform.processor(),
            "hostname": socket.gethostname(),
        }
    
    def add_edsl_object(self, object, variable_name, description=None) -> None:
        oe = ObjectEntry(variable_name = variable_name, object = object, description = description)
        #print("The object entry hash is ", oe.hash)
        if oe.hash in self.objects:
            #print(f"Object with hash {oe.hash} already exists.")
            return
        else:
            #print("Hash not found in objects")
            self.objects[oe.hash] = oe

    def load_name_space(self):
        for variable_name, object in self.edsl_objects.items():
            globals()[variable_name] = object

    def push(self, refresh = False):
        """Push the objects to coop."""
        for obj_entry in self.objects.values():
            obj_entry.push(refresh = refresh)

    def _write_local(self):
        timestamp = datetime.fromtimestamp(self.start_time).strftime('%Y%m%d_%H%M%S')
        log_folder = os.path.join(self.log_dir, f"study_log_{timestamp}")
        os.makedirs(log_folder)
        for hash, obj in self.objects.items():
            #print(f"Now saving object of type {obj.__class__.__name__} with hash:", hash)
            obj.save(os.path.join(log_folder, f"{obj.__class__.__name__}_{hash}"), compress = False)

    def __repr__(self):
        return f"""Study(name = {self.name}, description = {self.description})"""


from edsl import Cache, QuestionFreeText, ScenarioList



with Study(name = "kktv2", description = "KKT replication", file_path="fhm_replication2", coop = True) as study:
    q = QuestionFreeText.example()
    q2 = QuestionFreeText.example()    
    results = q.run()
    

#r0 = study.versions()['results'][0].object; r1 = study.versions()['results'][1].object; diff = r1 - r0; print(diff)

#c0 = study.versions()['c'][0].object
#c1 = study.versions()['c'][1].object
#diff = c1 - c0
#print(diff)

#d = study.to_dict()
#newd = Study.from_dict(d)