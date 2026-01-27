# Web Interface - Phase 1 Complete ✅

**Date**: January 18, 2026
**Status**: Foundation scaffold complete and running

## Summary

Phase 1 of the "Why Would I Lie" web interface has been successfully implemented. The application provides a complete scaffold with all 4 main pages, navigation, and a FastAPI backend skeleton.

## What Was Built

### Frontend (Next.js 14 + TypeScript)

**Location**: `/web`

#### Pages Created
1. **Design** (`/design`) - Full experiment configuration form
   - Game type selection (Standard, All Truth, All Lies, Majority Lies)
   - Rounds and word count configuration
   - Model selection with temperature sliders
   - Strategy pickers for storyteller and judge
   - Fact category multi-select
   - Preset save/load buttons

2. **Run** (`/run`) - Live experiment execution interface
   - Start/Pause/Stop controls
   - Progress bar with round tracking
   - Phase indicators (Story → Questions → Verdict)
   - Live output panels (mock data for now)
   - Completed rounds summary cards
   - Collapsible technical logs section

3. **Results** (`/results`) - Analysis dashboard
   - Experiment list table with filtering
   - Aggregate statistics cards
   - Confidence calibration chart placeholder
   - Round inspector with detailed view
   - Export functionality button

4. **Human Play** (`/human-play`) - Future mode placeholder
   - Three mode cards (Storyteller, Judge, Mixed)
   - Email signup form
   - Research contribution info section

#### Components
- **TabNavigation** - Main navigation with icons and active state
- **Layout** - Updated with TabNavigation and styling

#### Configuration
- `vercel.json` - Vercel deployment configuration
- `.env.local.example` - Environment variable template
- `components.json` - shadcn/ui configuration
- Updated `README.md` with full documentation

### Backend (FastAPI + Python)

**Location**: `/backend`

#### API Structure
```
backend/
├── main.py              # FastAPI app with CORS
├── requirements.txt     # Dependencies
├── routes/
│   ├── config.py        # Models, facts, presets endpoints
│   ├── experiment.py    # Experiment CRUD operations
│   └── streaming.py     # Server-Sent Events for live updates
└── adapters/
    └── game_runner.py   # GameEngine wrapper (skeleton)
```

#### Endpoints Implemented
- `GET /` - Health check
- `GET /health` - Detailed health status
- `GET /api/config/models` - List available models
- `GET /api/config/facts` - Get fact database
- `GET /api/config/presets` - List presets
- `POST /api/config/presets` - Save preset
- `POST /api/experiment/start` - Start experiment
- `GET /api/experiment/status/{id}` - Get status
- `POST /api/experiment/stop/{id}` - Stop experiment
- `GET /api/experiment/results/{id}` - Get results
- `GET /api/experiment/list` - List all experiments
- `GET /api/stream/{id}` - SSE stream

## Technology Stack

### Frontend
- Next.js 16.1.3 (App Router)
- TypeScript
- Tailwind CSS
- shadcn/ui components
- Lucide React icons

### Backend
- FastAPI 0.109.0
- Uvicorn with hot reload
- Pydantic for validation
- SSE-Starlette for streaming

## Running the Application

### Frontend
```bash
cd web
npm install
npm run dev
```
Access at: http://localhost:3000

### Backend (when ready)
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```
Access at: http://localhost:8000

## Current Status

✅ **Complete**
- Project scaffold and structure
- All 4 pages with UI mockups
- Tab navigation
- Design form with all parameters
- Backend API skeleton with all routes
- Development environment setup
- Documentation (READMEs)

🚧 **Next Steps (Phase 2)**
- Connect frontend to backend API
- Implement actual GameEngine integration in `game_runner.py`
- Add Server-Sent Events handling in frontend
- Real-time streaming of experiment output
- Error handling and loading states
- Form validation
- API client utilities

📋 **Future Phases**
- **Phase 3**: Results persistence, export, charts
- **Phase 4**: Human Play mode, polish, deployment

## File Tree

```
two_truths_lie_study/
├── web/
│   ├── app/
│   │   ├── design/
│   │   │   └── page.tsx          ✅ Full config form
│   │   ├── run/
│   │   │   └── page.tsx          ✅ Live execution UI
│   │   ├── results/
│   │   │   └── page.tsx          ✅ Analysis dashboard
│   │   ├── human-play/
│   │   │   └── page.tsx          ✅ Future mode placeholder
│   │   ├── layout.tsx            ✅ With TabNavigation
│   │   ├── page.tsx              ✅ Redirects to /design
│   │   └── globals.css
│   ├── components/
│   │   └── TabNavigation.tsx    ✅ Main navigation
│   ├── lib/
│   │   └── utils.ts              ✅ shadcn utils
│   ├── public/
│   ├── .env.local.example        ✅ Environment template
│   ├── components.json           ✅ shadcn config
│   ├── vercel.json               ✅ Vercel deployment
│   ├── package.json
│   ├── tsconfig.json
│   └── README.md                 ✅ Full documentation
│
└── backend/
    ├── routes/
    │   ├── __init__.py
    │   ├── config.py             ✅ Config endpoints
    │   ├── experiment.py         ✅ Experiment CRUD
    │   └── streaming.py          ✅ SSE streaming
    ├── adapters/
    │   ├── __init__.py
    │   └── game_runner.py        ✅ GameEngine wrapper skeleton
    ├── main.py                   ✅ FastAPI app
    ├── requirements.txt          ✅ Dependencies
    └── README.md                 ✅ Backend docs
```

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                   Browser (localhost:3000)               │
│  ┌────────────┬────────────┬────────────┬─────────────┐ │
│  │  Design    │    Run     │  Results   │ Human Play  │ │
│  └────────────┴────────────┴────────────┴─────────────┘ │
└─────────────────────────────────────────────────────────┘
                         │ HTTP/SSE
                         ▼
┌─────────────────────────────────────────────────────────┐
│            FastAPI Backend (localhost:8000)              │
│  ┌─────────────────────────────────────────────────┐    │
│  │  /api/config    /api/experiment    /api/stream  │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│          GameEngine Adapter (game_runner.py)            │
│                                                          │
│  ┌──────────────────────────────────────────────┐       │
│  │  Wraps existing two_truths_lie package       │       │
│  │  - GameEngine                                │       │
│  │  - EDSLAdapter                               │       │
│  │  - ResultStore                               │       │
│  └──────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────┘
```

## Testing

The frontend is currently running at http://localhost:3000. You can:
1. Navigate between all 4 tabs
2. See the design form with all configuration options
3. View the run page UI mockup
4. Browse the results page layout
5. Check out the human play placeholder

The backend can be started separately to test API endpoints via http://localhost:8000/docs (Swagger UI).

## Notes

- All UI is functional but uses mock data
- Backend routes are implemented but need GameEngine integration
- SSE streaming is scaffolded but needs real event emission
- Form submissions don't persist yet (Phase 2)
- No authentication/authorization (future consideration)

## Next Session Goals

1. Create API client utilities in frontend
2. Connect Design form to `/api/experiment/start`
3. Implement SSE connection in Run page
4. Complete `game_runner.py` GameEngine integration
5. Test end-to-end experiment execution

---

**Phase 1 Completion**: All objectives met. Ready for Phase 2 development.
