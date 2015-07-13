- PostgreSQL
    PostgreSQL is the most capable of all the databases here in terms of schema support; the only caveat is that adding columns with default values will cause a full rewrite of the table, for a time proportional to its size.
    For this reason, it’s recommended you always create new columns with null=True, as this way they will be added immediately.

Might be worthing looking into:
- prefetch_related - https://docs.djangoproject.com/en/1.7/ref/models/querysets/#django.db.models.query.QuerySet.prefetch_related
- custom lookups - https://docs.djangoproject.com/en/1.7/howto/custom-lookups/
- Django Guardian: User.get_all_permissions
