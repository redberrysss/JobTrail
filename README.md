# JobTrail

A local-first job application tracker with a small SQLite backend. Use **Add application** to save roles, search/filter the list, advance a stage, or remove a record. Four sample applications are seeded on first run; every change is saved to a local SQLite database.

## CV angle
Demonstrates a full CRUD REST API (Python stdlib `http.server` + SQLite), a responsive application UI, accessible form validation, search/filter logic, and status transitions across a real client–server boundary.

## Stack
- **Frontend:** single `index.html` — vanilla HTML, CSS, and JavaScript (no frameworks, no build step)
- **Backend:** `server.py` — Python 3 standard library only (`http.server`, `sqlite3`); no `pip install` required

## Run

```bash
python3 server.py          # serves http://localhost:8000 and creates jobtrail.db
```

Then open <http://localhost:8000> in your browser. Pass a port number to use a different one, e.g. `python3 server.py 3000`.

Data is stored in `jobtrail.db` (git-ignored) next to `server.py`. Delete that file to reset back to the seeded sample applications.

## API

| Method | Path            | Body                          | Returns            |
| ------ | --------------- | ----------------------------- | ------------------ |
| GET    | `/api/jobs`     | —                             | `{ jobs: [...] }`  |
| POST   | `/api/jobs`     | `{ company, role, stage, nextStep }` | the created job |
| PATCH  | `/api/jobs/:id` | `{ stage }`                   | the updated job    |
| DELETE | `/api/jobs/:id` | —                             | `{ ok: true }`     |

Errors are returned as `{ "error": "..." }` with an appropriate status code.
