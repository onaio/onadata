# vim: ai ts=4 sts=4 et sw=4 fileencoding=utf-8
"""
CsvReader class module.
"""
import csv


class CsvReader:
    """
    Typical usage::

        csv_reader = CsvReader(path)
        for d in csv_reader.iter_dicts():
        Variable.objects.create(**d)

    """

    def __init__(self, path):
        self.open(path)

    def open(self, path):
        """Opens a file handle sets a CSV reader."""
        # pylint: disable=consider-using-with,unspecified-encoding
        self._file = open(path, "rU")  # universal new-line mode
        # http://stackoverflow.com/questions/904041/reading-a-utf8-csv-file-wit
        # h-python/904085#904085
        self._csv_reader = csv.reader(self._file)

    def close(self):
        """Closes the file handle."""
        self._file.close()

    def __iter__(self):
        return iter(self)

    def next(self):
        """
        A CsvReader object is iterable (since we have defined __iter__
        and next methods. Each iteration of this object returns a row
        of data.
        """
        row = self._csv_reader.next()
        return list(row)

    def _set_headers(self):
        # pylint: disable=attribute-defined-outside-init
        self._headers = self.next()

    def iter_dicts(self):
        """Iterate over CSV rows as dict items."""
        self._set_headers()
        for row in self:
            result = {}
            for key, value in zip(self._headers, row):
                # note since we're reading this in from a csv file
                # value is going to be a string or unicode string, we
                # quite simply want to avoid including empty strings in our
                # dict.
                if value:
                    result[key] = value
            # we only want to yield rows where there is something in
            # the row.
            if result:
                yield result
        self.close()
