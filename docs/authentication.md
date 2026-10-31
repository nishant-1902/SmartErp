# Authentication

## Browser sign-in

1. The login form sends the user's email and password to `POST /api/auth/login/`.
2. The API returns a short-lived access token and the user's role and
   permissions. The browser stores the refresh token in an `HttpOnly` cookie.
3. The access token stays in JavaScript memory only: in React authentication
   state and the API client's module variable. It is not written to
   `localStorage`, `sessionStorage`, or a persistent browser store.
4. The API client sends the access token as a bearer `Authorization` header.
   The browser automatically includes the refresh cookie on requests because
   Axios uses `withCredentials: true`.
5. On reload, the app silently calls `POST /api/auth/refresh/`, saves the new
   access token in memory, then calls `GET /api/auth/me/`. A module-level
   single-flight promise means React StrictMode's development-only duplicate
   effects share one boot refresh request.
6. When an API request returns `401`, the API client makes one shared refresh
   request for concurrent failures and retries each original request once.
   Failed refresh clears the in-memory session and returns the user to `/login`.
7. Logout calls `POST /api/auth/logout/` to revoke the refresh-token family and
   clear the cookie, then clears the in-memory session.

Login and refresh requests are excluded from automatic 401 refresh retries.
This prevents a failed refresh from triggering another refresh indefinitely.
During silent boot restore, a refresh failure simply leaves the user signed
out; it does not redirect repeatedly.

## CORS and cookies

The frontend (`http://localhost:5173`) and API (`http://localhost:8000`) have
different origins because their ports differ. The browser therefore applies
cross-origin rules. Configure `CORS_ALLOWED_ORIGINS` in the backend environment
with the exact frontend origin, such as `http://localhost:5173`. Do not use
`*`: credentialed CORS must use an explicit origin.

Axios `withCredentials: true` asks the browser to send eligible cookies and to
accept cookies set by the API. JavaScript cannot read the refresh token because
it is `HttpOnly`; the browser manages it. The API must respond with both the
matching `Access-Control-Allow-Origin` value and
`Access-Control-Allow-Credentials: true`.

The bearer `Authorization` header and `X-Requested-With` header cause the
browser to send a CORS preflight `OPTIONS` request before some API calls. The
backend must allow those headers, along with `Content-Type` and
`Idempotency-Key`. The frontend sends `X-Requested-With: XMLHttpRequest` on
requests; the backend requires it on refresh and logout as a CSRF safeguard.

For local development, set `CORS_ALLOWED_ORIGINS=http://localhost:5173` in
`backend/.env` and `VITE_API_BASE_URL=http://localhost:8000/api` in
`frontend/.env`. For production use the exact deployed frontend origin, HTTPS,
and secure refresh-cookie settings. Cross-site deployments may also require
`SameSite=None; Secure` and corresponding browser cookie policy support.

## Frontend route guards

`ProtectedRoute` redirects signed-out users to `/login`. `RoleRoute` and the
`hasPermission` helper can hide or redirect UI that does not match the user's
role/permissions. These checks are only for user experience. The backend
permission matrix remains the security boundary and must protect every API
operation.

## Troubleshooting

- **CORS error in browser console:** Check the exact scheme, hostname, and port
  in `CORS_ALLOWED_ORIGINS`; restart Django after changing its environment.
- **Refresh returns 403:** Confirm the `X-Requested-With` header is present.
- **Refresh returns 401 after login:** Confirm the browser stores the cookie,
  the refresh cookie path covers `/api/auth/refresh/`, credentials are enabled,
  and frontend requests use `withCredentials`.
- **Preflight fails:** Inspect the browser Network panel for the `OPTIONS`
  request and confirm `Authorization`, `Content-Type`, `X-Requested-With`, and
  `Idempotency-Key` are allowed by the backend.
- **User remains on login after reload:** Check the refresh response, then the
  `/auth/me/` response, and confirm the cookie's SameSite/Secure settings fit
  the frontend/API deployment.
