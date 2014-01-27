from south.db import db


def rename_table_pending_creates(old_name, new_name):
    """Replace app name in db.pending_create_signals to avoid crashing
    out at the end of the migration.
    """
    create_signals = db.get_pending_creates()
    for i in xrange(0, len(create_signals)):
        if create_signals[i][0] == old_name:
            create_signals[i] = (new_name, create_signals[i][1])
