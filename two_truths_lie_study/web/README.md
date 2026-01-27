# Why Would I Lie - Web Interface

Next.js 14 web application for the "Why Would I Lie" LLM deception experiment platform.

## Getting Started

1. Install dependencies:
```bash
npm install
```

2. Create environment file:
```bash
cp .env.local.example .env.local
```

3. Run the development server:
```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## Application Structure

### Pages

- **Design** (`/design`) - Configure experiment parameters
  - Game type, rounds, word count limits
  - Model selection with temperature controls
  - Strategy and fact category selection
  - Preset management

- **Run** (`/run`) - Execute experiments with live streaming
  - Real-time experiment execution
  - Phase indicators (Story → Q&A → Verdict)
  - Live output streaming
  - Round summary cards

- **Results** (`/results`) - Analyze completed experiments
  - Experiment list with filtering
  - Aggregate statistics
  - Confidence calibration charts
  - Round-by-round inspector

- **Human Play** (`/human-play`) - Future interactive mode (placeholder)
  - Human as Storyteller
  - Human as Judge
  - Mixed mode

### Key Components

- `TabNavigation` - Main tab navigation
- `ModelSelector` - LLM model selection (future)
- `StrategyPicker` - Strategy configuration (future)
- `LiveStream` - Real-time experiment output (future)
- `RoundCard` - Round summary display (future)
- `ResultsTable` - Results data table (future)

## Tech Stack

- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **UI Components**: shadcn/ui
- **Icons**: Lucide React
- **Deployment**: Vercel

## API Integration

The frontend connects to the Python FastAPI backend at:
- Development: `http://localhost:8000`
- Production: Configured via `NEXT_PUBLIC_API_URL`

### API Endpoints Used

- `GET /api/config/models` - Available models
- `GET /api/config/facts` - Fact database
- `POST /api/experiment/start` - Start experiment
- `GET /api/stream/{id}` - SSE stream for live updates
- `GET /api/experiment/results/{id}` - Get results

## Development Phases

### ✅ Phase 1: Foundation (COMPLETE)
- [x] Next.js project setup
- [x] Tab navigation and layout
- [x] Basic design form
- [x] All 4 main pages created

### 🚧 Phase 2: Experiment Execution (NEXT)
- [ ] Connect to GameEngine via API
- [ ] Server-Sent Events integration
- [ ] Live streaming UI
- [ ] Error handling

### 📋 Phase 3: Results & Persistence
- [ ] Results storage integration
- [ ] Round inspector implementation
- [ ] Export functionality
- [ ] Charts and visualizations

### 🎨 Phase 4: Polish & Human Play
- [ ] Responsive design refinements
- [ ] Human Play mode implementation
- [ ] Preset system
- [ ] Documentation

## Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run start` - Start production server
- `npm run lint` - Run ESLint

## Deployment

This app is configured for Vercel deployment:

1. Push to GitHub
2. Connect repository to Vercel
3. Configure environment variables
4. Deploy

See `vercel.json` for deployment configuration.

## Next Steps

- [ ] Implement API client utilities
- [ ] Add Server-Sent Events handling
- [ ] Build reusable UI components
- [ ] Add form validation
- [ ] Implement error boundaries
- [ ] Add loading states
- [ ] Write tests
