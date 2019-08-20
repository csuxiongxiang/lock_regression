import unittest
import pdbc.trafodion.connector as connector
import time

config = {
    'host': '10.10.23.23',
    'port': 23400,
    'tenant_name': 'ESGYNDB',
    'schema': 'S_LOCKPLSQL',
    'user': 'trafodion',
    'password': 'traf123',
    'charset': 'utf-8',
    'use_unicode': True,
    'get_warnings': True
   }

class MyTest (unittest.TestCase):

    def test_select_count(self):
        conx = connector.connect(**config)
        cursor = conx.cursor()
        cursor.execute("begin work;");
        msg = cursor.callproc("""CALL TESTprocdure();""")
        print(msg)
        time.sleep(20)


        cursor.close()
        conx.close()

if __name__ == "__main__":
    unittest.main()