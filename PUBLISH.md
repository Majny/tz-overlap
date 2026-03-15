# Publishing tz-overlap to PyPI

## Step 1: Register / Log in to PyPI

Go to <https://pypi.org/account/register/> and create an account (or log in).

## Step 2: Create an API Token

1. Go to <https://pypi.org/manage/account/token/>
2. Token name: `tz-overlap` (or anything you like)
3. Scope: **Entire account** (first upload) or **Project: tz-overlap** (subsequent uploads)
4. Click **Create token** and copy the token (starts with `pypi-`)

## Step 3: Publish (one command)

```bash
cd /home/majny/Desktop/MyProjects/tz-overlap
./publish.sh pypi-YOUR_TOKEN_HERE
```

Or using an environment variable:

```bash
export PYPI_TOKEN=pypi-YOUR_TOKEN_HERE
./publish.sh
```

The script will:
- Clean and rebuild the package from source
- Run `twine check` on the built artifacts
- Upload to PyPI
- Verify the package is live at <https://pypi.org/project/tz-overlap/>

## Verification

After publishing, confirm the package is installable:

```bash
pip install tz-overlap
tz-overlap --help
```
