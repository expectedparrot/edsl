# Why Would I Lie - Backend API

FastAPI backend for the Two Truths and a Lie experiment platform.

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the development server:
```bash
python main.py
```

The API will be available at http://localhost:8000

## API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Endpoints

### Configuration
- `GET /api/config/models` - List available LLM models
- `GET /api/config/facts` - Get fact database
- `GET /api/config/presets` - List experiment presets
- `POST /api/config/presets` - Save new preset

### Experiments
- `POST /api/experiment/start` - Start new experiment
- `GET /api/experiment/status/{id}` - Get experiment status
- `POST /api/experiment/stop/{id}` - Stop running experiment
- `GET /api/experiment/results/{id}` - Get experiment results
- `GET /api/experiment/list` - List all experiments

### Streaming
- `GET /api/stream/{experiment_id}` - Server-Sent Events stream for live updates

## Architecture

```
backend/
├── main.py              # FastAPI application entry point
├── routes/
│   ├── config.py        # Configuration endpoints
│   ├── experiment.py    # Experiment management
│   └── streaming.py     # SSE streaming
└── adapters/
    └── game_runner.py   # Wrapper for existing GameEngine
```

## Integration with GameEngine

The `adapters/game_runner.py` module wraps the existing Two Truths and a Lie game engine
from the `two_truths_lie` package. It provides:

- Configuration conversion (web config → GameConfig)
- Event streaming for real-time updates
- Async execution of experiments

## Development

The backend is designed to be developed alongside the frontend. Key features:

1. **CORS enabled** for local development (localhost:3000)
2. **Auto-reload** enabled for fast iteration
3. **Type safety** with Pydantic models
4. **SSE support** for real-time experiment streaming

## Next Steps

- [ ] Complete GameEngine integration in `game_runner.py`
- [ ] Implement persistent storage for results
- [ ] Add authentication/authorization
- [ ] Add rate limiting
- [ ] Deploy to production (Docker + cloud hosting)
