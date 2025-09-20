# Repository Guidelines
- 使用中文回答问题
- 在经过我同意之前不要修改代码
- 每次修改完代码之后,更新项目文档
This concise guide helps contributors work effectively on the Trademe monorepo.

## Project Structure & Module Organization
- `frontend/` — Vite + React + TypeScript. Pages in `src/pages/*Page.tsx`; tests in `src/tests/*.test.tsx`.
- `backend/user-service/` — Node/Express + Prisma. Source in `src/`, tests in `tests/`.
- `backend/trading-service/` — Python FastAPI. App in `app/`, tests in `tests/`, deps in `requirements.txt`.
- `database/` SQL init/migration scripts; `nginx/` configs; `assets/`, `scripts/`, and various reports under repo root.

## Build, Test, and Development Commands
- Prereqs: Node 18+, npm 8+; Python 3.11/3.12; Docker (optional).
- Install:
  - Root tools: `npm install`
  - Frontend: `cd frontend && npm install`
  - User Service: `cd backend/user-service && npm install`
  - Trading Service: `cd backend/trading-service && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- Develop (concurrent): from repo root `npm run dev`.
- Frontend: `cd frontend && npm run dev` • Build: `npm run build` • Test: `npm test` or `npm run test:coverage`.
- User Service: `cd backend/user-service && npm run dev` • Build: `npm run build` • Test: `npm test`.
- Trading Service: `cd backend/trading-service && uvicorn app.main:app --reload --port 8001` • Tests: `pip install pytest pytest-asyncio && pytest -q`.
- Docker: `npm run docker:up` / `npm run docker:down` using `docker-compose.yml`.

## Coding Style & Naming Conventions
- JS/TS: Prettier + ESLint. 2‑space indent, semicolons, single quotes. React components PascalCase; hooks/use*; tests `*.test.ts[x]`.
- Python: PEP 8, 4‑space indent, type hints where practical. Modules `snake_case.py`; FastAPI entry `uvicorn app.main:app`.
- Env vars UPPER_SNAKE_CASE. Do not hardcode secrets.

## Testing Guidelines
- Frameworks: Vitest (frontend), Jest (user-service), Pytest (trading-service).
- Naming: `frontend/src/tests/*.test.tsx`, `backend/user-service/tests/**/*.test.ts`, `backend/trading-service/tests/test_*.py`.
- Aim for meaningful unit tests and fast integration tests; target 70%+ coverage on changed code. Prefer hermetic tests; use `.env.example` values.

## Commit & Pull Request Guidelines
- History is mixed; adopt Conventional Commits: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`. Example: `feat(frontend): add websocket status toast`.
- PRs: focused scope, description of changes, linked issues, test plan, and screenshots/GIFs for UI.
- Keep noise out of VCS: don’t commit `node_modules/`, `dist/`, `.venv/`, `logs/`, or `.env*`.

## Security & Configuration Tips
- Copy `.env.example` → `.env` in repo root and service folders; never commit secrets.
- Review CORS, rate limits, and JWT settings before deploying. Prefer running locally via Docker for parity.

## Agent-Specific Instructions
- Make surgical changes, preserve structure, and update related docs/tests. Prefer small PRs and fast iteration.
