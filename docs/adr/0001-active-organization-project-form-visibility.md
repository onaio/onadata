# ADR 0001: Active organization visibility for project and form APIs

## Status

Proposed

## Area

API / Access control

## Date

2026-07-16

## Context

Project and form API endpoints do not apply active organization filtering
consistently. Public sharing and object permissions should not expose resources
owned by inactive organizations.

Forms need one important distinction: visibility should depend on the form's
project organization, not on the active state of the user who uploaded or
created the form. An uploader can become inactive while the organization remains
active.

Performance was checked separately with `EXPLAIN ANALYZE`. The project list
paths need partial indexes for ordered non-deleted and public non-deleted
queries; the sampled form paths did not require a new form index.

## Decision

Project API visibility requires:

```python
deleted_at__isnull=True,
organization__is_active=True,
```

Form API visibility requires:

```python
deleted_at__isnull=True,
project__organization__is_active=True,
```

The form rule intentionally does not require `XForm.user.is_active`,
`XForm.created_by.is_active`, or any uploader active-state predicate.

This rule applies to API endpoints that return or target projects, forms, or
resources selected through a project or form, including public/shared,
owner-filtered, nested, detail, and permission-filtered paths.

## Consequences

Projects and forms owned by inactive organizations are omitted from list
endpoints and should behave as not found on detail/action endpoints.

Public and authenticated behavior remains otherwise unchanged: public endpoints
still require public sharing, and authenticated endpoints still require the
existing permissions.

The implementation should enforce the rule through the DRF queryset/filter
lifecycle where possible. Any direct project/form lookup or public queryset
union must preserve the same predicate.

Project list performance relies on the partial indexes added for non-deleted and
public non-deleted project ordering. The SQL investigation did not show a need
for a new form index.
