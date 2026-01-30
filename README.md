# Social Engineering Simulator

Training app against social engineering: practice recognizing tactics in emails, messages, and calls.

## Tech stack

- Python 3.11+
- FastAPI
- SQLAlchemy 2.0
- Pydantic v2
- SQLite (default); switch to PostgreSQL via `DATABASE_URL`
- Jinja2 templates (no React)
- JWT auth optional (MVP: guest mode + optional login)
- Alembic migrations (minimal)

## Setup on Windows

1. **Create and activate a virtual environment**

   ```powershell
   cd c:\Users\user\Documents\projects
   python -m venv .venv
   .venv\Scripts\activate
   ```

2. **Install dependencies**

   ```powershell
   pip install -r requirements.txt
   ```

3. **Optional: copy env example**

   ```powershell
   copy .env.example .env
   ```
   Edit `.env` if you need a different database URL or secret.

4. **Run the app**

   ```powershell
   uvicorn app.main:app --reload
   ```

5. **Open in browser**

   - http://127.0.0.1:8000 — home
   - http://127.0.0.1:8000/train — start training
   - http://127.0.0.1:8000/result — view results

## First run

- The app creates the SQLite DB and seeds 12 scenarios on first run (or when the DB is empty).
- No login required: use guest mode. Progress is stored in a session cookie.

## Routes

| Method | Path       | Description        |
|--------|------------|--------------------|
| GET    | /          | Home page          |
| GET    | /train     | Show next scenario |
| POST   | /train     | Submit choice      |
| GET    | /train/feedback | Feedback after choice |
| GET    | /result    | Results & stats     |
| POST   | /reset     | Reset progress      |

## API (JSON)

| Method | Path               | Description          |
|--------|--------------------|----------------------|
| GET    | /api/scenarios/{id} | Get one scenario     |
| POST   | /api/attempts       | Submit choice        |
| GET    | /api/stats          | Current stats        |

## Test scenarios (3 to click through)

1. **Urgent password reset** (email, Urgency) — Start training → choose “Open the company website in my browser and go to account settings” → Safe.
2. **IT support request** (messenger, Authority) — Choose “Ask for a ticket number and verify via the company portal” → Safe.
3. **Limited offer** (email, Scarcity) — Choose “Click to reserve my spot” → Unsafe; see explanation and tactic.

## Risk score and level

- **Risk score:** 0–100 (starts at 50). Wrong choice +10, correct −5; clamped 0–100.
- **Level:** 0–20 Security Ninja, 21–40 Aware User, 41–60 Rookie, 61–80 At Risk, 81–100 High Risk.

## Alembic (optional)

```powershell
alembic upgrade head
```

Migrations are in `alembic/versions/`. The app also creates tables on startup if they don’t exist.

## License

MIT.
