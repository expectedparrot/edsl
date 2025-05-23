"""A list of Humans with specialized operations for managing human participants.

This module provides the HumanList class, which extends AgentList to provide functionality
specific to managing collections of human participants.
"""

from __future__ import annotations
import csv
import copy
from typing import Optional, List, Dict, Any, TYPE_CHECKING, Union

from ..agents.agent_list import AgentList
from .human import Human
from .exceptions import HumanListError

if TYPE_CHECKING:
    from ..scenarios import ScenarioList


class HumanList(AgentList):
    """A list of Human objects with additional functionality for human participants.
    
    The HumanList class extends AgentList to provide a container for Human objects
    with specialized methods for managing collections of human participants in
    research studies, surveys, or interviews.
    
    Examples:
        >>> from edsl.humans import Human, HumanList
        >>> h1 = Human(traits={"age": 30}, email="user1@example.com")
        >>> h2 = Human(traits={"age": 25}, phone="555-1234")
        >>> hl = HumanList([h1, h2])
        >>> len(hl)
        2
        >>> hl[0].email
        'user1@example.com'
        >>> hl[1].phone
        '555-1234'
        
        >>> # Only Human objects allowed
        >>> from edsl.agents import Agent
        >>> agent = Agent(traits={"test": "value"})
        >>> HumanList([agent])  # doctest: +ELLIPSIS
        Traceback (most recent call last):
        ...
        edsl.humans.exceptions.HumanListError: All items in a HumanList must be Human objects...
    """

    __documentation__ = "https://docs.expectedparrot.com/en/latest/humans.html#humanlist-class"

    def __init__(self, data: Optional[list[Human]] = None, codebook: Optional[dict[str, str]] = None):
        """Initialize a new HumanList.
        
        Args:
            data: A list of Human objects. If None, creates an empty HumanList.
            codebook: Optional dictionary mapping trait names to descriptions.
                    If provided, will be applied to all humans in the list.
        """
        super().__init__(data, codebook)
        
        # Validate that all items are Humans
        if data:
            for item in data:
                if not isinstance(item, Human):
                    raise HumanListError(
                        f"All items in a HumanList must be Human objects, got {type(item).__name__}"
                    )

    def duplicate(self) -> HumanList:
        """Create a deep copy of the HumanList.
        
        Returns:
            HumanList: A new HumanList containing copies of all humans.
        """
        return HumanList([human.duplicate() for human in self.data])
    
    def contact_list(self) -> List[Dict[str, str]]:
        """Get a list of contact information for all humans in the list.
        
        Returns:
            List[Dict[str, str]]: A list of dictionaries with contact information
            
        Examples:
            >>> h1 = Human(traits={"age": 30}, email="user1@example.com", name="Alice")
            >>> h2 = Human(traits={"age": 25}, phone="555-1234", name="Bob")
            >>> hl = HumanList([h1, h2])
            >>> contacts = hl.contact_list()
            >>> len(contacts)
            2
            >>> contacts[0]['email']
            'user1@example.com'
            >>> contacts[0]['name']
            'Alice'
            >>> contacts[1]['phone']
            '555-1234'
            >>> contacts[1]['name']
            'Bob'
        """
        contacts = []
        for human in self.data:
            # Filter out None values
            contact_info = {k: v for k, v in human.contact_info.items() if v is not None}
            if contact_info:
                # Add name if available
                if human.name:
                    contact_info["name"] = human.name
                contacts.append(contact_info)
        return contacts
    
    def to_dict(self, sorted=False, add_edsl_version=True) -> dict:
        """Serialize the HumanList to a dictionary.
        
        Args:
            sorted: Whether to sort the humans by hash value
            add_edsl_version: Whether to include EDSL version information
            
        Returns:
            dict: Dictionary representation of the HumanList
        """
        d = super().to_dict(sorted=sorted, add_edsl_version=add_edsl_version)
        
        if add_edsl_version:
            d["edsl_class_name"] = self.__class__.__name__
            
        return d
    
    @classmethod
    def from_dict(cls, data: dict) -> HumanList:
        """Deserialize a dictionary to a HumanList object.
        
        Args:
            data: Dictionary representation of a HumanList
            
        Returns:
            HumanList: A HumanList instance created from the dictionary
        """
        humans = []
        
        for human_dict in data["agent_list"]:
            humans.append(Human.from_dict(human_dict))
            
        human_list = cls(humans)
        
        # Apply codebook if present in the dictionary
        if "codebook" in data and data["codebook"]:
            human_list.set_codebook(data["codebook"])
            
        return human_list
    
    @classmethod
    def from_csv(cls, file_path: str, name_field: Optional[str] = None, 
                 codebook: Optional[dict[str, str]] = None,
                 email_field: str = "email", 
                 phone_field: Optional[str] = "phone",
                 prolific_id_field: Optional[str] = "prolific_id",
                 ep_username_field: Optional[str] = "ep_username") -> HumanList:
        """Load HumanList from a CSV file.
        
        Args:
            file_path: Path to the CSV file
            name_field: Name of the field to use as the human name
            codebook: Optional dictionary mapping trait names to descriptions
            email_field: Name of the column containing email addresses
            phone_field: Name of the column containing phone numbers
            prolific_id_field: Name of the column containing Prolific IDs
            ep_username_field: Name of the column containing EP usernames
            
        Returns:
            HumanList: A new HumanList created from the CSV data
            
        Raises:
            HumanContactInfoError: If no valid contact information is found
        """
        human_list = []
        
        with open(file_path, "r") as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                # Extract contact information
                email = row.pop(email_field, None) if email_field in row else None
                phone = row.pop(phone_field, None) if phone_field in row else None
                prolific_id = row.pop(prolific_id_field, None) if prolific_id_field in row else None
                ep_username = row.pop(ep_username_field, None) if ep_username_field in row else None
                
                # Extract name if specified
                if "name" in row:
                    name_field = "name"
                    
                if name_field is not None:
                    name = row.pop(name_field, None)
                else:
                    name = None
                
                # Create Human object
                h = Human(
                    name=name,
                    email=email,
                    phone=phone,
                    prolific_id=prolific_id,
                    ep_username=ep_username
                )
                h.traits = row  # type: ignore[attr-defined]
                if codebook:
                    h.codebook = codebook  # type: ignore[attr-defined]
                human_list.append(h)
                
        return cls(human_list)
    
    @classmethod
    def example(cls, randomize: bool = False, codebook: Optional[dict[str, str]] = None) -> HumanList:
        """Return an example HumanList instance.
        
        Args:
            randomize: If True, adds randomness to the example data
            codebook: Optional dictionary mapping trait names to descriptions
            
        Returns:
            HumanList: An example HumanList with sample humans
            
        Examples:
            >>> hl = HumanList.example()
            >>> len(hl)
            2
            >>> hl[0].name
            'John Doe'
            >>> hl[0].email
            'example@example.com'
            >>> hl[1].name
            'Jane Smith'
            >>> hl[1].email
            'teacher@example.com'
            >>> hl[1].traits['occupation']
            'teacher'
        """
        h1 = Human.example(randomize)
        h2 = Human(name="Jane Smith", email="teacher@example.com")
        h2.traits = {"age": 42, "occupation": "teacher", "hobby": "gardening"}  # type: ignore[attr-defined]
        human_list = cls([h1, h2])
        
        if codebook:
            human_list.set_codebook(codebook)
            
        return human_list
    
    @classmethod
    def from_scenario_list(cls, scenario_list: ScenarioList) -> HumanList:
        """Create a HumanList from a ScenarioList.
        
        This method extends the AgentList.from_scenario_list method to handle
        contact information contained in the scenarios.
        
        Args:
            scenario_list: A ScenarioList object to convert to a HumanList
            
        Returns:
            HumanList: A HumanList created from the scenarios
            
        Raises:
            HumanContactInfoError: If no valid contact information is found
        """
        humans = []
        
        for scenario in scenario_list:
            # Extract scenario data
            scenario_data = copy.deepcopy(scenario.data)
            
            # Extract contact information (if present)
            contact_info = scenario_data.pop("contact_info", {})
            
            # Check for flat contact fields
            email = scenario_data.pop("email", None) or contact_info.get("email")
            phone = scenario_data.pop("phone", None) or contact_info.get("phone")
            prolific_id = scenario_data.pop("prolific_id", None) or contact_info.get("prolific_id")
            ep_username = scenario_data.pop("ep_username", None) or contact_info.get("ep_username")
            
            # Extract name if present
            name = scenario_data.pop("name", None)
            
            # Create Human object
            h = Human(
                name=name,
                email=email,
                phone=phone,
                prolific_id=prolific_id,
                ep_username=ep_username
            )
            h.traits = scenario_data  # type: ignore[attr-defined]
            humans.append(h)
            
        return cls(humans)
    
    def __repr__(self) -> str:
        """Return a string representation of the HumanList.
        
        Returns:
            str: String representation of the HumanList
        """
        return f"HumanList({self.data})"


def main():
    """Demo usage of the HumanList class."""
    human_list = HumanList.example()
    print(human_list)
    print(human_list.contact_list())


if __name__ == "__main__":
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)