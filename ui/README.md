# Resume Structurer UI

Angular (NgModule-based) app to upload a resume PDF, review and edit structured data in forms, and export or copy the JSON.

## Run

1. Start the FastAPI backend from repo root:
   ```bash
   uvicorn FastAPI.app.main:app --reload --reload-dir FastAPI/app --reload-dir parser
   ```

2. From this folder:
   ```bash
   npm install
   npm start
   ```

3. Open http://localhost:4200. Upload a PDF, edit sections in the tabs, then use **Copy JSON** or **Export JSON**.

## API

- `apiBaseUrl` is set in `src/environments/environment.ts` (default `http://localhost:8000`). Update for production in `environment.prod.ts`.
