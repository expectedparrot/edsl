import os
import platform
import socket
import time
import json
from typing import Optional
from datetime import datetime
import inspect
#from edsl.Base import Base

class Study:
    """A class for logging and tracking EDSL studies.
    It lets you group a series of events and objects together. 
    
    """
    def __init__(self, 
                 name: Optional[str] = None,
                 description: Optional[str] = None, 
                 coop: bool = False, 
                 local: bool = True, 
                 log_dir="study_logs"):
        self.log_dir = log_dir
        self.name = name
        self.coop = coop
        self.local = local
        self.description = description
        
        self.entries = []
        self.objects = {}
        self.hash_to_entries = {}
        self.hash_to_name = {}
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

    def _get_edsl_classes(self):
        from edsl.Base import RegisterSubclassesMeta
        from edsl import QuestionBase
        for name, value in globals().items():
            if inspect.isclass(value) and name in RegisterSubclassesMeta.get_registry() and value != RegisterSubclassesMeta:
                yield name, value
            if inspect.isclass(value) and issubclass(value, QuestionBase):
                yield name, value

    @property
    def edsl_classes(self):
        return dict(self._get_edsl_classes())
            
    def _get_edsl_objects(self):
        from edsl.Base import Base
        for name, value in globals().items():
            if hasattr(value, "to_dict") and not inspect.isclass(value) and not isinstance(value, Study):
                yield name, value

    @property
    def edsl_objects(self):
        return dict(self._get_edsl_objects())

    def __enter__(self):
        self.start_time = time.time()
        if self.edsl_objects:
            raise ValueError("You have EDSL objects in the global namespace. Please remove them before starting a study or put under the 'Study' context manager.")
        self.entries.append({
            "timestamp": self.start_time,
            "event": "study_started",
            "system_info": self._get_system_info(),
            "description": self.description
        })
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        self.entries.append({
            "timestamp": self.end_time,
            "event": "study_ended"
        })
        for variable_name, object in self.edsl_objects.items():
            self.add_edsl_objects(object = object, variable_name = variable_name)

        self._write_log_file()
        if self.coop:
            self.push()
        if self.local:
            self._write_local()

    def to_dict(self):
        return {'entries': self.entries, 
                'objects': {hash: obj.to_dict() for hash, obj in self.objects.items()}
                }
    
    @classmethod
    def _get_class(self, obj_dict):
        class_name = obj_dict['edsl_class_name']
        if class_name == "QuestionBase":
            from edsl import QuestionBase
            return QuestionBase
        else:
            from edsl.Base import RegisterSubclassesMeta
            return RegisterSubclassesMeta._registry[class_name]

    @classmethod
    def from_dict(cls, d):
        entries = d['entries']
        objects = {object_hash: cls._get_class(obj_str).from_dict(obj_str) for object_hash, obj_str in d['objects'].items()}
        return {'objects': objects, 'entries': entries}

    def _get_system_info(self):
        return {
            "platform": platform.platform(),
            "system": platform.system(),
            "processor": platform.processor(),
            "hostname": socket.gethostname(),
        }
    
    def add_edsl_objects(self, object, variable_name, description=None):
        object_hash = hash(object)
        self.objects[object_hash] = object
        entry_class = object.__class__.__name__
        entry = {
            "timestamp": time.time(),
            "event": "object_added",
            "hash": object_hash,
            "description": description, 
            "class": entry_class,
            "variable_name": variable_name,
            "coop_info": None,
        }
        self.entries.append(entry)
        self.hash_to_entries[object_hash] = entry
        self.hash_to_name[object_hash] = variable_name

    def load_name_space(self):
        for variable_name, object in self.edsl_objects.items():
            globals()[variable_name] = object

    def push(self):
        for hash, obj in self.objects.items():
            print("Now pushing object with hash:", hash)
            coop_info = obj.push(description = f"Study name: {self.name}, Study description: {self.description}")
            print(coop_info)
            self.hash_to_entries[hash]["coop_info"] = coop_info

    def add_entry(self, info):
        entry = {
            "timestamp": time.time(),
            "event": "info_added",
            "info": info
        }
        self.entries.append(entry)

    def _write_log_file(self):
        timestamp = datetime.fromtimestamp(self.start_time).strftime('%Y%m%d_%H%M%S')
        if self.name:
            log_filename = os.path.join(self.log_dir, f"{self.name}.json")
        else:
            log_filename = os.path.join(self.log_dir, f"study_log_{timestamp}.json")
        with open(log_filename, 'w') as f:
            json.dump(self.entries, f, indent=4)

    def _write_local(self):
        timestamp = datetime.fromtimestamp(self.start_time).strftime('%Y%m%d_%H%M%S')
        log_folder = os.path.join(self.log_dir, f"study_log_{timestamp}")
        os.makedirs(log_folder)
        for hash, obj in self.objects.items():
            print(f"Now saving object of type {obj.__class__.__name__} with hash:", hash)
            obj.save(os.path.join(log_folder, f"{obj.__class__.__name__}_{hash}"), compress = False)

    def __repr__(self):
        return f"""Study(name = {self.name}, description = {self.description})"""



with Study(name = "kktv2", description = "KKT replication") as study:
    from edsl import Cache, QuestionFreeText, ScenarioList
    s = ScenarioList.example()
    c = Cache()
    q = QuestionFreeText.example()    
    results = q.run(cache = c)

del s
del c
del q
del results

d = study.to_dict()
newd = Study.from_dict(d)