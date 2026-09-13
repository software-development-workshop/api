# UdeSA-X Mobile App

Mobile client for UdeSA-X, built with [Expo](https://expo.dev) SDK 57, [React Native](https://reactnative.dev) 0.86, and TypeScript using [Expo Router](https://docs.expo.dev/router/introduction/). The client implements a single, flat dark theme using system fonts and native primitives.

This delivery implements the mobile foundation and authentication slice for **Issue #48** (E1S2 Login and E1S3 Logout):

- Single-stack navigation with protected routes (`/sign-in` and `/(app)/index`).
- Sign-in against the Accounts API using an email or `@handle` with password.
- In-memory JWT session lifecycle, automatic expiration handling, and sign-out.
- Shared HTTP client and authenticated request helpers consumed by Bruno in **Issue #49** (home, composer, and post publication confirmation).

> [!NOTE]
> **Scope boundaries:**
>
> - **Product target:** The product is strictly a native mobile application (Android and iOS). The web preview script (`npm run web`) exists solely for development inspection and quick code review; it is not a production target.
> - **Out of scope:** App Store and Google Play distribution, automated token refresh endpoints (none exist on the backend), registration, email verification, password recovery, profile editing, and client-side disk persistence.
> - **Hardware verification note:** No physical phone has been tested yet. Follow the procedure below to connect and verify on hardware.

---

## Prerequisites

- **Node.js**: 24 LTS.
  - Windows 11 ARM64 is supported using the official native Node.js ARM64 binary. Running on a physical phone avoids having to set up or run heavy native emulators on ARM64 hardware.
- **Expo Go client**: Install a compatible [Expo Go](https://expo.dev/go) app matching **SDK 57** on your physical phone (Android or iOS).
- **Network**: Both your development computer and the physical phone must be connected to the same trusted Wi-Fi or local area network (LAN). Guest networks with client isolation will block communication.
- **Backend services**: Running instance of Accounts and Posts APIs via Docker Compose.

---

## Environment & Network Setup

### 1. Opt into LAN Access for Backend APIs

By default, Docker Compose binds backend services to `127.0.0.1`, which is inaccessible to external physical devices. Use the mobile compose override as described in [root README: Connect a physical phone](../../README.md#connect-a-physical-phone):

```powershell
docker compose -f compose.yaml -f compose.mobile.yaml up --build -d
```

This configuration exposes:

- **Accounts API**: port `8000` bound to `0.0.0.0` (accessible across the LAN).
- **Posts API**: port `8001` bound to `0.0.0.0` (accessible across the LAN).
- **PostgreSQL databases**: ports `5433` and `5434` remain securely bound to `127.0.0.1` (loopback only).

Find your computer's local IPv4 address (e.g., via `ipconfig` or PowerShell `Get-NetIPConfiguration | Where-Object IPv4DefaultGateway | Select-Object InterfaceAlias,IPv4Address`).

### 2. Verify Connectivity from the Phone Browser

Before starting the app or attempting to sign in, open the phone's web browser and navigate to both health checks:

1. `http://<computer-lan-ip>:8000/health`
2. `http://<computer-lan-ip>:8001/health`

Both must respond with a healthy HTTP status. If requests time out or fail, check Windows Firewall or router client-isolation settings.

> [!IMPORTANT]
> **Metro Tunnel vs. API Connectivity:**
> Running Metro with the `--tunnel` flag (`npx expo start --tunnel`) only tunnels the Metro JavaScript packager bundle. **It does not tunnel API traffic to Accounts or Posts.** The physical phone must still be able to reach your computer's LAN IP address directly on ports 8000 and 8001, or you must configure deployed HTTPS endpoints.

### 3. Configure Environment Variables

In `apps/mobile/`, copy the template to `.env`:

```bash
cp .env.template .env
```

Edit `.env` to supply your computer's reachable private LAN IP or deployed HTTPS URLs:

```env
EXPO_PUBLIC_ACCOUNTS_API_URL=http://<computer-lan-ip>:8000
EXPO_PUBLIC_POSTS_API_URL=http://<computer-lan-ip>:8001
```

#### Public Environment Variables

| Variable                       | Description                                   | Example                    |
| ------------------------------ | --------------------------------------------- | -------------------------- |
| `EXPO_PUBLIC_ACCOUNTS_API_URL` | Base URL for Accounts API (without `/api/v1`) | `http://192.168.1.50:8000` |
| `EXPO_PUBLIC_POSTS_API_URL`    | Base URL for Posts API (without `/api/v1`)    | `http://192.168.1.50:8001` |

> [!WARNING]
>
> - Base URLs **must not** contain trailing slashes or the `/api/v1` path suffix. The API client appends path segments (e.g., `/api/v1/sessions`).
> - Do **not** use `localhost` or `127.0.0.1` when targeting a physical phone; `localhost` on a phone resolves to the phone itself.
> - **Zero Secrets**: Never commit `.env` or embed backend secrets (e.g., `JWT_SECRET`, mail API keys, database credentials, or test account passwords) in mobile configuration or client code.

---

## Running the App

1. Install dependencies:

   ```bash
   npm ci
   ```

2. Start the Expo development server in LAN mode:

   ```bash
   npx expo start --lan
   # or
   npm start -- --lan
   ```

3. Open the **Expo Go** app on your physical phone and scan the QR code displayed in the terminal.

---

## Phone Walkthrough & Verification

> [!NOTE]
> Testing requires an **existing, verified test account**. Account registration, email verification, and password creation are performed via the backend API or seed scripts (see [root README](../../README.md#work-on-a-service)), not through the mobile client. Do not create accounts or send verification emails from the app.

Follow these steps to exercise the authentication flow:

1. **Sign In (`/sign-in`)**:
   - Enter your identifier: either an email (`user@example.com`) or handle (`@user`).
   - Enter the account password.
   - Tap **Ingresar**.
   - **Submission behavior**: The button displays a loading spinner and becomes disabled, preventing duplicate submissions or double taps.
2. **Error Handling**:
   - **Invalid credentials**: Submitting wrong credentials returns `401 invalid-credentials` and renders the generic message: `"Email, usuario o contraseña incorrectos."`
   - **Unverified account**: Attempting to sign into an unverified account returns `403 unverified-account` with message: `"Tu cuenta aún no fue verificada. Revisá tu casilla de correo."`
   - **Suspended account**: Returns `403 suspended-account` with message: `"Esta cuenta ha sido suspendida."`
   - **Locked account**: After five wrong passwords, submit the correct password during the 15-minute lock to receive `423 account-temporarily-locked`. Wrong passwords continue to return the generic `401` response.
   - **Network failure or timeout**: Displays an offline / connectivity warning (`"No pudimos conectar con el servidor..."` / `"La solicitud tardó demasiado tiempo..."`). Form fields remain filled, enabling an immediate retry once connection is restored.
3. **Authenticated Home (`/(app)/index`)**:
   - On successful sign-in, the API returns `{ access_token, token_type: "bearer", expires_in }`.
   - The token is held **strictly in RAM** (React Context memory) with a calculated `expiresAt` timestamp.
   - The app navigates to the minimal home screen, displaying `"Sesión iniciada"` and a **Cerrar sesión** button.
4. **Navigation History Protection**:
   - The root navigator uses protected stacks. Once authenticated, pressing the Android hardware Back button or gesture will **not** return to the sign-in screen.
5. **Sign Out**:
   - Tap **Cerrar sesión**.
   - The app attempts `POST /api/v1/sessions/logout` with the active Bearer token.
   - The in-memory session is erased immediately, navigation history is cleared, and the app redirects to `/sign-in`.
6. **Unconfirmed Server Revocation**:
   - If the network drops or the server fails to confirm revocation during sign-out, local session data is still wiped immediately (`signOut()` resolves with `{ revoked: false }`).
   - The sign-in screen displays the warning notice: `"Saliste de este dispositivo. No pudimos confirmar el cierre de sesión en el servidor"`.
   - Tokens are never persisted to disk or retained for retry.
7. **Process Restart**:
   - Closing or killing the mobile app process completely drops the in-memory token. Relaunching the app will prompt for credentials on `/sign-in`.
8. **Session Expiry & Stale Response Handling**:
   - When the app returns to the foreground (`AppState` becomes `active`), session validity is checked against `expiresAt`.
   - Any authenticated API call verifies token expiration beforehand.
   - An expired token or a backend `401` / `invalid-access-token` response immediately invalidates the session and redirects the user to `/sign-in`.

---

## Shared Contracts for Issue #49 (Companion Feature)

Issue #49 (owned by Bruno) implements the post composer, publication, and confirmation views. All network and session interactions must use the shared contracts in `src/api/` and `src/auth/`.

### 1. `useAuthenticatedApi()`

The primary hook for executing authenticated requests:

```ts
import { useAuthenticatedApi } from '../api/useAuthenticatedApi';

export function useComposePost() {
  const { request, session } = useAuthenticatedApi();

  const createPost = async (content: string) => {
    return await request<PostResponse>('posts', '/api/v1/posts', {
      method: 'POST',
      body: { content },
    });
  };

  return { createPost, session };
}
```

**Safe Usage Guarantees**:

- **Pre-request validation**: Inspects `Date.now() >= session.expiresAt`. If expired, it triggers `invalidate()` and throws `ApiError(401, 'invalid-access-token', ...)`.
- **Automatic Bearer header**: Injects `Authorization: Bearer <activeToken>` automatically.
- **Race condition & stale response protection**: If the session changed or expired while a request was in flight, the response is discarded and an `ApiError` is thrown.
- **Automatic session invalidation**: If the backend returns `401` or `invalid-access-token`, the current session is invalidated, returning the user to `/sign-in`.
- **No automatic POST retries**: Automatic retries on `POST` requests are prohibited to prevent creating duplicate posts on network interruptions.

### 2. `requestJson<T>()`

Low-level HTTP utility located at `src/api/http.ts`:

```ts
import { requestJson } from '../api/http';

const response = await requestJson<{ status: string }>('accounts', '/health', {
  method: 'GET',
});
```

- Accepts `service` (`'accounts'` or `'posts'`), target `path` (e.g. `'/api/v1/posts'`), and options.
- Configured with a strict **10-second timeout** via `AbortController`.
- Handles `204 No Content` gracefully without attempting JSON parsing.
- Automatically maps RFC 7807 / RFC 9457 Problem Details error payloads into strongly typed `ApiError` instances with Spanish user-facing messages.

### 3. `useSession()`

Context hook located at `src/auth/SessionContext.tsx`:

```ts
interface SessionContextValue {
  session: { accessToken: string; expiresAt: number } | null;
  signIn: (identifier: string, password: string) => Promise<void>;
  signOut: () => Promise<{ revoked: boolean }>;
  invalidate: () => void;
  getSession: () => SessionData | null;
  sessionNotice: string | null;
  clearSessionNotice: () => void;
}
```

- Access current session metadata (`accessToken`, `expiresAt`).
- `signOut()` returns `{ revoked: boolean }` and immediately cleans up local RAM state.

---

## Package Scripts & Quality Checks

Run all commands from within `apps/mobile/`:

| Command                    | Action                                                                         |
| -------------------------- | ------------------------------------------------------------------------------ |
| `npm run format:check`     | Verify formatting across files using Prettier                                  |
| `npm run format`           | Auto-format files using Prettier                                               |
| `npm run lint`             | Check lint rules using ESLint                                                  |
| `npm run typecheck`        | Run TypeScript compiler check (`tsc --noEmit`)                                 |
| `npm run test:unit`        | Run unit tests with Jest (`--runInBand --coverage`)                            |
| `npm run test:integration` | Run integration tests using Node/tsx test runner                               |
| `npm run build`            | Export production native bundles (`expo export -p android -p ios`)             |
| `npm run web`              | Start local development review preview in browser (mobile review preview only) |

---

## Continuous Integration (CI)

The GitHub Actions workflow is defined in `.github/workflows/mobile-ci.yml`. It runs sequentially on every branch push and pull request:

1. Sets up Node.js 24 LTS with npm dependency caching against `apps/mobile/package-lock.json`.
2. Installs dependencies via `npm ci`.
3. Runs checks sequentially:
   - `npm run format:check`
   - `npm run lint`
   - `npm run typecheck`
   - `npm run test:unit`
   - `npm run test:integration`
   - `npm run build`
4. Provides dummy loopback URLs (`http://127.0.0.1:8000` and `http://127.0.0.1:8001`) to satisfy build bundling without requiring external services or secrets.
5. Employs `concurrency` with `cancel-in-progress: true` to prevent redundant check runs.
