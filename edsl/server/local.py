"""
Local EDSL Server - Seamless local storage and execution.

This module provides a seamless experience for using EDSL with a local server.
Users just call normal EDSL methods and everything works.

Usage:
    from edsl import ScenarioList
    
    # Just works - auto-starts local server if needed
    sl = ScenarioList.example()
    info = sl.push()  # Pushes to local server
    
    # Later, pull it back
    sl2 = ScenarioList.pull(info["uuid"])
"""

import os
import sys
import uuid
from typing import Optional, Dict, Any, TypeVar, Type
from datetime import datetime

from edsl import servers


T = TypeVar("T")


class LocalStorage:
    """
    Simple interface for storing and retrieving EDSL objects locally.
    
    This class provides push/pull operations that automatically manage
    the local server - starting it if needed, creating keys, etc.
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        self._client = None
        self._username = None
    
    @property
    def client(self):
        """Get HTTP client, ensuring server is available."""
        if self._client is None:
            self._client = servers.require_client(purpose="local storage")
            self._username = self._client.username
        return self._client
    
    @property
    def username(self) -> str:
        """Get the current username."""
        if self._username is None:
            self._username = self.client.username
        return self._username
    
    def push(
        self,
        obj: Any,
        description: Optional[str] = None,
        alias: Optional[str] = None,
        visibility: str = "private",
    ) -> Dict[str, Any]:
        """
        Push an EDSL object to local storage.
        
        Args:
            obj: The EDSL object to push (ScenarioList, Survey, Results, etc.)
            description: Optional description
            alias: Optional human-readable alias
            visibility: "private", "unlisted", or "public"
            
        Returns:
            Dict with uuid, alias, url, and other info
        """
        # Generate UUID
        object_uuid = str(uuid.uuid4())
        
        # Get object type
        object_type = type(obj).__name__
        
        # Serialize object
        try:
            data = obj.to_dict()
        except Exception as e:
            raise ValueError(f"Cannot serialize {object_type}: {e}")
        
        # Build snapshot
        snapshot = {
            "uuid": object_uuid,
            "object_type": object_type,
            "data": data,
            "owner": self.username,
            "visibility": visibility,
            "description": description,
            "alias": alias,
            "created_at": datetime.utcnow().isoformat(),
            "edsl_version": self._get_edsl_version(),
        }
        
        # Push to server
        self.client.push_snapshot(object_uuid, snapshot)
        
        # Set alias if provided
        if alias:
            try:
                self.client.set_alias(f"{self.username}/{alias}", object_uuid)
            except Exception:
                pass  # Alias conflicts are not fatal
        
        # Print confirmation
        print(f"✓ Pushed {object_type} to local server")
        print(f"  UUID: {object_uuid}")
        if alias:
            print(f"  Alias: {alias}")
        
        return {
            "uuid": object_uuid,
            "object_type": object_type,
            "alias": alias,
            "visibility": visibility,
            "url": f"{self.client.base_url}/stores/{object_uuid}",
            "description": description,
        }
    
    def pull(
        self,
        uuid_or_alias: str,
        expected_type: Optional[Type[T]] = None,
    ) -> T:
        """
        Pull an EDSL object from local storage.
        
        Args:
            uuid_or_alias: UUID or alias of the object
            expected_type: Expected class type (for type checking)
            
        Returns:
            The deserialized EDSL object
        """
        # Try to resolve alias
        store_id = uuid_or_alias
        if "/" not in uuid_or_alias and not self._is_uuid(uuid_or_alias):
            # Might be an alias - try with username prefix
            store_id = f"{self.username}/{uuid_or_alias}"
        
        # Pull snapshot
        snapshot = self.client.pull_snapshot(store_id)
        if snapshot is None:
            # Try without prefix
            snapshot = self.client.pull_snapshot(uuid_or_alias)
        
        if snapshot is None:
            raise ValueError(f"Object not found: {uuid_or_alias}")
        
        # Deserialize
        object_type = snapshot.get("object_type")
        data = snapshot.get("data")
        
        if not object_type or not data:
            raise ValueError(f"Invalid snapshot format for {uuid_or_alias}")
        
        # Get the class
        cls = self._get_class(object_type)
        
        if expected_type and cls != expected_type:
            raise TypeError(
                f"Expected {expected_type.__name__}, got {object_type}"
            )
        
        # Deserialize
        obj = cls.from_dict(data)
        
        print(f"✓ Pulled {object_type} from local server")
        
        return obj
    
    def list(
        self,
        object_type: Optional[str] = None,
        visibility: Optional[str] = None,
    ) -> list:
        """List objects in local storage."""
        stores = self.client.search_stores(
            owner=self.username,
            object_type=object_type,
            visibility=visibility,
        )
        return stores
    
    def delete(self, uuid_or_alias: str) -> bool:
        """Delete an object from local storage."""
        return self.client.delete_store(uuid_or_alias, force=True)
    
    def _is_uuid(self, s: str) -> bool:
        """Check if string looks like a UUID."""
        try:
            uuid.UUID(s)
            return True
        except ValueError:
            return False
    
    def _get_class(self, object_type: str):
        """Get EDSL class by name."""
        from edsl import (
            Scenario, ScenarioList, Survey, Agent, AgentList,
            Results, QuestionBase, QuestionMultipleChoice,
            QuestionFreeText, QuestionLinearScale, QuestionList,
            Model,
        )
        
        classes = {
            "Scenario": Scenario,
            "ScenarioList": ScenarioList,
            "Survey": Survey,
            "Agent": Agent,
            "AgentList": AgentList,
            "Results": Results,
            "Model": Model,
            # Add more as needed
        }
        
        # Also check QuestionBase subclasses
        if object_type.startswith("Question"):
            for q in [QuestionMultipleChoice, QuestionFreeText, 
                      QuestionLinearScale, QuestionList]:
                if q.__name__ == object_type:
                    return q
            return QuestionBase
        
        cls = classes.get(object_type)
        if cls is None:
            raise ValueError(f"Unknown object type: {object_type}")
        return cls
    
    def _get_edsl_version(self) -> str:
        """Get current EDSL version."""
        try:
            from edsl import __version__
            return __version__
        except:
            return "unknown"


# Global instance
_storage = None


def get_local_storage() -> LocalStorage:
    """Get the global LocalStorage instance."""
    global _storage
    if _storage is None:
        _storage = LocalStorage()
    return _storage


def push(
    obj: Any,
    description: Optional[str] = None,
    alias: Optional[str] = None,
    visibility: str = "private",
) -> Dict[str, Any]:
    """
    Push an EDSL object to local storage.
    
    This is the simplest way to store an object:
    
        from edsl.server.local import push
        from edsl import ScenarioList
        
        sl = ScenarioList.example()
        info = push(sl, alias="my-scenarios")
    """
    return get_local_storage().push(obj, description, alias, visibility)


def pull(uuid_or_alias: str, expected_type: Optional[Type[T]] = None) -> T:
    """
    Pull an EDSL object from local storage.
    
        from edsl.server.local import pull
        from edsl import ScenarioList
        
        sl = pull("my-scenarios", ScenarioList)
    """
    return get_local_storage().pull(uuid_or_alias, expected_type)

