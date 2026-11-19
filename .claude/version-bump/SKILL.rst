version-bump
============

Automates the process of bumping the onadata version and creating a release PR.

This skill checks out main, identifies unreleased PRs since the last tag,
updates version files (CHANGES.rst, onadata/__init__.py, setup.cfg), and
creates a PR.

.. code-block:: bash

   /version-bump [version-type]

Where ``version-type`` can be:

- ``patch`` (default) - Increments patch version (5.13.0 -> 5.13.1)
- ``minor`` - Increments minor version (5.13.0 -> 5.14.0)
- ``major`` - Increments major version (5.13.0 -> 6.0.0)

The workflow:

1. Checkout main and pull latest: ``git checkout main && git pull origin main``
2. Get the last tag: ``git describe --tags --abbrev=0``
3. Get unreleased PRs: ``git log <last-tag>..HEAD --oneline --merges``
4. Determine new version based on version type and current version
5. Create new branch: ``git checkout -b bump-version-to-v<new-version>``
6. Update CHANGES.rst with new version section listing all merged PRs
7. Update ``__version__`` in onadata/__init__.py
8. Update ``version`` in setup.cfg metadata section
9. Commit and push changes
10. Create PR using ``gh pr create``

CHANGES.rst format: PRs listed as ``- Title [@author] PR #<number> <url>``
with only PR creators and co-authors included.
