# Frontend

This folder is the News-Yapper website. It is the only folder Vercel should build.

The browser talks to this Next.js app. This app calls the FastAPI service in `../backend` using `API_BASE_URL`. It does not talk to Neon, Gemini, or Groq.

## Vercel

1. Import the Git repository.
2. Set **Root Directory** to `frontend`.
3. Framework preset: **Next.js**. Leave the build command as `npm run build` and the output as the Next.js default.
4. Add these environment variables. `API_JWT_SECRET` and `AUTH_SECRET` must be the same values you set on Render.

| Name | Value |
|---|---|
| `API_BASE_URL` | The Render API URL, for example `https://news-yapper-api.onrender.com` |
| `API_JWT_SECRET` | Long random secret. Same value as on the API and the worker |
| `AUTH_SECRET` | A different long random secret |
| `AUTH_TRUST_HOST` | `true` |
| `DEMO_MODE` | `true` while you still want the name-only login. Set `false` before a public launch and add GitHub or Google OAuth |

Optional, only if you turn off demo login:

| Name | Value |
|---|---|
| `AUTH_GITHUB_ID` / `AUTH_GITHUB_SECRET` | GitHub OAuth app |
| `AUTH_GOOGLE_ID` / `AUTH_GOOGLE_SECRET` | Google OAuth app |

Redeploy after changing variables. The site reads them on the server. Nothing in this list is sent to the browser except the normal login session.
