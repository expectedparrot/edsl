"""Human module for representing human participants with contact information.

This module provides the Human class, which represents a human participant with
contact information, customizable traits, and other attributes inherited from Agent.
"""

from __future__ import annotations
import copy
import re
from typing import Optional, Union, Any, Dict, Type

from ..agents.agent import Agent
from .exceptions import HumanErrors, HumanContactInfoError
from .human_interaction_manager import HumanInteractionManager
from .contact_info import ContactInfo


class Human(Agent):
    """A class representing a human participant with contact information.
    
    The Human class extends Agent to represent real human participants with
    required contact information. This allows tracking and contacting participants
    for studies, surveys, or interviews.
    
    Attributes:
        email (Optional[str]): Email address of the human
        phone (Optional[str]): Phone number of the human
        prolific_id (Optional[str]): Prolific platform identifier
        ep_username (Optional[str]): Expected Parrot platform username
    
    Examples:
        >>> h = Human(traits={"age": 30}, email="test@example.com")
        >>> h.email
        'test@example.com'
        >>> h.traits
        {'age': 30}
        
        >>> h2 = Human(traits={"location": "NYC"}, phone="555-1234")
        >>> h2.phone
        '555-1234'
        
        >>> # Multiple contact methods
        >>> h3 = Human(traits={"role": "participant"}, email="user@test.com", prolific_id="ABC123")
        >>> sorted(h3.contact_info.keys())
        ['email', 'ep_username', 'phone', 'prolific_id']
        >>> h3.contact_info['email']
        'user@test.com'
        >>> h3.contact_info['prolific_id']
        'ABC123'
        
        >>> # Must have at least one contact method
        >>> Human(traits={"age": 25})  # doctest: +ELLIPSIS
        Traceback (most recent call last):
        ...
        edsl.humans.exceptions.HumanContactInfoError: At least one contact method...
    """

    __documentation__ = "https://docs.expectedparrot.com/en/latest/humans.html"

    default_instruction = """You are answering questions as a real human participant."""

    def __init__(
        self,
        name: Optional[str] = None,
        **kwargs,
    ):
        """Initialize a new Human instance with contact information and traits.

        Args:
            name: Optional name identifier for the human
            **kwargs: Expected to contain contact-info keywords (email, phone, prolific_id, ep_username)
            
        Raises:
            HumanContactInfoError: If no contact information is provided or if invalid
                                   contact information is provided
                                   
        At least one of email, phone, prolific_id, or ep_username must be provided.
        """
        # ------------------------------------------------------------------
        # Peel contact-related kwargs before delegating to Agent.__init__
        # ------------------------------------------------------------------
        contact_info = ContactInfo.from_kwargs(kwargs)

        # Fail fast on unexpected kwargs (anything not recognised as contact info)
        if kwargs:
            unexpected = ", ".join(kwargs.keys())
            raise TypeError(f"Unexpected keyword argument(s) for Human: {unexpected}")

        # Call Agent with *minimal* information as requested – everything but name is None.
        super().__init__(
            traits=None,
            name=name,
            codebook=None,
            instruction=None,
            traits_presentation_template=None,
        )

        # Persist contact details in helper object only (no flat attributes).
        self._contact_info: ContactInfo = contact_info
        
        # Validate contact information
        self._validate_contact_info()
        
        # Create an interaction-manager helper for this participant.
        self._interaction_manager = HumanInteractionManager(self)
        
    def _validate_contact_info(self) -> None:
        """Validate that at least one contact method is provided and properly formatted.
        
        Raises:
            HumanContactInfoError: If no contact information is provided or if the
                                   provided contact information is invalid
        """
        # Check if at least one contact method is provided
        if not any(self._contact_info.as_dict().values()):
            raise HumanContactInfoError(
                "At least one contact method (email, phone, prolific_id, or ep_username) "
                "must be provided for a Human."
            )
            
        # Validate email format if provided
        if self._contact_info.email and not ContactInfo.is_valid_email(self._contact_info.email):
            raise HumanContactInfoError(
                f"Invalid email format: {self._contact_info.email}"
            )
        
    def list_past_studies(self) -> list[str]:
        """Get a list of past studies the human has participated in.
        
        This requires the user have an Expected Parrot account.
        
        It will list:
        - The study name
        - The study owner (ep_username)
        - The study ID
        - The study status (e.g. "completed", "in progress", "not started")
        - The study start date
        - The study end date
        - Survey URL
        - The Result object for that response        
        
        Returns:
            list[str]: List of past studies
        """
        return self._interaction_manager.list_past_studies()
    
    def _get_ep_user_name(self) -> str:
        """Get the human's Expected Parrot username.
        
        Returns:
            str: The human's Expected Parrot username
        """
        if self._contact_info.ep_username is None:
            raise HumanContactInfoError("Expected Parrot username is not set")
        return self._contact_info.ep_username
    
    def make_payment(self, ep_credits: float) -> None:
        """High-level convenience wrapper that forwards to the internal
        `HumanInteractionManager`. Users can simply call `human.make_payment(...)`.
        """
        self._interaction_manager.make_payment(ep_credits)
    
    def send_message(self, message: str) -> None:
        """High-level convenience wrapper that forwards to the internal
        `HumanInteractionManager`. Users can simply call `human.send_message(...)`.
        """
        self._interaction_manager.send_message(message)
    
    # New study APIs
    def send_study(self, study_id: str) -> None:
        self._interaction_manager.send_study(study_id)

    def list_pending_studies(self):
        return self._interaction_manager.list_pending_studies()
    
    def get_messages(self, study_id: Optional[str] = None, direction: str | None = None, purge: bool = False):
        """Return message objects for this Human (optionally filtered)."""
        return self._interaction_manager.get_messages(study_id=study_id, direction=direction, purge=purge)
    
    # Keep legacy alias for backward compatibility
    _is_valid_email = staticmethod(ContactInfo.is_valid_email)
    
    @property
    def contact_info(self) -> Dict[str, Optional[str]]:
        """Get a dictionary of the human's contact information.
        
        Returns:
            Dict[str, Optional[str]]: Dictionary with all contact methods
            
        Examples:
            >>> h = Human(traits={"age": 30}, email="test@example.com")
            >>> info = h.contact_info
            >>> info['email']
            'test@example.com'
            >>> info['phone'] is None
            True
            
            >>> h2 = Human(traits={}, phone="555-1234", prolific_id="ABC123")
            >>> info2 = h2.contact_info
            >>> info2['phone']
            '555-1234'
            >>> info2['prolific_id']
            'ABC123'
        """
        return self._contact_info.as_dict()
    
    # ------------------------------------------------------------------
    # Read-only attribute accessors (legacy convenience)
    # ------------------------------------------------------------------
    @property
    def email(self) -> Optional[str]:
        """Return the participant's email, if available (read-only)."""
        return self._contact_info.email

    @property
    def phone(self) -> Optional[str]:
        return self._contact_info.phone

    @property
    def prolific_id(self) -> Optional[str]:
        return self._contact_info.prolific_id

    @property
    def ep_username(self) -> Optional[str]:
        return self._contact_info.ep_username
    
    def duplicate(self) -> Human:
        """Create a deep copy of this human with all traits and contact information.
        
        Returns:
            Human: A new human instance that is functionally identical to this one
            
        Examples:
            >>> h = Human(traits={"age": 30}, email="test@example.com", name="Original")
            >>> h_copy = h.duplicate()
            >>> h_copy.email == h.email
            True
            >>> h_copy.traits == h.traits
            True
            >>> h_copy.name == h.name
            True
            >>> h_copy is h
            False
        """
        new_human = Human.from_dict(self.to_dict())
        
        # Transfer methods from the parent class duplicate method
        if hasattr(self, "answer_question_directly"):
            answer_question_directly = self.answer_question_directly
            def newf(self, question, scenario):
                return answer_question_directly(question, scenario)
            new_human.add_direct_question_answering_method(newf)
            
        if hasattr(self, "dynamic_traits_function"):
            dynamic_traits_function = self.dynamic_traits_function
            new_human.dynamic_traits_function = dynamic_traits_function
            
        return new_human
    
    def to_dict(self, add_edsl_version=True, full_dict=False) -> dict:
        """Serialize to a dictionary with EDSL info and contact information.
        
        Args:
            add_edsl_version: Whether to add EDSL version information
            full_dict: Whether to include all fields even if not set
            
        Returns:
            dict: Dictionary representation of the Human
        """
        d = super().to_dict(add_edsl_version=add_edsl_version, full_dict=full_dict)
        
        # Add contact information to the dictionary
        d["contact_info"] = self._contact_info.as_dict()
        
        if add_edsl_version:
            d["edsl_class_name"] = self.__class__.__name__
            
        return d
    
    @classmethod
    def from_dict(cls, human_dict: dict) -> Human:
        """Deserialize from a dictionary.
        
        Args:
            human_dict: Dictionary representation of a Human
            
        Returns:
            Human: A Human instance created from the dictionary
        """
        # Make a copy to avoid modifying the input
        human_data = copy.deepcopy(human_dict)
        
        # Extract contact information
        contact_info = human_data.pop("contact_info", {})
        
        # Build minimal instance then restore ancillary fields held by Agent
        h = cls(name=human_data.get("name"), **contact_info)

        # Restore trait-related metadata directly (since constructor no longer accepts them)
        h.traits = human_data.get("traits", {})  # type: ignore[attr-defined]
        h.codebook = human_data.get("codebook")   # type: ignore[attr-defined]
        h.instruction = human_data.get("instruction")  # type: ignore[attr-defined]
        h.traits_presentation_template = human_data.get("traits_presentation_template")  # type: ignore[attr-defined]
        return h
    
    def __repr__(self) -> str:
        """Return a string representation of the Human.
        
        Returns:
            str: String representation including traits and contact info
        """
        class_name = self.__class__.__name__
        items = []
        
        # Add traits
        traits_str = f"traits = {self.traits}"
        items.append(traits_str)
        
        # Add contact info
        contact_items = []
        if self._contact_info.email:
            contact_items.append(f'email = """{self._contact_info.email}"""')
        if self._contact_info.phone:
            contact_items.append(f'phone = """{self._contact_info.phone}"""')
        if self._contact_info.prolific_id:
            contact_items.append(f'prolific_id = """{self._contact_info.prolific_id}"""')
        if self._contact_info.ep_username:
            contact_items.append(f'ep_username = """{self._contact_info.ep_username}"""')
            
        # Add name if present
        if self.name:
            items.append(f'name = """{self.name}"""')
            
        # Add codebook if present
        if self.codebook:
            items.append(f"codebook = {self.codebook}")
            
        # Combine all items
        return f"{class_name}({', '.join(items + contact_items)})"
    
    @classmethod
    def example(cls, randomize: bool = False) -> Human:
        """Return an example Human instance.
        
        Args:
            randomize: If True, adds randomness to the example data
            
        Returns:
            Human: An example Human instance with sample traits and contact info
            
        Examples:
            >>> h = Human.example()
            >>> h.email
            'example@example.com'
            >>> h.name
            'John Doe'
            >>> h.traits['age']
            35
            >>> h.traits['occupation']
            'software developer'
        """
        h = cls(name="John Doe", email="example@example.com")
        # Populate illustrative traits after construction
        h.traits = {"age": 35, "occupation": "software developer", "hobby": "photography"}  # type: ignore[attr-defined]
        return h


def main():
    """Demonstrate core capabilities using HumanInteractionManager."""

    # ------------------------------------------------------------------
    # Create two participants with different contact modalities
    # ------------------------------------------------------------------
    alice = Human(name="Alice", email="alice@example.com")
    bob = Human(name="Bob", phone="555-123-4567", ep_username="bob_ep")

    # ------------------------------------------------------------------
    # Interact with participants *directly* (manager is hidden)
    # ------------------------------------------------------------------

    # Send introductory messages
    alice.send_message("Welcome to the study, Alice!")
    bob.send_message("Hi Bob — thanks for joining.")

    # Send study invitations
    study_id = "study_abc"
    alice.send_study(study_id)
    bob.send_study(study_id)

    print("Pending (Alice):", alice.list_pending_studies())
    # Simulate Alice accepting study via her manager (not exposed on Human)
    alice._interaction_manager.accept_study(study_id)  # pylint: disable=protected-access
    print("Pending (Alice):", alice.list_pending_studies())
    print("Past (Alice):", alice.list_past_studies())

    # Retrieve and display inbox contents
    print("--- Alice inbox ---", [m.content for m in alice.get_messages(direction="received")])
    print("--- Bob inbox ---", [m.content for m in bob.get_messages(direction="received")])

    # Make payments (in Expected Parrot credits)
    alice.make_payment(10)
    bob.make_payment(12.5)

    # Display serialized representation
    print("--- Serialized Alice ---")
    print(alice.to_dict())

    print("--- Serialized Bob ---")
    print(bob.to_dict())


if __name__ == "__main__":
    #import doctest
    #doctest.testmod(optionflags=doctest.ELLIPSIS)
    main()