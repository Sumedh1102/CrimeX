# Deploying to Vercel

CrimeX deploys as two Vercel projects from this one repository:

| Project | Source | What it serves |
|---|---|---|
| `crimex-api` | `.vercel-api/`, assembled in CI by `scripts/build_vercel_api.py` | FastAPI (`backend.main:app`) as a Python function, reading the pipeline's Parquet/JSON outputs |
| `crimex-web` | `frontend/` (Vercel Git integration) | Next.js dashboard; rewrites `/api/v1/*` to `CRIMEX_API_URL` |

The browser only talks to the dashboard's origin. Next.js proxies API calls server-side, so
CORS settings are not needed.

## Why the API is assembled, not built from the repo root

- **Artifacts are generated.** `data/processed/` and `artifacts/` are gitignored and come from
  `make pipeline` (synthetic data, training, predictions). The GitHub Actions workflow runs the
  pipeline, then deploys its outputs with the code.
- **Bundle size.** Vercel Python functions must stay under 500 MB uncompressed. The full
  `pyproject.toml` pulls XGBoost and its CUDA libraries (over 400 MB on their own). The API
  only imports FastAPI, pandas, pyarrow, NumPy, SciPy, Pydantic, PyYAML and global-land-mask
  (about 390 MB unpacked), so the bundle ships a separate `requirements.txt` with just those.

The deployed data is the same **SYNTHETIC / DEMONSTRATION** dataset the pipeline always
generates. It stays labelled as synthetic in every API response and in the UI.

## One-time setup

1. **Create the API project.** In Vercel, go to Add New → Project, pick any template or
   import this repository, and name it `crimex-api`. Then, in the project's Settings → Git,
   disconnect the repository: the GitHub workflow deploys this project, not Vercel's Git
   integration. (Or run `npx vercel link` in an empty folder to create it from the CLI.)
   Note its Project ID (Settings → General) and your Team/Org ID (Team Settings → General).
2. **Add GitHub secrets.** In the repository, go to Settings → Secrets and variables → Actions:
   - `VERCEL_TOKEN`: an access token from https://vercel.com/account/tokens
   - `VERCEL_ORG_ID`: the team or personal account ID
   - `VERCEL_API_PROJECT_ID`: the `crimex-api` project ID
3. **Deploy the API.** Actions → "Deploy API to Vercel" → Run workflow. It takes about 6
   minutes: install, pipeline, bundle, deploy. Then open
   `https://<crimex-api-domain>/api/v1/health` to check it. Pushes to the default branch that
   touch `backend/`, `ml/`, `configs/`, `data/official/`, `scripts/` or `pyproject.toml`
   redeploy it automatically.
4. **Create the dashboard project.** Add New → Project → import this repository, and set:
   - Root Directory: `frontend`
   - Framework preset: Next.js (also pinned in `frontend/vercel.json`)
   - Environment variable `CRIMEX_API_URL` = `https://<crimex-api-domain>` (no trailing
     slash, no `/api/v1`). Set it for Production and Preview.
   - Optional: `NEXT_PUBLIC_MAP_STYLE_URL` (see `frontend/README.md`)

   Deploy. Each push then redeploys the dashboard; pull requests get preview URLs.

`CRIMEX_API_URL` is read when `next.config.ts` builds the rewrites, so after changing it,
redeploy the dashboard.

## Local check of the API bundle

```bash
make pipeline
.venv/bin/python scripts/build_vercel_api.py      # writes .vercel-api/
cd .vercel-api && npx vercel dev                  # or: npx vercel deploy --prod
```

## Limits to know

- The API is read-only over the bundled artifacts. To refresh predictions, rerun the
  workflow. Feedback writes need the planned PostGIS store (`docs/db-schema.sql`), not the
  function's filesystem, which is ephemeral.
- On a cold start the function loads the Parquet files into memory (a few seconds on the
  first request). Later requests on the same instance are served from cache.
- The free (Hobby) plan is for non-commercial use. A police-station deployment belongs on a
  paid plan or self-hosted infrastructure, behind authentication.
