import re

from .exceptions import SharedStateAuthoringError


class SharedState:
    _RESERVED = {"scope", "store", "primitives"}

    def __init__(self, scope: str, store, **primitives):
        self.scope = scope
        self.store = store
        self.primitives = {}
        for name, primitive in primitives.items():
            if name in self._RESERVED:
                raise SharedStateAuthoringError(f"primitive name '{name}' is reserved")
            primitive.name = name
            primitive.parent = self
            self.primitives[name] = primitive
            setattr(self, name, primitive)

    def resolve_scope(self, agent_traits=None) -> str:
        """Resolve an optional ``{{ agent.trait }}`` scope for one interview."""
        match = re.fullmatch(r"\s*{{\s*agent\.([A-Za-z_]\w*)\s*}}\s*", self.scope)
        if match is None:
            return self.scope
        trait = match.group(1)
        traits = agent_traits or {}
        if trait not in traits:
            raise SharedStateAuthoringError(
                f"shared-state scope requires agent trait '{trait}'"
            )
        return str(traits[trait])

    def read(self, *, agent_traits=None, scope=None, at_version=None):
        resolved_scope = scope or self.resolve_scope(agent_traits)
        return self.store.read(
            resolved_scope, self, agent_traits, at_version=at_version
        )

    def close(self, *, agent_traits=None, scope=None):
        resolved_scope = scope or self.resolve_scope(agent_traits)
        return self.store.close(resolved_scope)

    def scopes(self) -> list[str]:
        """Return all realized scopes in first-seen order."""
        return self.store.scopes()

    def history(self, *, scope=None, target=None):
        """Return typed events, optionally filtered by scope and primitive target."""
        return self.store.history(scope=scope, target=target)

    def snapshots(self, *, scopes=None, context=None):
        """Return current snapshots for all or selected realized scopes."""
        selected = self.scopes() if scopes is None else list(scopes)
        return [
            (scope, self.read(scope=scope, agent_traits=context))
            for scope in selected
        ]

    def records(self, *, target=None, scopes=None, context=None):
        """Flatten current snapshots into analysis-friendly dictionaries."""
        records = []
        for scope, snapshot in self.snapshots(scopes=scopes, context=context):
            value = snapshot.state if target is None else snapshot.state[target]
            payload = dict(value) if isinstance(value, dict) else {"value": value}
            records.append(
                payload
                | {
                    "scope": scope,
                    "version": snapshot.version,
                    "closed": snapshot.closed,
                }
            )
        return records

    def render_markdown(self, *, agent_traits=None, scope=None) -> str:
        """Render the current snapshot using each primitive's Markdown view."""
        resolved_scope = scope or self.resolve_scope(agent_traits)
        snapshot = self.read(scope=resolved_scope)
        status = "closed" if snapshot.closed else "open"
        sections = [
            f"# Shared state: {resolved_scope}",
            "",
            f"_Version {snapshot.version} · {status}_",
        ]
        for name, primitive in self.primitives.items():
            sections.extend(
                [
                    "",
                    f"## {name.replace('_', ' ').title()}",
                    "",
                    primitive.render_markdown(snapshot.state[name]),
                ]
            )
        return "\n".join(sections)

    def to_dict(self):
        return {
            "scope": self.scope,
            "store": self.store.to_dict(),
            "primitives": {
                name: primitive.to_dict() for name, primitive in self.primitives.items()
            },
        }

    @classmethod
    def from_dict(cls, data):
        from .configured_game import ConfiguredSharedGame
        from .file_store import FileStateStore
        from .primitives import (
            SharedAuction,
            SharedBinaryMarket,
            SharedBilateralTrade,
            SharedBeautyContest,
            SharedBudgetPool,
            SharedCoalitionPool,
            SharedCentipedeGame,
            SharedCheapTalkGame,
            SharedCommonPoolGame,
            SharedAgenda,
            SharedCounterMap,
            SharedDictatorGame,
            SharedDelphiPanel,
            SharedDeferredAcceptance,
            SharedDocument,
            SharedDoubleAuction,
            SharedForecast,
            SharedLog,
            SharedMatchPool,
            SharedMatrixGame,
            SharedMarketEntryGame,
            SharedMessageBoard,
            SharedMoneyRequestGame,
            SharedNegotiation,
            SharedNashDemandGame,
            SharedRepeatedMatrixGame,
            SharedResourceBoard,
            SharedPrincipalAgentGame,
            SharedSignalSchedule,
            SharedSignalingGame,
            SharedSealedAuction,
            SharedTrustGame,
            SharedUltimatumGame,
            SharedVotingGame,
            SharedWorkPool,
        )

        store = FileStateStore.from_dict(data["store"])
        primitives = {}
        for name, config in data["primitives"].items():
            if config["type"] == "configured_game":
                primitives[name] = ConfiguredSharedGame.from_dict(config)
            elif config["type"] == "counter_map":
                primitives[name] = SharedCounterMap(config["keys"])
            elif config["type"] == "match_pool":
                primitives[name] = SharedMatchPool(
                    config["items"], config["rule"], config.get("capacity", 1)
                )
            elif config["type"] == "deferred_acceptance":
                primitives[name] = SharedDeferredAcceptance(
                    config["capacities"], config["priorities"]
                )
            elif config["type"] == "auction":
                primitives[name] = SharedAuction(config["item"], config["increment"])
            elif config["type"] == "double_auction":
                primitives[name] = SharedDoubleAuction(config["participants"])
            elif config["type"] == "message_board":
                primitives[name] = SharedMessageBoard()
            elif config["type"] == "negotiation":
                primitives[name] = SharedNegotiation(config["subject"])
            elif config["type"] == "agenda":
                primitives[name] = SharedAgenda()
            elif config["type"] == "forecast":
                primitives[name] = SharedForecast()
            elif config["type"] == "delphi_panel":
                primitives[name] = SharedDelphiPanel(
                    config["panel_size"],
                    config["range_threshold"],
                    config["median_shift_threshold"],
                    config["min_rounds"],
                )
            elif config["type"] == "log":
                primitives[name] = SharedLog(
                    visible_to=config.get("visible_to"),
                    viewer_trait=config.get("viewer_trait", "name"),
                )
            elif config["type"] == "work_pool":
                primitives[name] = SharedWorkPool(config["items"])
            elif config["type"] == "resource_board":
                primitives[name] = SharedResourceBoard(
                    config["incidents"], config["resources"]
                )
            elif config["type"] == "binary_market":
                primitives[name] = SharedBinaryMarket(
                    contract=config["contract"],
                    liquidity=config["liquidity"],
                    initial_cash=config["initial_cash"],
                )
            elif config["type"] == "coalition_pool":
                primitives[name] = SharedCoalitionPool(config["coalitions"])
            elif config["type"] == "signal_schedule":
                primitives[name] = SharedSignalSchedule(config["signals"])
            elif config["type"] == "budget_pool":
                primitives[name] = SharedBudgetPool(config["total"], config["projects"])
            elif config["type"] == "document":
                primitives[name] = SharedDocument(
                    config["title"], config["initial_text"]
                )
            elif config["type"] == "ultimatum_game":
                primitives[name] = SharedUltimatumGame(config["stake"])
            elif config["type"] == "money_request_game":
                primitives[name] = SharedMoneyRequestGame(
                    config["minimum"], config["maximum"], config["bonus"]
                )
            elif config["type"] == "matrix_game":
                primitives[name] = SharedMatrixGame(
                    config["actions"], config["payoffs"]
                )
            elif config["type"] == "repeated_matrix_game":
                primitives[name] = SharedRepeatedMatrixGame(
                    config["actions"], config["payoffs"], config["rounds"]
                )
            elif config["type"] == "dictator_game":
                primitives[name] = SharedDictatorGame(config["endowment"])
            elif config["type"] == "trust_game":
                primitives[name] = SharedTrustGame(
                    config["endowment"], config["multiplier"]
                )
            elif config["type"] == "beauty_contest":
                primitives[name] = SharedBeautyContest(
                    config["player_count"], config["factor"]
                )
            elif config["type"] == "common_pool_game":
                primitives[name] = SharedCommonPoolGame(
                    config["player_count"], config["stock"], config["max_request"]
                )
            elif config["type"] == "centipede_game":
                primitives[name] = SharedCentipedeGame(
                    config["take_payoffs"], config["final_pass_payoffs"]
                )
            elif config["type"] == "market_entry_game":
                primitives[name] = SharedMarketEntryGame(
                    config["player_count"],
                    config["outside_payoff"],
                    config["entry_value"],
                    config["congestion_cost"],
                )
            elif config["type"] == "sealed_auction":
                primitives[name] = SharedSealedAuction(
                    config["mechanism"], config["bidder_count"]
                )
            elif config["type"] == "bilateral_trade":
                primitives[name] = SharedBilateralTrade()
            elif config["type"] == "signaling_game":
                primitives[name] = SharedSignalingGame(config["wage"])
            elif config["type"] == "nash_demand_game":
                primitives[name] = SharedNashDemandGame(config["pie"])
            elif config["type"] == "voting_game":
                primitives[name] = SharedVotingGame(
                    config["candidates"], config["voter_count"]
                )
            elif config["type"] == "cheap_talk_game":
                primitives[name] = SharedCheapTalkGame()
            elif config["type"] == "principal_agent_game":
                primitives[name] = SharedPrincipalAgentGame(
                    config["output_value"],
                    config["high_probability"],
                    config["low_probability"],
                    config["high_cost"],
                )
            else:
                raise SharedStateAuthoringError(
                    f"unknown primitive type '{config['type']}'"
                )
        return cls(data["scope"], store, **primitives)
