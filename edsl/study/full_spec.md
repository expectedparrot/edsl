# Agent Git Repository Service — Technical Reference

> Version 1.0 · March 2026

---

## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Server](#server)
   - [Data Model](#data-model)
   - [API Reference](#api-reference)
   - [Authentication & Signature Verification](#authentication--signature-verification)
   - [GitLab Integration](#gitlab-integration)
   - [Webhook Processing](#webhook-processing)
4. [Client](#client)
   - [Key Management](#key-management)
   - [Registration](#registration)
   - [Pushing](#pushing)
   - [Pulling](#pulling)
   - [Recovery](#recovery)
5. [Signed Payload Format](#signed-payload-format)
6. [Error Reference](#error-reference)
7. [Security Notes](#security-notes)
8. [Out of Scope for v1](#out-of-scope-for-v1)

---

## Overview

The Agent Git Repository Service is a control plane for agent-owned git repositories hosted on GitLab. It manages identity, ownership, and access token issuance. It is not in the git data path — agents communicate with GitLab directly for all git operations.

**The service handles:**

- Registering a repository triple `(owner, project, topic)` and binding it to an agent's public key
- Issuing short-lived, scoped GitLab access tokens on demand
- Lazy provisioning of GitLab projects on first push
- Recording push and pull activity via webhooks and agent self-reporting
- Credential recovery via single-use recovery codes

**The service does not handle:**

- Git traffic, diffs, or file contents
- GitLab group or namespace management
- Manifest or metadata submission (deferred to v2)

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client Agent                            │
│                                                                 │
│  ┌──────────────┐   signed requests    ┌─────────────────────┐  │
│  │ Ed25519      │ ──────────────────▶  │                     │  │
│  │ private key  │                      │    Meta-server      │  │
│  └──────────────┘ ◀──────────────────  │                     │  │
│                    token + gitlab_url  └──────────┬──────────┘  │
│                                                   │             │
│  git push / git pull (direct, token auth)         │ admin ops   │
│  ────────────────────────────────────────────▶    │ (Projects   │
└───────────────────────────────────────────────    │  API)       │
                                                    ▼             │
                                         ┌─────────────────────┐  │
                                         │       GitLab        │  │
                                         │                     │  │
                                         │  Projects API       │  │
                                         │  Git repos          │  │
                                         │  Push webhooks ─────┼──┘
                                         │  Access tokens      │
                                         └─────────────────────┘
                                                    │
                                         POST /webhook (push events)
                                                    │
                                         ┌──────────▼──────────┐
                                         │    Meta-server      │
                                         │    (webhook rcvr)   │
                                         └─────────────────────┘
```

The meta-server requires one long-lived GitLab credential: a bot account or group access token with `api` scope, configured at startup via environment variable. This is used exclusively for admin operations (project creation, webhook registration, access token minting) and is never exposed to agents.

---

## Server

### Data Model

All timestamps are `TIMESTAMPTZ` (UTC). All UUIDs are v4.

```sql
-- Core repository registry
CREATE TABLE repos (
    uuid          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    owner         TEXT        NOT NULL,
    project       TEXT        NOT NULL,
    topic         TEXT        NOT NULL,
    pub_key       BYTEA       NOT NULL,        -- Ed25519 public key, 32 bytes
    gitlab_url    TEXT,                        -- NULL until first push-req
    hook_secret   BYTEA,                       -- NULL until first push-req; 32 random bytes
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_accessed TIMESTAMPTZ,
    CONSTRAINT repos_triple_unique UNIQUE (owner, project, topic)
);

-- Push activity, populated via GitLab webhook
CREATE TABLE push_events (
    id            BIGSERIAL   PRIMARY KEY,
    repo_uuid     UUID        NOT NULL REFERENCES repos(uuid),
    pushed_at     TIMESTAMPTZ NOT NULL,
    branch        TEXT,
    commit_count  INT,
    pusher_name   TEXT,
    raw_payload   JSONB
);

-- Pull activity, populated by agent self-reporting
CREATE TABLE pull_events (
    id            BIGSERIAL   PRIMARY KEY,
    repo_uuid     UUID        NOT NULL REFERENCES repos(uuid),
    pulled_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Single-use recovery codes; hashes only, never plaintext
CREATE TABLE recovery_codes (
    id            BIGSERIAL   PRIMARY KEY,
    repo_uuid     UUID        NOT NULL REFERENCES repos(uuid),
    code_hash     TEXT        NOT NULL,        -- sha256(code), hex-encoded
    used_at       TIMESTAMPTZ                  -- NULL until burned
);

CREATE INDEX ON push_events (repo_uuid, pushed_at DESC);
CREATE INDEX ON pull_events (repo_uuid, pulled_at DESC);
CREATE INDEX ON recovery_codes (repo_uuid) WHERE used_at IS NULL;
```

**Notes:**

- `gitlab_url` and `hook_secret` are nullable on `repos` by design. A null `gitlab_url` means the repository has never been pushed to and has no GitLab project yet. Code that reads `gitlab_url` must treat null as "not yet provisioned," not as an error.
- `raw_payload` on `push_events` stores the full GitLab webhook body for auditability. The structured columns (`branch`, `commit_count`, `pusher_name`) are extracted from it at write time.
- `code_hash` uses `sha256(code)` hex-encoded. The plaintext code is generated by the server, returned to the agent exactly once, and never stored.

---

### API Reference

All endpoints accept and return `application/json`. All agent-facing endpoints require HTTPS.

---

#### `POST /register`

Register a new repository. Fails if the triple already exists.

**Request body:**

```json
{
  "owner":   "acme",
  "project": "search",
  "topic":   "rag-v1",
  "pub_key": "<base64url-encoded Ed25519 public key, 32 bytes>"
}
```

**Response — `201 Created`:**

```json
{
  "uuid": "550e8400-e29b-41d4-a716-446655440000",
  "recovery_codes": [
    "rc_a3f7b2c1d4e5",
    "rc_b9c2d1e4f3a0",
    "rc_d1e4f8a0b7c2",
    "rc_f8a0b2c4d1e3",
    "rc_k2m6n1p4q8r0"
  ]
}
```

**Response — `409 Conflict`:**

```json
{ "error": "triple_exists" }
```

**Server behaviour:**

1. Validate that all four fields are present and non-empty.
2. Decode and validate `pub_key` as a 32-byte Ed25519 public key.
3. Attempt INSERT into `repos`. On unique constraint violation, return `409`.
4. Generate 5 recovery codes (16 random bytes each, hex-encoded, prefixed `rc_`).
5. Hash each code with SHA-256 and insert into `recovery_codes`.
6. Return the UUID and plaintext codes. **This is the only time plaintext codes are available.**

---

#### `POST /push-req`

Request a write token for a repository. Authenticated by signed payload.

**Request body:**

```json
{
  "uuid":      "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": 1710678234,
  "signature": "<base64url-encoded Ed25519 signature>"
}
```

The signature is over the UTF-8 bytes of:

```
push:550e8400-e29b-41d4-a716-446655440000:1710678234
```

**Response — `200 OK`:**

```json
{
  "token":      "glpat-xxxxxxxxxxxxxxxxxxxx",
  "gitlab_url": "https://gitlab.example.com/bot/550e8400-e29b-41d4-a716-446655440000",
  "expires_at": "2024-03-17T14:30:00Z"
}
```

**Response — `401 Unauthorized`:**

```json
{ "error": "invalid_signature" }
```

**Response — `404 Not Found`:**

```json
{ "error": "not_found" }
```

**Server behaviour:**

1. Look up the `repos` row by `uuid`. Return `404` if not found.
2. Verify the Ed25519 signature. Return `401` if invalid.
3. Check `|now() - timestamp| <= 300`. Return `401` with `"error": "timestamp_out_of_range"` if outside window.
4. If `gitlab_url` is NULL (first push): call the GitLab Projects API to create the project, register a webhook with a freshly generated `hook_secret`, store both on the `repos` row.
5. Call the GitLab API to mint a `write_repository`-scoped project access token with a 30-minute TTL.
6. Update `repos.last_accessed = now()`.
7. Return the token, URL, and expiry.

---

#### `POST /pull-event`

Request a read token and record pull intent. Authenticated by signed payload. Identical shape to `/push-req` except the signed string uses `pull` as the request type.

**Request body:**

```json
{
  "uuid":      "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": 1710678234,
  "signature": "<base64url-encoded Ed25519 signature>"
}
```

Signature is over:

```
pull:550e8400-e29b-41d4-a716-446655440000:1710678234
```

**Response — `200 OK`:**

```json
{
  "token":      "glpat-xxxxxxxxxxxxxxxxxxxx",
  "gitlab_url": "https://gitlab.example.com/bot/550e8400-e29b-41d4-a716-446655440000",
  "expires_at": "2024-03-17T14:30:00Z"
}
```

**Response — `404 Not Found`:**

```json
{ "error": "not_provisioned" }
```

Returned when `gitlab_url` is NULL — there is nothing to pull yet.

**Server behaviour:**

1. Look up `repos` by `uuid`. Return `404` if not found.
2. Verify signature and timestamp window (same as `/push-req`).
3. If `gitlab_url` is NULL, return `404 not_provisioned`.
4. Write a `pull_events` row (`pulled_at = now()`).
5. Mint a `read_repository`-scoped token with a 30-minute TTL.
6. Update `repos.last_accessed = now()`.
7. Return token, URL, and expiry.

**Important:** The pull event is recorded at token issuance, not at git pull completion. A pull that fails after token issuance is still counted. This is a known limitation of the self-reporting approach.

---

#### `POST /webhook`

Receives push notifications from GitLab. Called by GitLab, not by agents.

**Headers (from GitLab):**

```
X-Gitlab-Token: <per-project hook_secret>
X-Gitlab-Event: Push Hook
Content-Type: application/json
```

**Response:** Always `200 OK`, even on validation failure. Returning `4xx` or `5xx` would trigger GitLab's retry mechanism.

**Server behaviour:**

1. Extract the project path from `project.path_with_namespace` in the payload body. Parse the UUID from the path (the path is the UUID).
2. Look up the `repos` row by UUID. If not found, log and return `200`.
3. Compare `X-Gitlab-Token` against the stored `hook_secret` using constant-time comparison. If invalid, log and return `200` silently — do not leak that validation failed.
4. Extract `ref` (branch), `total_commits_count`, `user_name`, and `push_time` from the payload.
5. Insert a `push_events` row. Store the full payload in `raw_payload`.
6. Update `repos.last_accessed = now()`.

---

#### `POST /recover`

Replace the public key for a repository using a single-use recovery code. Unauthenticated — the agent has no valid private key.

**Request body:**

```json
{
  "uuid":          "550e8400-e29b-41d4-a716-446655440000",
  "recovery_code": "rc_a3f7b2c1d4e5",
  "new_pub_key":   "<base64url-encoded Ed25519 public key>"
}
```

**Response — `200 OK`:**

```json
{ "uuid": "550e8400-e29b-41d4-a716-446655440000" }
```

**Response — `401 Unauthorized`:**

```json
{ "error": "invalid_recovery_code" }
```

Returned for any of: code not found, code already used, UUID mismatch. The response is intentionally uniform — do not distinguish between these cases.

**Server behaviour:**

1. Look up `repos` by `uuid`. If not found, return `401 invalid_recovery_code` (do not leak whether the UUID exists).
2. Hash the submitted `recovery_code` with SHA-256.
3. Look up a matching `recovery_codes` row where `code_hash` matches, `repo_uuid` matches, and `used_at IS NULL`. Return `401` if not found.
4. In a single transaction: set `used_at = now()` on the code row, update `repos.pub_key` with the new key.
5. Return `200`.

---

### Authentication & Signature Verification

All agent-facing endpoints except `/register` and `/recover` require a valid Ed25519 signature.

**Signed payload construction (agent side):**

```
{request_type}:{uuid}:{unix_timestamp_seconds}
```

Examples:

```
push:550e8400-e29b-41d4-a716-446655440000:1710678234
pull:550e8400-e29b-41d4-a716-446655440000:1710678234
```

The payload is UTF-8 encoded before signing. The signature is base64url-encoded (no padding).

**Verification (server side):**

```python
import time
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
import base64

def verify_request(uuid, timestamp, signature_b64, request_type, stored_pub_key_bytes):
    # 1. Timestamp window check
    if abs(time.time() - timestamp) > 300:
        raise AuthError("timestamp_out_of_range")

    # 2. Reconstruct payload
    payload = f"{request_type}:{uuid}:{timestamp}".encode("utf-8")

    # 3. Decode signature
    signature = base64.urlsafe_b64decode(signature_b64 + "==")

    # 4. Verify
    pub_key = Ed25519PublicKey.from_public_bytes(stored_pub_key_bytes)
    try:
        pub_key.verify(signature, payload)
    except InvalidSignature:
        raise AuthError("invalid_signature")
```

The timestamp check must happen before signature verification to avoid unnecessary cryptographic work on replayed requests with valid but expired signatures.

---

### GitLab Integration

The server requires a GitLab bot credential configured at startup:

```
GITLAB_BASE_URL=https://gitlab.example.com
GITLAB_BOT_TOKEN=glpat-xxxxxxxxxxxxxxxxxxxx   # api scope required
GITLAB_NAMESPACE_ID=12345                     # group or user namespace to create projects under
```

**Project creation (on first push-req for a UUID):**

```
POST /api/v4/projects
Authorization: Bearer {GITLAB_BOT_TOKEN}

{
  "name":         "{uuid}",
  "path":         "{uuid}",
  "namespace_id": {GITLAB_NAMESPACE_ID},
  "visibility":   "private",
  "description":  "{owner}/{project}/{topic}"
}
```

The project `path` is the UUID. The `description` is set to the human-readable triple for discoverability in the GitLab UI.

**Webhook registration (immediately after project creation):**

```
POST /api/v4/projects/{project_id}/hooks
Authorization: Bearer {GITLAB_BOT_TOKEN}

{
  "url":         "https://your-meta-server.example.com/webhook",
  "token":       "{hook_secret_hex}",
  "push_events": true,
  "enable_ssl_verification": true
}
```

`hook_secret` is 32 cryptographically random bytes, hex-encoded for the GitLab API, stored as raw bytes in the database.

**Access token minting (on every push-req and pull-event):**

```
POST /api/v4/projects/{project_id}/access_tokens
Authorization: Bearer {GITLAB_BOT_TOKEN}

{
  "name":        "agent-push-{uuid}-{timestamp}",
  "scopes":      ["write_repository"],   // or ["read_repository"] for pulls
  "expires_at":  "{now + 30 minutes, YYYY-MM-DD}"
}
```

Note: GitLab project access tokens use date-only expiry in the API (`YYYY-MM-DD`). The actual expiry is end-of-day UTC on that date, so tokens may live up to ~54 minutes depending on time of day. This is acceptable for the v1 threat model.

---

### Webhook Processing

GitLab sends a `Push Hook` payload when a push lands on any branch. Relevant fields:

```json
{
  "object_kind":    "push",
  "user_name":      "agent-bot",
  "ref":            "refs/heads/main",
  "total_commits_count": 3,
  "push_time":      "2024-03-17T14:01:02Z",
  "project": {
    "path_with_namespace": "bot/550e8400-e29b-41d4-a716-446655440000"
  }
}
```

The UUID is extracted by taking the last path segment of `project.path_with_namespace`. This is reliable because project paths are set to the UUID at creation time and GitLab does not allow path changes that would break this assumption without admin intervention.

---

## Client

### Key Management

The client generates an Ed25519 keypair once, before registration. The private key must be persisted securely and survive process restarts.

```python
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding, PublicFormat, PrivateFormat, NoEncryption
)
import base64

# Generate keypair
private_key = Ed25519PrivateKey.generate()

# Serialise for storage (raw bytes)
private_bytes = private_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
public_bytes  = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)

# Encode public key for transmission
pub_key_b64 = base64.urlsafe_b64encode(public_bytes).rstrip(b"=").decode()
```

The client is responsible for storing:

- `private_key_bytes` — the 32-byte raw private key, ideally in a secrets store or encrypted at rest
- `uuid` — returned at registration
- `recovery_codes` — the five plaintext codes returned at registration; store alongside the private key

If the private key is lost and no recovery codes remain, access to the repository cannot be restored without an admin operation.

---

### Registration

Registration is performed once per `(owner, project, topic)` triple. The client should treat a `409` response as a hard failure — it means another agent already owns that triple.

```python
import requests, json, base64, time

def register(base_url, owner, project, topic, private_key):
    pub_bytes = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    pub_b64   = base64.urlsafe_b64encode(pub_bytes).rstrip(b"=").decode()

    resp = requests.post(f"{base_url}/register", json={
        "owner":   owner,
        "project": project,
        "topic":   topic,
        "pub_key": pub_b64,
    })

    if resp.status_code == 409:
        raise RuntimeError("triple already registered")
    resp.raise_for_status()

    data = resp.json()
    return data["uuid"], data["recovery_codes"]
```

The client must persist the UUID and recovery codes before using the service for any subsequent operation.

---

### Pushing

The client calls `/push-req` to obtain a token, then performs the git push directly against GitLab using that token as the HTTP password.

```python
import time, base64

def sign_payload(private_key, request_type, uuid, timestamp):
    payload = f"{request_type}:{uuid}:{timestamp}".encode("utf-8")
    sig_bytes = private_key.sign(payload)
    return base64.urlsafe_b64encode(sig_bytes).rstrip(b"=").decode()

def request_push_token(base_url, uuid, private_key):
    ts  = int(time.time())
    sig = sign_payload(private_key, "push", uuid, ts)

    resp = requests.post(f"{base_url}/push-req", json={
        "uuid":      uuid,
        "timestamp": ts,
        "signature": sig,
    })
    resp.raise_for_status()
    return resp.json()   # { token, gitlab_url, expires_at }

def push(base_url, uuid, private_key, local_repo_path, branch="main"):
    token_data  = request_push_token(base_url, uuid, private_key)
    gitlab_url  = token_data["gitlab_url"]
    token       = token_data["token"]

    # Inject the token into the remote URL
    from urllib.parse import urlparse, urlunparse
    parsed = urlparse(gitlab_url)
    authed = parsed._replace(netloc=f"oauth2:{token}@{parsed.netloc}")
    remote = urlunparse(authed)

    import subprocess
    subprocess.run(
        ["git", "push", remote, f"HEAD:{branch}"],
        cwd=local_repo_path,
        check=True
    )
```

**Token expiry:** The token is valid for approximately 30 minutes. For large repositories, request a fresh token immediately before the push rather than reusing one obtained earlier in the session.

**First push:** The first push to a new UUID triggers GitLab project creation on the server side. The response time will be slightly higher (~1–3 seconds) than subsequent pushes. This is expected.

---

### Pulling

Pulling mirrors the push flow exactly, using `/pull-event` instead of `/push-req` and `read_repository` scope.

```python
def request_pull_token(base_url, uuid, private_key):
    ts  = int(time.time())
    sig = sign_payload(private_key, "pull", uuid, ts)

    resp = requests.post(f"{base_url}/pull-event", json={
        "uuid":      uuid,
        "timestamp": ts,
        "signature": sig,
    })

    if resp.status_code == 404:
        raise RuntimeError("repository not yet provisioned — no pushes have occurred")
    resp.raise_for_status()
    return resp.json()   # { token, gitlab_url, expires_at }

def pull(base_url, uuid, private_key, local_repo_path, branch="main"):
    token_data = request_pull_token(base_url, uuid, private_key)
    gitlab_url = token_data["gitlab_url"]
    token      = token_data["token"]

    from urllib.parse import urlparse, urlunparse
    parsed = urlparse(gitlab_url)
    authed = parsed._replace(netloc=f"oauth2:{token}@{parsed.netloc}")
    remote = urlunparse(authed)

    import subprocess
    subprocess.run(
        ["git", "fetch", remote, branch],
        cwd=local_repo_path,
        check=True
    )
```

An agent that wants to read a repository it does not own cannot use this service to do so — `/pull-event` requires a valid signature from the key registered against that UUID.

---

### Recovery

If the private key is lost, the agent can recover access using any unused recovery code. After recovery, the old private key is permanently invalidated.

```python
def recover(base_url, uuid, recovery_code, new_private_key):
    pub_bytes = new_private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    pub_b64   = base64.urlsafe_b64encode(pub_bytes).rstrip(b"=").decode()

    resp = requests.post(f"{base_url}/recover", json={
        "uuid":          uuid,
        "recovery_code": recovery_code,
        "new_pub_key":   pub_b64,
    })

    if resp.status_code == 401:
        raise RuntimeError("recovery code invalid or already used")
    resp.raise_for_status()

    # Persist new_private_key immediately
    return resp.json()["uuid"]
```

**After recovery:**

1. Persist the new private key before making any further requests.
2. Update the stored UUID (it remains the same).
3. The remaining recovery codes (if any) are still valid. They are bound to the UUID, not the key.
4. If this was the last recovery code, arrange for admin-level key rotation — there is no self-service path after all codes are exhausted.

---

## Signed Payload Format

| Field | Type | Description |
|---|---|---|
| `request_type` | string | `push` or `pull` |
| `uuid` | string | The repository UUID, lowercase hyphenated |
| `timestamp` | integer | Unix timestamp, seconds since epoch |

Payload string: `{request_type}:{uuid}:{timestamp}`

Encoded as UTF-8 bytes before signing. Signature is raw Ed25519 output (64 bytes), base64url-encoded without padding.

The server rejects any request where `|server_time - timestamp| > 300` seconds. Clients should use a reliable time source. Clock skew beyond 5 minutes will cause valid requests to be rejected.

---

## Error Reference

| Status | `error` value | Meaning |
|---|---|---|
| `400` | `missing_fields` | Required fields absent from request body |
| `400` | `invalid_pub_key` | `pub_key` is not a valid 32-byte Ed25519 public key |
| `401` | `invalid_signature` | Ed25519 signature verification failed |
| `401` | `timestamp_out_of_range` | Timestamp more than 300 seconds from server time |
| `401` | `invalid_recovery_code` | Recovery code not found, already used, or UUID mismatch |
| `404` | `not_found` | UUID does not exist |
| `404` | `not_provisioned` | UUID exists but has no GitLab project (pull before first push) |
| `409` | `triple_exists` | `(owner, project, topic)` already registered |
| `502` | `gitlab_error` | GitLab API call failed during project creation or token minting |

All error responses have the shape `{ "error": "<value>" }`. The `gitlab_error` response may include an additional `"detail"` field with a sanitised GitLab error message.

---

## Security Notes

**Database compromise.** The `repos` table stores only Ed25519 public keys. The `recovery_codes` table stores only SHA-256 hashes of codes. A full database dump contains nothing that can be used to impersonate an agent or forge a signature.

**Replay attacks.** The ±5-minute timestamp window bounds replay. A captured request is useless after 300 seconds. There is no nonce table — the timestamp is the sole replay defence.

**Token scope.** GitLab tokens are scoped to a single project and carry only the permissions needed: `write_repository` for pushes, `read_repository` for pulls. They cannot be used to access other projects or perform administrative actions.

**Webhook forgery.** Each project has a unique `hook_secret`. The `/webhook` endpoint validates `X-Gitlab-Token` using constant-time comparison before processing any payload. Validation failure returns `200` silently to suppress GitLab retries and avoid timing oracles.

**Recovery code handling.** Recovery codes are generated using a cryptographically secure random source. Codes are returned to the client exactly once and never stored in plaintext. The `/recover` endpoint returns the same `401 invalid_recovery_code` for all failure modes (not found, already used, UUID mismatch) to avoid leaking information.

**Bot token handling.** The GitLab bot token should be stored as an environment variable or in a secrets manager, never in source control. It should be scoped to the minimum required namespace and rotated on a regular schedule.

---

## Out of Scope for v1

- **Manifest submission** — agents cannot submit structured metadata about repository contents.
- **Agent-initiated key rotation** — an agent with a valid private key cannot proactively rotate it; rotation requires burning a recovery code.
- **Rate limiting** — no per-UUID or per-IP rate limits on token issuance.
- **Multi-GitLab-instance support** — a single GitLab host is assumed.
- **Pull accuracy** — pull events are recorded at token issuance, not at git pull completion.
- **Admin recovery after exhausted codes** — not documented here; requires direct database intervention.

---

*End of document.*