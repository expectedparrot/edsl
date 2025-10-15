"""MacroDeploy dataclass for managing EDSL macro deployment configuration."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Literal
from enum import Enum


class ExecutionMode(str, Enum):
    """Where and how the macro can be executed."""
    COOP_ONLINE = "coop_online"  # Run on Coop servers only
    DOWNLOADABLE = "downloadable"  # User can download source and run locally
    HYBRID = "hybrid"  # Both options available


class PricingModel(str, Enum):
    """How the macro is priced."""
    FREE = "free"
    PER_CALL = "per_call"
    TOKEN_MARKUP = "token_markup"
    SUBSCRIPTION = "subscription"
    CUSTOM = "custom"


@dataclass
class PricingConfig:
    """Pricing configuration details."""
    model: PricingModel = PricingModel.FREE
    per_call_price: Optional[float] = None  # Price per macro execution
    token_markup_percent: Optional[float] = None  # Markup % on LLM token costs
    subscription_price: Optional[float] = None  # Monthly/annual subscription
    subscription_period: Optional[Literal["monthly", "annual"]] = None
    currency: str = "USD"
    custom_details: Optional[str] = None  # Free-form pricing description


@dataclass
class AuthorInfo:
    """Information about the macro creator."""
    name: Optional[str] = None
    email: Optional[str] = None
    organization: Optional[str] = None
    website: Optional[str] = None


@dataclass
class MacroDeploy:
    """
    Deployment configuration for an EDSL Macro.

    This dataclass holds all metadata and settings relevant to deploying
    and distributing an EDSL macro through Coop or other channels.

    Attributes:
        execution_mode: How users can execute the macro (online, downloadable, or both)
        source_available: Whether source code is viewable/available
        license: Software license (e.g., "MIT", "Apache-2.0", "Proprietary")
        github_url: GitHub repository URL, if applicable
        author: Information about the macro creator
        pricing: Pricing configuration
        executor: Who runs the macro ("creator" uses creator's resources, "user" uses user's)
        requires_coop: Whether macro requires Coop infrastructure
        requires_api_keys: Whether user needs to provide their own API keys
        description: Deployment-specific description or notes
        version: Macro version string
        tags: Searchable tags for categorization

    Example:
        >>> deploy = MacroDeploy(
        ...     execution_mode=ExecutionMode.HYBRID,
        ...     source_available=True,
        ...     license="MIT",
        ...     github_url="https://github.com/example/my-macro",
        ...     author=AuthorInfo(name="John Doe", email="john@example.com"),
        ...     pricing=PricingConfig(model=PricingModel.TOKEN_MARKUP, token_markup_percent=10.0),
        ...     executor="user",
        ...     requires_api_keys=True,
        ... )
    """

    # Execution settings
    execution_mode: ExecutionMode = ExecutionMode.COOP_ONLINE
    source_available: bool = False
    requires_coop: bool = True
    requires_api_keys: bool = False
    executor: Literal["creator", "user"] = "user"

    # Licensing and source
    license: Optional[str] = None
    github_url: Optional[str] = None

    # Author information
    author: Optional[AuthorInfo] = None

    # Pricing
    pricing: PricingConfig = field(default_factory=PricingConfig)

    # Metadata
    description: Optional[str] = None
    version: str = "1.0.0"
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dictionary."""
        return {
            "execution_mode": self.execution_mode.value if isinstance(self.execution_mode, ExecutionMode) else self.execution_mode,
            "source_available": self.source_available,
            "requires_coop": self.requires_coop,
            "requires_api_keys": self.requires_api_keys,
            "executor": self.executor,
            "license": self.license,
            "github_url": self.github_url,
            "author": {
                "name": self.author.name,
                "email": self.author.email,
                "organization": self.author.organization,
                "website": self.author.website,
            } if self.author else None,
            "pricing": {
                "model": self.pricing.model.value if isinstance(self.pricing.model, PricingModel) else self.pricing.model,
                "per_call_price": self.pricing.per_call_price,
                "token_markup_percent": self.pricing.token_markup_percent,
                "subscription_price": self.pricing.subscription_price,
                "subscription_period": self.pricing.subscription_period,
                "currency": self.pricing.currency,
                "custom_details": self.pricing.custom_details,
            },
            "description": self.description,
            "version": self.version,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MacroDeploy":
        """Create MacroDeploy instance from dictionary."""
        author_data = data.get("author")
        author = AuthorInfo(**author_data) if author_data else None

        pricing_data = data.get("pricing", {})
        pricing_data["model"] = PricingModel(pricing_data.get("model", "free"))
        pricing = PricingConfig(**pricing_data)

        return cls(
            execution_mode=ExecutionMode(data.get("execution_mode", "coop_online")),
            source_available=data.get("source_available", False),
            requires_coop=data.get("requires_coop", True),
            requires_api_keys=data.get("requires_api_keys", False),
            executor=data.get("executor", "user"),
            license=data.get("license"),
            github_url=data.get("github_url"),
            author=author,
            pricing=pricing,
            description=data.get("description"),
            version=data.get("version", "1.0.0"),
            tags=data.get("tags", []),
        )

    @classmethod
    def example_free_open_source(cls) -> "MacroDeploy":
        """Example: Free, open-source macro with downloadable code."""
        return cls(
            execution_mode=ExecutionMode.HYBRID,
            source_available=True,
            license="MIT",
            github_url="https://github.com/example/free-app",
            author=AuthorInfo(name="Open Source Developer"),
            pricing=PricingConfig(model=PricingModel.FREE),
            executor="user",
            requires_api_keys=True,
            requires_coop=False,
            tags=["open-source", "free"],
        )

    @classmethod
    def example_commercial_hosted(cls) -> "MacroDeploy":
        """Example: Commercial macro, hosted only, per-call pricing."""
        return cls(
            execution_mode=ExecutionMode.COOP_ONLINE,
            source_available=False,
            license="Proprietary",
            author=AuthorInfo(
                name="Commercial Developer",
                email="support@example.com",
                organization="Example Corp",
            ),
            pricing=PricingConfig(
                model=PricingModel.PER_CALL,
                per_call_price=0.50,
                currency="USD",
            ),
            executor="creator",
            requires_api_keys=False,
            requires_coop=True,
            tags=["commercial", "hosted"],
        )

    @classmethod
    def example_token_markup(cls) -> "MacroDeploy":
        """Example: Macro with token markup pricing model."""
        return cls(
            execution_mode=ExecutionMode.HYBRID,
            source_available=True,
            license="Apache-2.0",
            github_url="https://github.com/example/markup-app",
            author=AuthorInfo(name="Developer", email="dev@example.com"),
            pricing=PricingConfig(
                model=PricingModel.TOKEN_MARKUP,
                token_markup_percent=15.0,
            ),
            executor="user",
            requires_api_keys=True,
            tags=["token-markup", "hybrid"],
        )


if __name__ == "__main__":
    # Demonstrate usage
    print("Example 1: Free Open Source")
    deploy1 = MacroDeploy.example_free_open_source()
    print(deploy1)
    print("\nSerialized:")
    print(deploy1.to_dict())

    print("\n" + "="*50)
    print("Example 2: Commercial Hosted")
    deploy2 = MacroDeploy.example_commercial_hosted()
    print(deploy2)

    print("\n" + "="*50)
    print("Example 3: Token Markup")
    deploy3 = MacroDeploy.example_token_markup()
    print(deploy3)

    # Test round-trip serialization
    print("\n" + "="*50)
    print("Testing round-trip serialization...")
    data = deploy1.to_dict()
    restored = MacroDeploy.from_dict(data)
    print(f"Original == Restored: {deploy1 == restored}")
