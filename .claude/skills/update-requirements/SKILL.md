---
description: Update pip requirements and Docker base image
---

Updates the Docker base image tag and regenerates
all pinned `.pip` requirement files.

## Usage

```bash
/update-requirements
```

Example: `/update-requirements

## Steps

1. **Create a branch** named
   `chore/update-requirements-<YYYYMMDD>`
   using the date portion of the new tag.

2. **Delete all `.pip` files**:

   ```bash
   rm -f requirements/*.pip
   ```

3. **Regenerate `.pip` files** (order matters):

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

4. **Verify** all 6 `.pip` files exist:
   `ls requirements/*.pip`

5. **Commit** all changed files:
   - `requirements/*.pip`
   - `.claude/skills/update-requirements.md`

6. **Push and create PR** targeting `main`.
