import csv, codecs

class UnicodeReader:
    """A CSV reader which will iterate over lines in the CSV file "f",
    which is encoded in the given encoding.
    """

    def __init__(self, data, dialect=csv.excel, encoding="utf-8", **kwds):
        self.reader = csv.reader(
            self.utf_8_encoder(data), dialect=dialect, **kwds)

    def next(self):
        row = self.reader.next()
        return [unicode(s, "utf-8") for s in row]

    def utf_8_encoder(self, data):
        for line in data:
            yield line.encode('utf-8')

    def __iter__(self):
        return self
