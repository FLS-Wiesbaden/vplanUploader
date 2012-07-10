from bs4 import BeautifulSoup

class TableParser:
    def __init__(self, raw):
        self.raw = raw

    def getTable(self):
        soup = BeautifulSoup(self.raw)
        table = soup.find('table')
        records = []

        for row in table.findAll('tr'):
            col = row.findAll('td')
            for k,v in enumerate(col):
                cellStr = v.string
                if cellStr is None:
                    col[k] = ''
                elif '\xa0' in cellStr:
                    col[k] = ''
                else:
                    col[k] = str(v.string)
            records.append(col)

        return records

