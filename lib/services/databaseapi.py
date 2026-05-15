import pg8000.dbapi # For postgressql database access

class DatabaseAPI():
    def __init__(self, dbname, dbuser, dbpassword, dbhost, dbport, abort_exception, abort_function):
        self.DB = pg8000.dbapi.Connection(
            database=dbname,
            user=dbuser,
            password=dbpassword,
            host=dbhost,
            port=dbport,
            timeout=2
        )
        self.abort_function = abort_function
        self.abort_exception = abort_exception

    def exec_query(self,query):
        cursor = self.DB.cursor() 
        cursor.execute("SET statement_timeout = '1000ms'")
        cursor.execute(query)
        records = []
        while True:
            if self.abort_function ():
                raise self.abort_exception()
            rows = cursor.fetchmany(100)
            if not rows:
                break
            records.extend(rows)
        return records

    def exec_query(self, query):
        cursor = self.DB.cursor()
        try:
            cursor.execute("SET statement_timeout = '1000ms'")
            cursor.execute(query)
            records = []
            while True:
                if self.abort_function():
                    raise self.abort_exception()
                rows = cursor.fetchmany(100)
                if not rows:
                    break
                records.extend(rows)
            return records
        finally:
            try:
                cursor.close()
            except:
                pass

    def close(self):
        try:
            self.DB.close()
        except:
            pass
