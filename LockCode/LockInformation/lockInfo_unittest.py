# -*- coding: utf-8 -*-

import threading
import time
import queue
import pdbc.trafodion.connector as connector
import unittest
import sys
import os
import re
import traceback

config = {
    'host': '10.10.23.35',
    'port': 23400,
    'tenant_name': 'ESGYNDB',
    'schema': 'lockinfo',
    'user': 'trafodion',
    'password': 'traf123',
    'charset': 'utf-8',
    'use_unicode': True,
    'get_warnings': True,
    'connection_timeout' : 6000
   }


class ExecutionResult:
    pass


class FatalError (Exception):

    def __init__(self, message):
        self.message = message

    def __str__(self):
        self.message


class ExpectationError (AssertionError):

    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg


class QueryTerminal (threading.Thread):

    def __init__(self, auto_commit=True, log_prefix=""):
        super(QueryTerminal, self).__init__()
        try:
            self.connection = connector.connect(**config)
            self.connection.set_auto_commit(auto_commit)
            self.cursor = self.connection.cursor()
            self.stored_result_dict = {}
            self.log_prefix = log_prefix
        except Warning as w:
            print("Connection Warning: ", w)
        except Exception as e:
            print("Connection Exception: ", e.args)
            raise FatalError(e.args)

        # item of queue is a list
        # list idx 0: task type [0 close, 1 execute query, 2 fetch result]
        # list idx 1: task text
        # list idx 2: additional control info [0 nothing]
        self.task_queue = queue.Queue(20)

        # 0 not start, 1 waiting input, 2 executing, 3 down,  4 fatal error
        self.status = 0

        # idx 0: last execution return code, 0 success, 1 warning, 2 error
        # idx 1: last error or warning message if exists
        self.last_execution_result = [0, "", -1]

    def run(self):
        try:

            while True:
                self.status = 1
                query = self.task_queue.get()

                if query[0] == 0:
                    self.status = 3
                    break

                try:
                    if query[0] == 1:
                        self.status = 2
                        self.reset_result()
                        print("%s>>[INFO] SQL> %s" % (self.log_prefix, query[1]))
                        time_start = time.time()
                        self.cursor.execute(query[1])
                        time_end = time.time()
                        print("%s>>[INFO] success after %ss" % (self.log_prefix, round(time_end - time_start, 3)))
                        if not (query[1].startswith("begin") or query[1].startswith("rollback") or query[1].startswith("commit") or query[1].startswith("select")):
                            self.last_execution_result = [0, "operation success", self.cursor.rowcount]
                            print("%s>>[INFO] rowcount: %s" % (self.log_prefix, self.cursor.rowcount))
                        print("")

                    if query[0] == 2 and self.last_execution_result[0] == 0:
                        print("%s>>[INFO] fetch result" % self.log_prefix)
                        time_start = time.time()
                        self.stored_result_dict[query[1]] = self.cursor.fetchall()
                        time_end = time.time()
                        print("%s>>[INFO] success after %ss" % (self.log_prefix, round(time_end - time_start, 3)))
                        print("%s>>[INFO] Fetched result:\n" % self.log_prefix)
                        for row in self.stored_result_dict[query[1]]:
                            print(row)
                        print("%s>>[INFO] rowcount: %s" % (self.log_prefix, self.cursor.rowcount))
                        self.last_execution_result = [0, "operation success", self.cursor.rowcount]
                        print("")

                except connector.Error as e:
                    time_end = time.time()
                    code = self.exception_to_code(e)
                    print("%s>>[ERROR]failed after %ss, Error:[code]%s, [msg]:%s" %
                          (self.log_prefix, round(time_end - time_start, 3), code, e))
                    self.last_execution_result = [self.exception_to_code(e), e, self.cursor.rowcount]

                self.task_queue.task_done()
        except Exception as e:
            sys.stderr.write("%s>>[ERROR] %s" % (self.log_prefix, e))
            traceback.print_exc()
            self.status = 4
            self.task_queue.task_done()
        finally:
            self.cursor.close()
            self.connection.close()

    def close(self):
        self.task_queue.put([0, "shut down", 0])

    def reset_result(self):
        self.last_execution_result = [0, "", -1]

    def store_result(self, name):
        self.stored_result_dict[name] = "not ready"
        self.task_queue.put([2, name, 0])

    def get_result_set(self, name):
        return self.stored_result_dict[name]

    def get_last_execution_result(self):
        ret = ExecutionResult()
        ret.code = abs(self.last_execution_result[0])
        ret.message = self.last_execution_result[1]
        ret.rowcount = self.last_execution_result[2]
        return ret

    def execute(self, query):
        self.task_queue.put([1, query, 0])

    def wait_finish(self):
        self.task_queue.join()
        if self.status == 4:
            raise FatalError(self.log_prefix)

    @staticmethod
    def exception_to_code(e):
        if isinstance(e, connector.Error) or len(e.sqlstate) > 0:
            return 0 - e.errno[0]
        else:
            return -1


class MyTestCase (unittest.TestCase):

    def setUp(self):
        self.fails = []

    def expectEqual(self, first, second, msg=""):
        try:
            self.assertEqual(first, second, msg)
        except AssertionError as e:
            self.fails.append(ExpectationError("%s::%s != %s" % (msg, first, second)))

    def expectNotEqual(self, first, second, msg=""):
        try:
            self.assertNotEqual(first, second, msg)
        except AssertionError as e:
            self.fails.append(ExpectationError("%s::%s == %s" % (msg, first, second)))

    def expectTrue(self, expr, msg=""):
        try:
            self.assertTrue(expr, msg)
        except AssertionError as e:
            self.fails.append(ExpectationError("%s::%s is not True" % (msg, expr)))

    def test_CASE001(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE001:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            case_terminal.execute("begin work")
            case_terminal.wait_finish()
            case_terminal.execute("select employeeno, ename, job  from employee where employeeno=7788")
            case_terminal.store_result("result")
            case_terminal.wait_finish()
            os.system("lockmanage.py")
            case_terminal.execute("commit")
            case_terminal.wait_finish()
            case_terminal.execute("begin work")
            case_terminal.wait_finish()
            case_terminal.execute("select * from employee where employeeno >=7839 and employeeno<=7902")
            case_terminal.store_result("result")
            case_terminal.wait_finish()
            os.system("lockmanage.py")
            case_terminal.execute("commit")
            case_terminal.wait_finish()

            if len(self.fails) > 0:
                self.fail(self.fails)

        except FatalError as fe:
            print("Fatal Error:", fe)
            exit(-1)
        except AssertionError as ae:
            print("Test Case Assertion Error: ", ae.args)
            raise
        except Exception as e:
            print("Test Case Exception: ", e.args)
            raise
        finally:
            for term in terminals:
                term.close()
            for term in terminals:
                term.join()

    def test_CASE002(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE002:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            case_terminal.execute("begin work")
            case_terminal.wait_finish()
            case_terminal.execute("update employee set ename = 'lockinfo' where employeeno = 7788")
            case_terminal.wait_finish()
            os.system("lockmanage.py")
            case_terminal.execute("commit")
            case_terminal.wait_finish()
            case_terminal.execute("begin work")
            case_terminal.wait_finish()
            case_terminal.execute("update employee set ename = 'lockinfo'  where employeeno >=7839 and employeeno<=7902")
            case_terminal.wait_finish()
            os.system("lockmanage.py")
            case_terminal.execute("commit")
            case_terminal.wait_finish()

            if len(self.fails) > 0:
                self.fail(self.fails)

        except FatalError as fe:
            print("Fatal Error:", fe)
            exit(-1)
        except AssertionError as ae:
            print("Test Case Assertion Error: ", ae.args)
            raise
        except Exception as e:
            print("Test Case Exception: ", e.args)
            raise
        finally:
            for term in terminals:
                term.close()
            for term in terminals:
                term.join()

    def test_CASE003(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE003:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            case_terminal.execute("begin work")
            case_terminal.wait_finish()
            case_terminal.execute("select * from employee where employeeno = 7788 for update")
            case_terminal.store_result("result")
            case_terminal.wait_finish()
            os.system("lockmanage.py")
            case_terminal.execute("commit")
            case_terminal.wait_finish()
            case_terminal.execute("begin work")
            case_terminal.wait_finish()
            case_terminal.execute("select * from employee  where employeeno >=7839 and employeeno<=7902 for update")
            case_terminal.store_result("result")
            case_terminal.wait_finish()
            os.system("lockmanage.py")
            case_terminal.execute("commit")
            case_terminal.wait_finish()

            if len(self.fails) > 0:
                self.fail(self.fails)

        except FatalError as fe:
            print("Fatal Error:", fe)
            exit(-1)
        except AssertionError as ae:
            print("Test Case Assertion Error: ", ae.args)
            raise
        except Exception as e:
            print("Test Case Exception: ", e.args)
            raise
        finally:
            for term in terminals:
                term.close()
            for term in terminals:
                term.join()

    def test_CASE004(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE004:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            case_terminal.execute("begin work")
            case_terminal.wait_finish()
            case_terminal.execute("insert into employee values(1234, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)")
            case_terminal.wait_finish()
            os.system("lockmanage.py")
            case_terminal.execute("rollback")
            case_terminal.wait_finish()

            if len(self.fails) > 0:
                self.fail(self.fails)

        except FatalError as fe:
            print("Fatal Error:", fe)
            exit(-1)
        except AssertionError as ae:
            print("Test Case Assertion Error: ", ae.args)
            raise
        except Exception as e:
            print("Test Case Exception: ", e.args)
            raise
        finally:
            for term in terminals:
                term.close()
            for term in terminals:
                term.join()

    def test_CASE005(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE005:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            case_terminal.execute("begin work")
            case_terminal.wait_finish()
            case_terminal.execute(" delete from employee where employeeno = 7369")
            case_terminal.wait_finish()
            os.system("lockmanage.py")
            case_terminal.execute("rollback")
            case_terminal.wait_finish()
            case_terminal.execute("begin work")
            case_terminal.wait_finish()
            case_terminal.execute(" delete from employee where employeeno > 7369")
            case_terminal.wait_finish()
            os.system("lockmanage.py")
            case_terminal.execute("rollback")
            case_terminal.wait_finish()

            if len(self.fails) > 0:
                self.fail(self.fails)

        except FatalError as fe:
            print("Fatal Error:", fe)
            exit(-1)
        except AssertionError as ae:
            print("Test Case Assertion Error: ", ae.args)
            raise
        except Exception as e:
            print("Test Case Exception: ", e.args)
            raise
        finally:
            for term in terminals:
                term.close()
            for term in terminals:
                term.join()

if __name__ == '__main__':
    su = unittest.TestSuite()
    su.addTest(MyTestCase("test_CASE001"))
    su.addTest(MyTestCase("test_CASE002"))
    su.addTest(MyTestCase("test_CASE003"))
    su.addTest(MyTestCase("test_CASE004"))
    su.addTest(MyTestCase("test_CASE005"))
    unittest.TextTestRunner(verbosity=1).run(su)
