# PyPI Trusted Publisher Setup

The GitHub Actions OIDC publish workflow requires a "trusted publisher" to be
configured on PyPI. Until that is done, the `publish.yml` workflow will fail
with a permission error.

Follow the steps below to configure it.

---

## Option A: Trusted Publisher (OIDC) -- Recommended

### Step 1: Create a PyPI account

1. Go to https://pypi.org/account/register/
2. Register an account (or log in if you already have one).
3. Enable 2FA (required for publishing).

### Step 2: Add a pending trusted publisher

Since the `tz-overlap` package does not exist on PyPI yet, you need to
register it as a **pending publisher**:

1. Go to https://pypi.org/manage/account/publishing/
2. Under **"Add a new pending publisher"**, fill in:

   | Field               | Value                                |
   |---------------------|--------------------------------------|
   | PyPI project name   | `tz-overlap`                         |
   | Owner               | `Majny`                              |
   | Repository name     | `tz-overlap`                         |
   | Workflow name        | `publish.yml`                        |
   | Environment name     | `pypi`                               |

3. Click **"Add"**.

### Step 3: (Optional) Add TestPyPI trusted publisher

Repeat the same on TestPyPI for dry-run publishing:

1. Go to https://test.pypi.org/manage/account/publishing/
2. Fill in the same values, but set **Environment name** to `testpypi`.

### Step 4: Trigger the workflow

1. Go to https://github.com/Majny/tz-overlap/actions/workflows/publish.yml
2. Click **"Run workflow"** (workflow_dispatch).
3. The build will run, and the publish step will use OIDC to authenticate
   with PyPI automatically -- no tokens needed.

---

## Option B: Token-based auth (fallback)

If you cannot or do not want to use OIDC, you can use an API token instead.

1. On PyPI, go to **Account Settings -> API tokens**.
2. Create a token scoped to the `tz-overlap` project (or an unscoped token
   for the first upload).
3. In the GitHub repo, go to **Settings -> Secrets and variables -> Actions**.
4. Add a new repository secret:
   - **Name:** `PYPI_TOKEN`
   - **Value:** the full token string (starts with `pypi-...`).
5. The `publish.yml` workflow will detect the secret and use it as a
   fallback when OIDC is not configured.

---

## Verification

After publishing, the package should appear at:

- **PyPI:** https://pypi.org/project/tz-overlap/
- **TestPyPI:** https://test.pypi.org/project/tz-overlap/

You can install it with:

```bash
pip install tz-overlap
```
