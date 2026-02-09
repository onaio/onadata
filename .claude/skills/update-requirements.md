---
description: Update pip requirements and Docker base image
---

Updates the Docker base image tag and regenerates
all pinned `.pip` requirement files.

## Usage

```bash
/update-requirements <new-docker-image-tag>
```

Example: `/update-requirements 3.10.19-20260205`

## Steps

1. **Read the current tag** from line 1 of
   `docker/onadata-uwsgi/Dockerfile.ubuntu`.

2. **Create a branch** named
   `chore/update-requirements-<YYYYMMDD>`
   using the date portion of the new tag.

3. **Update the Dockerfile** — change only line 1
   image tag from current value to the new tag:

   ```dockerfile
   FROM onaio/python-deps:<new-tag> AS base
   ```

4. **Delete all `.pip` files**:

   ```bash
   rm -f requirements/*.pip
   ```

5. **Regenerate `.pip` files** (order matters):

   ```bash
   # base.pip FIRST (other files depend on it)
   pip-compile \
     --output-file=requirements/base.pip \
     --strip-extras requirements/base.in

   # dev.pip SECOND (includes -r base.in)
   pip-compile \
     --output-file=requirements/dev.pip \
     --strip-extras requirements/dev.in

   # Remaining files (independent)
   pip-compile \
     --output-file=requirements/azure.pip \
     --strip-extras requirements/azure.in
   pip-compile \
     --output-file=requirements/s3.pip \
     --strip-extras requirements/s3.in
   pip-compile \
     --output-file=requirements/ses.pip \
     --strip-extras requirements/ses.in
   pip-compile \
     --output-file=requirements/docs.pip \
     --strip-extras requirements/docs.in
   ```

6. **Verify** all 6 `.pip` files exist:
   `ls requirements/*.pip`

7. **Commit** all changed files:
   - `docker/onadata-uwsgi/Dockerfile.ubuntu`
   - `requirements/*.pip`
   - `.claude/skills/update-requirements.md`

8. **Push and create PR** targeting `main`.
