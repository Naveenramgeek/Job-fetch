# JobFetch Setup

## Database

PostgreSQL connection (already configured):
```
postgresql://<db_user>:<db_password>@<db_host>:5432/<db_name>
```

**Provision database** (run once before first deploy, or after PostgreSQL upgrade):
```bash
cd FastAPI
# Set admin credentials if not using default postgres user
export POSTGRES_ADMIN_USER=postgres
export POSTGRES_ADMIN_PASSWORD=your_admin_password
# Or set full admin URL:
# export POSTGRES_ADMIN_URL=postgresql://postgres:adminpass@localhost:5432/postgres

python -m app.scripts.init_db_production
```

For managed DBs (RDS, Cloud SQL) where role/db are created via console:
```bash
python -m app.scripts.init_db_production --extension-only
```

Tables are created automatically on backend startup.

**Migration** (if `user_job_matches` already exists): add status and applied_at:
```sql
ALTER TABLE user_job_matches ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT 'pending';
ALTER TABLE user_job_matches ADD COLUMN IF NOT EXISTS applied_at TIMESTAMPTZ;
```

## Backend

1. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # or venv\Scripts\activate on Windows
   ```

2. Install dependencies:
   ```bash
   pip install -r FastAPI/requirements.txt
   ```

3. (Optional) Create `.env` in `FastAPI/` to override defaults:
   ```
   DATABASE_URL=postgresql://<db_user>:<db_password>@<db_host>:5432/<db_name>
   SECRET_KEY=your-secret-key
   ```

4. Run the backend:
   ```bash
   uvicorn FastAPI.app.main:app --reload --reload-dir FastAPI/app --reload-dir parser
   ```

## Frontend

```bash
cd ui && npm install && npm start
```

## Admin

To promote the first admin after creating a user:
```bash
python -m app.scripts.promote_admin your@email.com
```
Then log out and log back in to see the Admin link in the nav.

## Features

- **Auth**: Real sign up (email, password, confirm password) and login with JWT
- **Resume**: Parse PDF and store parsed resume in PostgreSQL
- **Models**: `users`, `resumes`, `jobs` tables (jobs populated later)
