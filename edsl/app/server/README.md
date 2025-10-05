# EDSL App Server

A FastAPI backend and React frontend for running EDSL applications in the browser.

## ✨ Features

- **App Registry**: Browse all available EDSL apps in one place
- **Interactive Surveys**: Fill out app parameters with user-friendly forms
- **Live Execution**: Run apps and see results in real-time
- **Multiple Formatters**: Choose different output formats without re-running
- **Simple Deployment**: Docker Compose or local development setup

## 🚀 Quick Start (Docker Compose)

```bash
cd edsl/app/server

# Start the full stack
docker-compose up --build

# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
```

## 💻 Development Setup (Local)

### Option 1: Use the startup script

```bash
cd edsl/app/server

# Make sure dependencies are installed first:
# pip install 'edsl[services]'
# cd frontend && npm install && cd ..

./start_local.sh
```

### Option 2: Manual setup

**Terminal 1 - Backend:**
```bash
cd edsl/app/server
python server.py
# Runs on http://localhost:8000
```

**Terminal 2 - Frontend:**
```bash
cd edsl/app/server/frontend
npm install
npm run dev
# Runs on http://localhost:3000
```

## 📋 Usage Workflow

### Step 1: Push an App to the Server

From Python:

```python
from edsl.app.examples.meal_planner import app

# Push to server
app_id = app.push_to_server("http://localhost:8000")
print(f"App pushed with ID: {app_id}")
```

Or use the test script:
```bash
cd edsl/app/server
python test_push_app.py
```

### Step 2: Use the Web Interface

1. **Open** http://localhost:3000
2. **Browse** available apps in the card grid
3. **Click** an app to open its survey form
4. **Fill out** the initial survey questions
5. **Submit** to execute the app
6. **Choose** an output formatter to view results

## 🔧 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/apps` | List all apps |
| GET | `/apps/{app_id}` | Get app metadata |
| GET | `/apps/{app_id}/parameters` | Get survey questions |
| POST | `/apps` | Push a new app |
| POST | `/apps/{app_id}/execute` | Execute an app with parameters |
| DELETE | `/apps/{app_id}` | Remove an app |
| GET | `/health` | Health check |
| GET | `/stats` | Server statistics |

## 🏗️ Architecture

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────┐
│  React Frontend  │────▶│  FastAPI Backend │────▶│  SQLite DB   │
│  (Port 3000)     │◀────│  (Port 8000)     │◀────│              │
│                  │     │                  │     │              │
│  - App List      │     │  - App Storage   │     │  - Apps      │
│  - Survey Forms  │     │  - Execution     │     │  - Executions│
│  - Results View  │     │  - Formatters    │     │              │
└──────────────────┘     └──────────────────┘     └──────────────┘
```

## 📝 Example: Pushing and Using an App

```python
# push_my_app.py
from edsl import Survey, Agent
from edsl.questions import QuestionFreeText, QuestionMultipleChoice
from edsl.app import App
from edsl.app.output_formatter import OutputFormatter

# Create a simple app
survey = Survey([
    QuestionFreeText(
        question_name="topic",
        question_text="What topic would you like advice on?"
    )
])

agent = Agent(name="advisor")
question = QuestionFreeText(
    question_name="advice",
    question_text="Give advice about: {{ scenario.topic }}"
)

jobs = Survey([question]).by(agent)

formatter = OutputFormatter().select('answer.advice').to_markdown().view()

app = App(
    initial_survey=survey,
    application_name="Simple Advisor",
    description="Get AI advice on any topic",
    jobs_object=jobs,
    output_formatters={"markdown": formatter},
    default_formatter_name="markdown"
)

# Push to server
app_id = app.push_to_server("http://localhost:8000")
print(f"✅ App ready at: http://localhost:3000")
```

## 🐛 Troubleshooting

**Backend won't start:**
- Make sure FastAPI is installed: `pip install 'edsl[services]'`
- Check port 8000 is not in use: `lsof -i :8000`

**Frontend won't start:**
- Install dependencies: `cd frontend && npm install`
- Check port 3000 is not in use: `lsof -i :3000`

**App execution fails:**
- Check backend logs for detailed error messages
- Verify your EDSL API keys are configured
- Make sure the app serialization/deserialization is working

## 🔮 Future Enhancements

- [ ] Add authentication and user management
- [ ] Support file uploads for scenarios
- [ ] Real-time progress updates for long-running jobs
- [ ] Export results in multiple formats (PDF, CSV, etc.)
- [ ] App versioning and history
- [ ] Collaborative features and sharing
