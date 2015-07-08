PostgreSQL

PostgreSQL is the most capable of all the databases here in terms of schema support; the only caveat is that adding columns with default values will cause a full rewrite of the table, for a time proportional to its size.

For this reason, it’s recommended you always create new columns with null=True, as this way they will be added immediately.
