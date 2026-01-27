"""
Adapter to wrap the existing Two Truths and a Lie game engine
for use with the FastAPI backend.
"""
import sys
from pathlib import Path
from typing import Dict, Any, Callable, Optional

# Add the two_truths_lie package to Python path
project_root = Path(__file__).parent.parent.parent
two_truths_lie_path = project_root / "two_truths_lie"
sys.path.insert(0, str(two_truths_lie_path))

# TODO: Import actual game engine components
# from src.game_engine import GameEngine
# from src.config.schema import GameConfig, LLMConfig
# from src.edsl_adapter import EDSLAdapter

class GameEngineAdapter:
    """
    Adapter class to run experiments using the existing game engine.
    Provides callbacks for streaming events to the web interface.
    """

    def __init__(self, on_event: Optional[Callable] = None):
        """
        Initialize the adapter.

        Args:
            on_event: Optional callback function for streaming events
        """
        self.on_event = on_event
        # TODO: Initialize actual game engine
        # self.engine = GameEngine()

    async def run_experiment(
        self,
        experiment_id: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run a complete experiment with the given configuration.

        Args:
            experiment_id: Unique identifier for this experiment
            config: Experiment configuration dictionary

        Returns:
            Experiment results dictionary
        """
        # TODO: Convert config dict to GameConfig
        # game_config = self._config_from_dict(config)

        # TODO: Run experiment and emit events
        # for round_num in range(config['rounds']):
        #     self._emit_event('round_start', {'round': round_num + 1})
        #     result = await self._run_single_round(game_config)
        #     self._emit_event('round_complete', result)

        # Placeholder response
        return {
            "experiment_id": experiment_id,
            "status": "completed",
            "rounds": config.get("rounds", 0),
            "results": []
        }

    async def _run_single_round(self, config: Any) -> Dict[str, Any]:
        """Run a single round of the game."""
        # TODO: Implement using GameEngine
        # - Generate stories
        # - Run Q&A
        # - Get verdict
        # - Return round data
        pass

    def _emit_event(self, event_type: str, data: Dict[str, Any]):
        """Emit an event through the callback if provided."""
        if self.on_event:
            self.on_event(event_type, data)

    def _config_from_dict(self, config: Dict[str, Any]) -> Any:
        """Convert config dictionary to GameConfig object."""
        # TODO: Implement conversion
        pass


# Singleton instance
_adapter: Optional[GameEngineAdapter] = None

def get_adapter(on_event: Optional[Callable] = None) -> GameEngineAdapter:
    """Get or create the game engine adapter instance."""
    global _adapter
    if _adapter is None:
        _adapter = GameEngineAdapter(on_event)
    return _adapter
