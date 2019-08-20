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
    'host': '10.10.23.23',
    'port': 23400,
    'tenant_name': 'ESGYNDB',
    'schema': 'S_LOCKREGRESSION',
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

    def test_CASE000(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE000:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            case_terminal.execute("drop schema S_LOCKREGRESSION cascade")
            case_terminal.wait_finish()
            temp_var = case_terminal.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            case_terminal.execute("cleanup schema S_LOCKREGRESSION")
            case_terminal.wait_finish()
            case_terminal.execute("create schema  if not exists S_LOCKREGRESSION")
            case_terminal.wait_finish()
            case_terminal.execute("set schema S_LOCKREGRESSION")
            case_terminal.wait_finish()
            case_terminal.execute("drop table dept cascade")
            case_terminal.wait_finish()
            case_terminal.execute("CREATE TABLE dept(deptno DECIMAL(2) not null primary key, dname VARCHAR(14),loc VARCHAR(13))")
            case_terminal.wait_finish()
            case_terminal.execute("showddl dept")
            case_terminal.wait_finish()
            case_terminal.execute("INSERT INTO dept VALUES(10, 'ACCOUNTING', 'NEW YORK')")
            case_terminal.wait_finish()
            case_terminal.execute("INSERT INTO dept VALUES(20, 'RESEARCH', 'DALLAS')")
            case_terminal.wait_finish()
            case_terminal.execute("INSERT INTO dept VALUES(30, 'SALES', 'CHICAGO')")
            case_terminal.wait_finish()
            case_terminal.execute("INSERT INTO dept VALUES(40, 'OPERATIONS', 'BOSTON')")
            case_terminal.wait_finish()
            case_terminal.execute("select * from dept where deptno = 10 for update")
            case_terminal.store_result("result")
            case_terminal.wait_finish()
            temp_var = case_terminal.get_result_set("result")
            t2rs1 = temp_var
            self.expectEqual(t2rs1, ((10,'ACCOUNTING','NEW YORK'),), "expect t2rs1 == ((10,'ACCOUNTING','NEW YORK'),)")
            case_terminal.execute("drop table employee cascade")
            case_terminal.wait_finish()
            case_terminal.execute("""CREATE TABLE employee
   (
    employeeno DECIMAL(4) NOT NULL primary key,
    ename VARCHAR(10),
    job VARCHAR(9),
    mgr DECIMAL(4),
    hiredate DATE,
    sal DECIMAL(7, 2),
    comm DECIMAL(7, 2),
    deptno DECIMAL(2),
    foreign key(deptno) references dept(deptno)
    )
     hbase_options
	(
    data_block_encoding = 'fast_diff',
    compression = 'snappy',
    memstore_flush_size = '1073741824'
	)
""")
            case_terminal.wait_finish()
            case_terminal.execute("INSERT INTO employee VALUES(7369, 'SMITH', 'CLERK', 7902, DATE '1980-12-17', 800, NULL, 20)")
            case_terminal.wait_finish()
            case_terminal.execute("INSERT INTO employee VALUES(7499, 'ALLEN', 'SALESMAN', 7698, DATE '1981-02-20', 1600, 300, 30)")
            case_terminal.wait_finish()
            case_terminal.execute("INSERT INTO employee VALUES(7521, 'WARD', 'SALESMAN', 7698, DATE '1981-02-22', 1250, 500, 30)")
            case_terminal.wait_finish()
            case_terminal.execute("INSERT INTO employee VALUES(7566, 'JONES', 'MANAGER', 7839, DATE '1981-04-02', 2975, NULL, 20)")
            case_terminal.wait_finish()
            case_terminal.execute("INSERT INTO employee VALUES(7654, 'MARTIN', 'SALESMAN', 7698, DATE '1981-09-28', 1250, 1400, 30)")
            case_terminal.wait_finish()
            case_terminal.execute("INSERT INTO employee VALUES(7698, 'BLAKE', 'MANAGER', 7839, DATE '1981-05-01', 2850, NULL, 30)")
            case_terminal.wait_finish()
            case_terminal.execute("INSERT INTO employee VALUES(7782, 'CLARK', 'MANAGER', 7839, DATE '1981-07-09', 2450, NULL, 10)")
            case_terminal.wait_finish()
            case_terminal.execute("INSERT INTO employee VALUES(7788, 'TAC-MD', 'ANALYST', 7566, DATE '1982-12-09', 3000, NULL, 20)")
            case_terminal.wait_finish()
            case_terminal.execute("INSERT INTO employee VALUES(7839, 'KING', 'PRESIDENT', 7788, DATE '1981-11-17', 5000, NULL, 10)")
            case_terminal.wait_finish()
            case_terminal.execute("INSERT INTO employee VALUES(7844, 'TURNER', 'SALESMAN', 7698, DATE '1981-09-08', 1500, 0, 30)")
            case_terminal.wait_finish()
            case_terminal.execute("INSERT INTO employee VALUES(7876, 'ADAMS', 'CLERK', 7788, DATE '1983-01-12', 1100, NULL, 20)")
            case_terminal.wait_finish()
            case_terminal.execute("INSERT INTO employee VALUES(7900, 'JAMES', 'CLERK', 7698, DATE '1981-12-03', 950, NULL, 30)")
            case_terminal.wait_finish()
            case_terminal.execute("INSERT INTO employee VALUES(7902, 'FORD', 'ANALYST', 7566, DATE '1981-12-03', 3000, NULL, 20)")
            case_terminal.wait_finish()
            case_terminal.execute("INSERT INTO employee VALUES(7934, 'MILLER', 'CLERK', 7782, DATE '1982-01-23', 1300, NULL, 10)")
            case_terminal.wait_finish()
            case_terminal.execute("create index employee_index on employee(employeeno)")
            case_terminal.wait_finish()
            case_terminal.execute("select * from employee")
            case_terminal.store_result("result")
            case_terminal.wait_finish()
            case_terminal.execute("drop table salgrade cascade")
            case_terminal.wait_finish()
            case_terminal.execute("""CREATE TABLE salgrade
   (grade DECIMAL primary key,
    losal DECIMAL,
    hisal DECIMAL)""")
            case_terminal.wait_finish()
            case_terminal.execute("showddl salgrade")
            case_terminal.wait_finish()
            case_terminal.execute("INSERT INTO salgrade VALUES(1, 700, 1200)")
            case_terminal.wait_finish()
            case_terminal.execute("INSERT INTO salgrade VALUES(2, 1201, 1400)")
            case_terminal.wait_finish()
            case_terminal.execute("INSERT INTO salgrade VALUES(3, 1401, 2000)")
            case_terminal.wait_finish()
            case_terminal.execute("INSERT INTO salgrade VALUES(4, 2001, 3000)")
            case_terminal.wait_finish()
            case_terminal.execute("INSERT INTO salgrade VALUES(5, 3001, 9999)")
            case_terminal.wait_finish()
            case_terminal.execute("SELECT * FROM salgrade")
            case_terminal.store_result("result")
            case_terminal.wait_finish()
            case_terminal.execute("create table largetable(id int not null primary key, name varchar(20))")
            case_terminal.wait_finish()
            case_terminal.execute("upsert using load into largetable select element, cast('lock' || element as varchar(20)) from udf(series(1,150))")
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

    def test_CASE001(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE001:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE001:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE001:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select employeeno, ename, job  from emp_temp where employeeno=7788")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("drop table emp_temp")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select employeeno, ename, job from emp_temp where employeeno=7788")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs1 = temp_var
            self.expectEqual(t1rs1, t2rs1, "expect t1rs1 == t2rs1")

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
            T1 = QueryTerminal(log_prefix="[test_CASE002:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE002:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select employeeno, ename, job  from emp_temp")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("drop table emp_temp")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select employeeno, ename, job from emp_temp")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs1 = temp_var
            self.expectEqual(t1rs1, t2rs1, "expect t1rs1 == t2rs1")
            T2.execute("commit")
            T2.wait_finish()

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
            T1 = QueryTerminal(log_prefix="[test_CASE003:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE003:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from emp_temp where employeeno >=7839 and employeeno<=7902")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("drop table emp_temp")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno >=7839 and employeeno<=7902")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs1 = temp_var
            self.expectEqual(t1rs1, t2rs1, "expect t1rs1 == t2rs1")
            T2.execute("commit")
            T2.wait_finish()

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
            T1 = QueryTerminal(log_prefix="[test_CASE004:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE004:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp as select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from emp_temp where employeeno = 7788")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("commit")
            T2.wait_finish()

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
            T1 = QueryTerminal(log_prefix="[test_CASE005:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE005:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp as select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from emp_temp")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE006(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE006:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE006:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE006:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp as select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from emp_temp where employeeno >=7566 and employeeno<=7788")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp  for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE007(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE007:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE007:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE007:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table  emp_temp like employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from emp_temp where employeeno = 7788")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE008(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE008:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE008:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE008:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table  emp_temp like employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from emp_temp")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE009(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE009:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE009:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE009:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table  emp_temp like employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from emp_temp where employeeno >=7566 and employeeno<=7788")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp  for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE010(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE010:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE010:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE010:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp as select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select employeeno, ename, job  from emp_temp where employeeno=7788")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from emp_temp where employeeno = 7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("rollback")
            T2.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select employeeno, ename, job  from emp_temp where employeeno=7788")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from emp_temp")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("rollback")
            T2.wait_finish()

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

    def test_CASE011(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE011:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE011:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE011:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp as select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select employeeno, ename, job  from emp_temp")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from emp_temp")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("rollback")
            T2.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select employeeno, ename, job  from emp_temp")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from emp_temp  where employeeno=7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("rollback")
            T2.wait_finish()

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

    def test_CASE012(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE012:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE012:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE012:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp as select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from emp_temp where employeeno >=7839 and employeeno<=7902")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from emp_temp where employeeno >=7839 and employeeno<=7902")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("rollback")
            T2.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from emp_temp where employeeno >=7839 and employeeno<=7902")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from emp_temp")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("rollback")
            T2.wait_finish()

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

    def test_CASE013(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE013:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE013:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE013:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table  emp_temp like employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select employeeno, ename, job  from emp_temp where employeeno=7788")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from emp_temp where employeeno = 7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("rollback")
            T2.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select employeeno, ename, job  from emp_temp where employeeno=7788")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from emp_temp")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("rollback")
            T2.wait_finish()

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

    def test_CASE014(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE014:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE014:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE014:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table  emp_temp like employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select employeeno, ename, job  from emp_temp")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from emp_temp")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("rollback")
            T2.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select employeeno, ename, job  from emp_temp")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from emp_temp  where employeeno=7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("rollback")
            T2.wait_finish()

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

    def test_CASE015(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE015:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE015:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE015:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table  emp_temp like employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from emp_temp where employeeno >=7839 and employeeno<=7902")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from emp_temp where employeeno >=7839 and employeeno<=7902")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("rollback")
            T2.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from emp_temp where employeeno >=7839 and employeeno<=7902")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from emp_temp")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("rollback")
            T2.wait_finish()

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

    def test_CASE016(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE016:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE016:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE016:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp as select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from emp_temp where employeeno = 7788")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T1.execute("select employeeno, ename, job from emp_temp where ename = 'TAC-MD'")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs2 = temp_var
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno = 7788")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs1 = temp_var
            T2.execute("select employeeno, ename, job from emp_temp where ename = 'TAC-MD'")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs2 = temp_var
            self.expectEqual(t1rs1, t2rs1, "expect t1rs1 == t2rs1")
            self.expectEqual(t1rs2, t2rs2, "expect t1rs2 == t2rs2")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE017(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE017:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE017:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE017:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp as select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from emp_temp")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T1.execute("select employeeno, ename, job from emp_temp")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs2 = temp_var
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs1 = temp_var
            T2.execute("select employeeno, ename, job from emp_temp")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs2 = temp_var
            self.expectEqual(t1rs1, t2rs1, "expect t1rs1 == t2rs1")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE018(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE018:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE018:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE018:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp as select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from emp_temp where employeeno >=7566 and employeeno<=7788")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T1.execute("select employeeno, ename,job from emp_temp where employeeno >=7839 and employeeno<=7902")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs2 = temp_var
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno >=7566 and employeeno<=7788")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs1 = temp_var
            T2.execute("select employeeno, ename,job from emp_temp where employeeno >=7839 and employeeno<=7902")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs2 = temp_var
            self.expectEqual(t1rs1, t2rs1, "expect t1rs1 == t2rs1")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE019(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE019:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE019:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE019:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table  emp_temp like employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from emp_temp where employeeno = 7788")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T1.execute("select employeeno, ename, job from emp_temp where ename = 'TAC-MD'")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs2 = temp_var
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno = 7788")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs1 = temp_var
            T2.execute("select employeeno, ename, job from emp_temp where ename = 'TAC-MD'")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs2 = temp_var
            self.expectEqual(t1rs1, t2rs1, "expect t1rs1 == t2rs1")
            self.expectEqual(t1rs2, t2rs2, "expect t1rs2 == t2rs2")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE020(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE020:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE020:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE020:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table  emp_temp like employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from emp_temp")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T1.execute("select employeeno, ename, job from emp_temp")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs2 = temp_var
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs1 = temp_var
            T2.execute("select employeeno, ename, job from emp_temp")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs2 = temp_var
            self.expectEqual(t1rs1, t2rs1, "expect t1rs1 == t2rs1")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE021(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE021:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE021:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE021:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table  emp_temp like employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from emp_temp where employeeno >=7566 and employeeno<=7788")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T1.execute("select employeeno, ename,job from emp_temp where employeeno >=7839 and employeeno<=7902")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs2 = temp_var
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno >=7566 and employeeno<=7788")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs1 = temp_var
            T2.execute("select employeeno, ename,job from emp_temp where employeeno >=7839 and employeeno<=7902")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs2 = temp_var
            self.expectEqual(t1rs1, t2rs1, "expect t1rs1 == t2rs1")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE022(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE022:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE022:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE022:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp as select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("delete from emp_temp where employeeno =7788")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("drop table emp_temp")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE023(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE023:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE023:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE023:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp as select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("delete from emp_temp")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("drop table emp_temp")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE024(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE024:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE024:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE024:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp as select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("delete from emp_temp  where employeeno >=7839 and employeeno<=7902")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("drop table emp_temp")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE025(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE025:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE025:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE025:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("delete from emp_temp where employeeno =7788")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("drop table emp_temp")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE026(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE026:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE026:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE026:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("delete from emp_temp")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("drop table emp_temp")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE027(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE027:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE027:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE027:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("delete from emp_temp  where employeeno >=7839 and employeeno<=7902")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("drop table emp_temp")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE028(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE028:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE028:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE028:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp as select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("delete from emp_temp where employeeno =7788")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from emp_temp where employeeno = 7902")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE029(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE029:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE029:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE029:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("delete from emp_temp where employeeno =7788")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from emp_temp where employeeno = 7902")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE030(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE030:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE030:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE030:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp as select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("delete from emp_temp  where employeeno >=7839 ")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from emp_temp  where employeeno <7839")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE031(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE031:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE031:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE031:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("delete from emp_temp  where employeeno >=7839 ")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from emp_temp  where employeeno <7839")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE032(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE032:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE032:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE032:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp as select * from employee")
            T1.wait_finish()
            T1.execute("select * from emp_temp where employeeno =7902")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("delete from emp_temp where employeeno = 7788")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno =7902")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("select * from emp_temp where employeeno =7902")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs1 = temp_var
            T1.execute("commit")
            T1.wait_finish()
            self.expectEqual(t1rs1, t2rs1, "expect t1rs1 == t2rs1")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE033(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE033:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE033:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE033:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp as select * from employee")
            T1.wait_finish()
            T1.execute("select * from emp_temp where employeeno >=7839")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("delete from emp_temp where employeeno < 7839")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno >=7839")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("select * from emp_temp where employeeno >=7839")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs1 = temp_var
            T1.execute("commit")
            T1.wait_finish()
            self.expectEqual(t1rs1, t2rs1, "expect t1rs1 == t2rs1")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE034(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE034:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE034:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE034:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("select * from emp_temp where employeeno =7902")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("delete from emp_temp where employeeno = 7788")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno =7902")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("select * from emp_temp where employeeno =7902")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs1 = temp_var
            T1.execute("commit")
            T1.wait_finish()
            self.expectEqual(t1rs1, t2rs1, "expect t1rs1 == t2rs1")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE035(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE035:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE035:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE035:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("select * from emp_temp where employeeno >=7839")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("delete from emp_temp where employeeno < 7839")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno >=7839")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("select * from emp_temp where employeeno >=7839")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs1 = temp_var
            T1.execute("commit")
            T1.wait_finish()
            self.expectEqual(t1rs1, t2rs1, "expect t1rs1 == t2rs1")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE036(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE036:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE036:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE036:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp as select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from emp_temp where employeeno = 7788 for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from emp_temp where employeeno =7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("delete from emp_temp")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("delete from emp_temp where employeeno !=7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno = 7788 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs1 = temp_var
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE037(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE037:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE037:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE037:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from emp_temp where employeeno = 7788 for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from emp_temp where employeeno =7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("delete from emp_temp")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("delete from emp_temp where employeeno !=7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno = 7788 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs1 = temp_var
            self.expectEqual(t1rs1, t2rs1, "expect t1rs1 == t2rs1")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE038(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE038:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE038:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE038:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from emp_temp for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("drop table  emp_temp")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs1 = temp_var
            self.expectEqual(t1rs1, t2rs1, "expect t1rs1 == t2rs1")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE039(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE039:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE039:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE039:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp as select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from emp_temp  where employeeno >=7839 and employeeno<=7902 for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from emp_temp where employeeno >=7839 and employeeno<=7902")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("delete from emp_temp where employeeno =7839")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T2.execute("delete from emp_temp")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp  where employeeno >=7839 and employeeno<=7902 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs1 = temp_var
            self.expectEqual(t1rs1, t2rs1, "expect t1rs1 == t2rs1")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE040(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE040:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE040:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE040:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from emp_temp  where employeeno >=7839 and employeeno<=7902 for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from emp_temp where employeeno >=7839 and employeeno<=7902")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("delete from emp_temp where employeeno =7839")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T2.execute("delete from emp_temp")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp  where employeeno >=7839 and employeeno<=7902 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs1 = temp_var
            self.expectEqual(t1rs1, t2rs1, "expect t1rs1 == t2rs1")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE041(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE041:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE041:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE041:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp as select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from emp_temp where employeeno = 7788  for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno =7788 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select employeeno, ename, job from emp_temp  where employeeno = 7902 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select employeeno, ename, job from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno = 7788 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs1 = temp_var
            self.expectEqual(t1rs1, t2rs1, "expect t1rs1 == t2rs1")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE042(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE042:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE042:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE042:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from emp_temp where employeeno = 7788  for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno =7788 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select employeeno, ename, job from emp_temp  where employeeno =7902 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select employeeno, ename, job from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno = 7788 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs1 = temp_var
            self.expectEqual(t1rs1, t2rs1, "expect t1rs1 == t2rs1")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE043(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE043:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE043:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE043:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from emp_temp for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select employeeno, ename, job from emp_temp where employeeno = 7788 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs1 = temp_var
            self.expectEqual(t1rs1, t2rs1, "expect t1rs1 == t2rs1")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE044(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE044:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE044:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE044:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from emp_temp where employeeno >=7839 and employeeno<=7902 for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno >=7839 and employeeno<=7902 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select employeeno, ename, job from emp_temp where employeeno = 7839 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select employeeno, ename, job from emp_temp where employeeno > 7902 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno = 7934 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno >=7839 and employeeno<=7902 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs1 = temp_var
            self.expectEqual(t1rs1, t2rs1, "expect t1rs1 == t2rs1")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE045(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE045:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE045:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE045:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from emp_temp for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from emp_temp")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs1 = temp_var
            self.expectEqual(t1rs1, t2rs1, "expect t1rs1 == t2rs1")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE046(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE046:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE046:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE046:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from emp_temp for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE047(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE047:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE047:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE047:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("select * from emp_temp where employeeno = 7788")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("delete from emp_temp where employeeno =7788")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from emp_temp where employeeno =7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("delete from emp_temp where employeeno = 7902")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("delete from emp_temp where employeeno !=7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("delete from emp_temp")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno = 7788")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs1 = temp_var
            self.expectEqual(t1rs1, t2rs1, "expect t1rs1 == t2rs1")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE048(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE048:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE048:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE048:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp as select * from employee")
            T1.wait_finish()
            T1.execute("select * from emp_temp where employeeno = 7788")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("delete from emp_temp where employeeno =7788")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from emp_temp where employeeno =7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("delete from emp_temp where employeeno = 7902")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("delete from emp_temp where employeeno !=7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("delete from emp_temp")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno = 7788")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs1 = temp_var
            self.expectEqual(t1rs1, t2rs1, "expect t1rs1 == t2rs1")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE049(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE049:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE049:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE049:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("select * from emp_temp")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("delete from emp_temp")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from emp_temp ")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("delete from emp_temp where employeeno =7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs1 = temp_var
            self.expectEqual(t1rs1, t2rs1, "expect t1rs1 == t2rs1")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE050(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE050:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE050:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE050:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp as select * from employee")
            T1.wait_finish()
            T1.execute("select * from emp_temp")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("delete from emp_temp")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from emp_temp ")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("delete from emp_temp where employeeno =7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("select * from emp_temp")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs1 = temp_var
            self.expectEqual(t1rs1, t2rs1, "expect t1rs1 == t2rs1")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE051(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE051:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE051:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE051:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("drop table emp_temp")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("commit")
            T2.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 4082, "expect statusValue.code == 4082")

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

    def test_CASE052(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE052:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE052:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE052:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from emp_temp where employeeno =7788")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T1.execute("delete from emp_temp where employeeno = 7788")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno =7788  for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno = 7902  for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno =7788 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs1 = temp_var
            self.expectEqual(t1rs1, t2rs1, "expect t1rs1 == t2rs1")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE053(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE053:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE053:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE053:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp as select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from emp_temp where employeeno =7788")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T1.execute("delete from emp_temp where employeeno = 7788")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno =7788  for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("select * from emp_temp where employeeno = 7902  for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno =7788 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs1 = temp_var
            self.expectEqual(t1rs1, t2rs1, "expect t1rs1 == t2rs1")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE054(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE054:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE054:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE054:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("select * from emp_temp")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno =7788  for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno = 7902  for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs1 = temp_var
            self.expectEqual(t1rs1, t2rs1, "expect t1rs1 == t2rs1")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE055(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE055:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE055:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE055:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("select * from emp_temp where employeeno >=7839 and employeeno<=7902")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("delete from emp_temp where employeeno >=7839 and employeeno<=7902")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno >=7839 and employeeno<=7902  for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno =7839  for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno =7369 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("select * from emp_temp where employeeno =7788 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno >=7839 and employeeno<=7902 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs1 = temp_var
            self.expectEqual(t1rs1, t2rs1, "expect t1rs1 == t2rs1")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE056(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE056:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE056:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE056:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("select * from emp_temp where employeeno = 7788")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from emp_temp where employeeno =7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("update emp_temp set ename = 'lock' where employeeno =7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno = 7788")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs1 = temp_var
            self.expectEqual(t1rs1, t2rs1, "expect t1rs1 == t2rs1")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE057(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE057:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE057:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE057:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_salgrade")
            T1.wait_finish()
            T1.execute("create table emp_salgrade as select * from salgrade")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("drop table emp_salgrade")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_salgrade")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_salgrade where  grade =1")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE058(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE058:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE058:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE058:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("delete from largetable where id < 102")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("update largetable set name = 'locktest' where id = 102")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("update largetable set name = 'locktest' where id = 102")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE059(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE059:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE059:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE059:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select count(*) from largetable where id < 102")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T1.execute("select count(*) from largetable where id < 102 for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T1.execute("delete from largetable where id < 102")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from largetable where id = 102")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("select * from largetable where id = 100")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs1 = temp_var
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE060(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE060:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE060:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE060:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("update using upsert largetable set name = 'lock' where id < 102")
            T1.wait_finish()
            T1.execute("select count(*) from largetable where id < 102 for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select  * from  largetable where id = 102 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from largetable where id = 100 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE061(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE061:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE061:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE061:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from dept where deptno = 10 for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from dept where deptno = 20 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            T1.execute("select * from dept where deptno = 20 for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from dept where deptno = 10 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs1 = temp_var
            self.expectEqual(t2rs1, ((10,'ACCOUNTING','NEW YORK'),), "expect t2rs1 == ((10,'ACCOUNTING','NEW YORK'),)")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE062(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE062:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE062:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE062:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from employee where employeeno = 7788 for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from dept where deptno =10 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            T2.execute("select * from employee where employeeno = 7788 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("begin work")
            T2.wait_finish()
            T1.execute("select * from dept where deptno =10 for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            self.expectEqual(t1rs1, ((10,'ACCOUNTING','NEW YORK'),), "expect t1rs1 == ((10,'ACCOUNTING','NEW YORK'),)")
            T1.execute("commit")
            T1.wait_finish()

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

    def test_CASE063(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE063:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE063:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE063:T2]")
            T2.start()
            terminals.append(T2)
            T3 = QueryTerminal(log_prefix="[test_CASE063:T3]")
            T3.start()
            terminals.append(T3)
            T4 = QueryTerminal(log_prefix="[test_CASE063:T4]")
            T4.start()
            terminals.append(T4)
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from employee where employeeno = 7788 for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from dept where deptno = 10 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            T3.execute("begin work")
            T3.wait_finish()
            T3.execute("select * from salgrade where grade = 1 for update")
            T3.store_result("scope_term_result")
            T3.wait_finish()
            T4.execute("begin work")
            T4.wait_finish()
            T4.execute("select * from largetable where id = 100 for update")
            T4.store_result("scope_term_result")
            T4.wait_finish()
            T1.execute("select * from dept where deptno = 10 for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("select * from salgrade where grade =1 for update ")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T3.execute("select * from largetable where id = 100 for update")
            T3.store_result("scope_term_result")
            T3.wait_finish()
            temp_var = T3.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T4.execute("select * from employee where employeeno = 7788 for update")
            T4.store_result("scope_term_result")
            T4.wait_finish()
            temp_var = T4.get_result_set("scope_term_result")
            t4rs1 = temp_var
            self.expectEqual(t1rs1, t4rs1, "expect t1rs1 == t4rs1")
            T4.execute("commit")
            T4.wait_finish()

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

    def test_CASE064(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE064:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE064:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE064:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("showddl dept")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("showddl dept")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs1 = temp_var
            self.expectEqual(t1rs1, t2rs1, "expect t1rs1 == t2rs1")
            T2.execute("alter table dept add if not exists column deptno decimal(2,0)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("alter table dept alter dname varchar(15)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("alter table dept add if not exists column deptno decimal(2,0)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE065(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE065:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE065:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE065:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table dept_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table dept_temp like  dept")
            T1.wait_finish()
            T1.execute("insert into dept_temp select * from dept")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("alter table dept_temp add column newcolumnlock varchar(20) default 'testLock'")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("alter table dept_temp add column newcolumnlock varchar(20) default 'testLock'")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("select newcolumnlock from dept_temp")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs1 = temp_var
            self.expectTrue(str("testLock") in str(t2rs1), "expect str(t2rs1) has str(\"testLock\")")
            T2.execute("alter table dept_temp drop column newcolumnlock")
            T2.wait_finish()
            T2.execute("commit")
            T2.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T1.execute("select * from dept_temp")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            self.expectTrue(str("testLock") not in str(t1rs1), "expect str(t1rs1) no str(\"testLock\")")

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

    def test_CASE066(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE066:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE066:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE066:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop index idxsal")
            T1.wait_finish()
            T1.execute("select * from salgrade")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            rs = temp_var
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("create index idxsal on salgrade(GRADE)")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("create index idxsal on salgrade(GRADE)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("drop index idxsal")
            T2.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from salgrade")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("select grade from salgrade where grade = 1")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("set parserflags 1")
            T1.wait_finish()
            T1.execute("select * from table(index_table idxsal)")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE067(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE067:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE067:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE067:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp cascade")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""create table emp(
    employeeno DECIMAL(4) NOT NULL primary key,
    ename VARCHAR(10),
    job VARCHAR(9),
    mgr DECIMAL(4),
    hiredate DATE,
    sal DECIMAL(7, 2),
    comm DECIMAL(7, 2),
    deptno DECIMAL(2)
    ) """)
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""create table emp(
    employeeno DECIMAL(4) NOT NULL primary key,
    ename VARCHAR(10),
    job VARCHAR(9),
    mgr DECIMAL(4),
    hiredate DATE,
    sal DECIMAL(7, 2),
    comm DECIMAL(7, 2),
    deptno DECIMAL(2)
    ) """)
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("drop table emp")
            T2.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from emp")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("commit")
            T2.wait_finish()
            T1.execute("select * from emp")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 4082, "expect statusValue.code == 4082")

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

    def test_CASE068(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE068:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE068:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE068:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop view viewemp")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("create view viewemp as select * from employee where employeeno >= 7839 and employeeno <= 7902")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("create view viewemp as select * from employee where employeeno >= 7839 and employeeno <= 7902")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("drop view viewemp")
            T2.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("drop view viewemp")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")

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

    def test_CASE069(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE069:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE069:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE069:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("invoke dept")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("invoke dept")
            T2.wait_finish()
            T2.execute("alter table dept add if not exists column deptno decimal(2,0)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE070(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE070:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE070:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE070:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop library spj_test cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("create library spj_test file '/opt/trafodion/QALibs/SPJ/test_spj.jar'")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("create library spj_test file '/opt/trafodion/QALibs/SPJ/test_spj.jar'")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("drop library spj_test")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("drop library spj_test")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"LOCK TIMEOUT ERROR\")")

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

    def test_CASE071(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE071:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE071:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE071:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop library spj_test cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create library spj_test file '/opt/trafodion/QALibs/SPJ/test_spj.jar'")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""create procedure numeric_insert(in value numeric(12,4))
external name 'org.trafodion.test.spj.Numeric.insert(java.math.BigDecimal)'
library spj_test
language  java
PARAMETER STYLE JAVA
modifies sql data""")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""create procedure numeric_insert(in value numeric(12,4))
external name 'org.trafodion.test.spj.Numeric.insert(java.math.BigDecimal)'
library spj_test
language  java
PARAMETER STYLE JAVA
modifies sql data""")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("drop procedure numeric_insert")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("drop procedure numeric_insert")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")

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

    def test_CASE072(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE072:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE072:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE072:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop library qa_udf_lib cascade")
            T1.wait_finish()
            T1.execute("create library qa_udf_lib file '/opt/trafodion/QALibs/UDF/qaUdfTest.so'")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""create function qa_udf_char
(INVAL char(50))
returns(c_char char(50))
language c
parameter style sql
external name 'qa_func_char'
library qa_udf_lib
deterministic
state area size 1024
allow any parallelism
no sql""")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""create function qa_udf_char
(INVAL char(50))
returns(c_char char(50))
language c
parameter style sql
external name 'qa_func_char'
library qa_udf_lib
deterministic
state area size 1024
allow any parallelism
no sql""")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("drop function qa_udf_char")
            T2.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("drop function qa_udf_char")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")

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

    def test_CASE073(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE073:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE073:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE073:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop sequence seqlock")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("create sequence seqlock")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("create sequence seqlock")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("drop sequence seqlock")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("drop sequence seqlock")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select seqlock.nextval from dual")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")

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

    def test_CASE074(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE074:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE074:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE074:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop sequence seqlock")
            T1.wait_finish()
            T1.execute("create sequence seqlock")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("alter sequence seqlock increment by 10")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("drop sequence seqlock")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("showddl sequence seqlock")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("select seqlock.nextval from dual")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("drop sequence seqlock")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE075(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE075:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE075:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE075:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table table_comment cascade")
            T1.wait_finish()
            T1.execute("drop view view_comment  cascade")
            T1.wait_finish()
            T1.execute("drop index index_comment  cascade")
            T1.wait_finish()
            T1.execute("drop library qa_udf_lib  cascade")
            T1.wait_finish()
            T1.execute("drop library  spj_test cascade")
            T1.wait_finish()
            T1.execute("drop procedure numeric_insert cascade")
            T1.wait_finish()
            T1.execute("drop function qa_udf_char cascade")
            T1.wait_finish()
            T1.execute("create table table_comment as select * from dept")
            T1.wait_finish()
            T1.execute("create view view_comment as select * from dept where deptno =20")
            T1.wait_finish()
            T1.execute("create index index_comment on table_comment(deptno)")
            T1.wait_finish()
            T1.execute("create library qa_udf_lib file '/opt/trafodion/QALibs/UDF/qaUdfTest.so'")
            T1.wait_finish()
            T1.execute("create library spj_test file '/opt/trafodion/QALibs/SPJ/test_spj.jar'")
            T1.wait_finish()
            T1.execute("""create procedure numeric_insert(in value numeric(12,4))
external name 'org.trafodion.test.spj.Numeric.insert(java.math.BigDecimal)'
library spj_test
language  java
PARAMETER STYLE JAVA
modifies sql data""")
            T1.wait_finish()
            T1.execute("""create function qa_udf_char
(INVAL char(50))
returns(c_char char(50))
language c
parameter style sql
external name 'qa_func_char'
library qa_udf_lib
deterministic
state area size 1024
allow any parallelism
no sql""")
            T1.wait_finish()
            T1.execute("comment on table table_comment is 'table comment x-lock test'")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("comment on table table_comment is 'table comment x-lock test'")
            T1.wait_finish()
            T2.execute("comment on table table_comment is ''")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("comment on table table_comment is ''")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("comment on column table_comment.deptno is 'column comment x-lock test'")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("comment on column table_comment.deptno is 'column comment x-lock test'")
            T1.wait_finish()
            T2.execute("comment on column table_comment.deptno is ''")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("comment on column table_comment.deptno is ''")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("comment on view view_comment is 'view comment x-lock test'")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("comment on view view_comment is 'view comment x-lock test'")
            T1.wait_finish()
            T2.execute("comment on view view_comment is ''")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("comment on view view_comment is ''")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("comment on index index_comment is 'index comment x-lock test'")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("comment on index index_comment is 'index comment x-lock test'")
            T1.wait_finish()
            T2.execute("comment on index index_comment is ''")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("comment on index index_comment is ''")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("comment on library spj_test is 'library comment x-lock test'")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("comment on library spj_test is 'library comment x-lock test'")
            T1.wait_finish()
            T2.execute("comment on library spj_test is ''")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("comment on library spj_test is ''")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("comment on procedure numeric_insert is 'procedure comment x-lock test'")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("comment on procedure numeric_insert is 'procedure comment x-lock test'")
            T1.wait_finish()
            T2.execute("comment on procedure numeric_insert is ''")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("comment on procedure numeric_insert is ''")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("comment on function qa_udf_char is 'function comment x-lock test'")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("comment on function qa_udf_char is 'function comment x-lock test'")
            T1.wait_finish()
            T2.execute("comment on function qa_udf_char is ''")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("comment on function qa_udf_char is ''")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("drop table table_comment cascade")
            T1.wait_finish()
            T1.execute("drop library qa_udf_lib  cascade")
            T1.wait_finish()
            T1.execute("drop library  spj_test cascade")
            T1.wait_finish()

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

    def test_CASE076(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE076:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE076:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE076:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table truncate_table cascade")
            T1.wait_finish()
            T1.execute("create table truncate_table as select * from dept")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("drop table truncate_table")
            T1.wait_finish()
            T2.execute("""truncate table truncate_table""")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("""truncate table truncate_table""")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 4082, "expect statusValue.code == 4082")

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

    def test_CASE077(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE077:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE077:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE077:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table  emp_delete cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_delete like employee")
            T1.wait_finish()
            T1.execute("insert into emp_delete  select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("delete from emp_delete where employeeno = 7788")
            T1.wait_finish()
            T2.execute("delete from emp_delete")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("delete from emp_delete where employeeno = 7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("delete from emp_delete where employeeno = 7369")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("delete from emp_delete where employeeno > 7369 and employeeno <7839")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("delete from emp_delete")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("delete from emp_delete where employeeno != 7788;")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("delete from emp_delete")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE078(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE078:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE078:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE078:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table  emp_delete cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("drop table emp_delete1 cascade")
            T1.wait_finish()
            T1.execute("create table emp_delete like employee")
            T1.wait_finish()
            T1.execute("insert into emp_delete  select * from employee")
            T1.wait_finish()
            T1.execute("create table emp_delete1 like employee")
            T1.wait_finish()
            T1.execute("insert into emp_delete1  select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("delete from emp_delete where employeeno in(select employeeno from emp_delete1 where employeeno >= 7788 ) and deptno in(select deptno from dept where deptno !=10) and job  = 'ANALYST'")
            T1.wait_finish()
            T2.execute("select employeeno from emp_delete1 where employeeno = 7788 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("select deptno from dept where deptno =20 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("delete from emp_delete where  job  = 'ANALYST'")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("delete from emp_delete")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE079(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE079:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE079:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE079:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table  emp_delete cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("drop view emp_view_delete")
            T1.wait_finish()
            T1.execute("create table emp_delete like employee")
            T1.wait_finish()
            T1.execute("insert into emp_delete  select * from employee")
            T1.wait_finish()
            T1.execute("create view emp_view_delete as select * from emp_delete where employeeno >=7839 and employeeno<=7902 ")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("delete from emp_view_delete")
            T1.wait_finish()
            T2.execute("delete from emp_delete where employeeno >=7839 and employeeno<=7902 ")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("delete from emp_delete")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("delete from emp_delete")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE080(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE080:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE080:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE080:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table  emp_delete cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("drop view emp_view_delete")
            T1.wait_finish()
            T1.execute("create table emp_delete like employee")
            T1.wait_finish()
            T1.execute("insert into emp_delete  select * from employee")
            T1.wait_finish()
            T1.execute("create view emp_view_delete as select * from emp_delete where employeeno >=7839 and employeeno<=7902 ")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("delete from emp_delete")
            T1.wait_finish()
            T2.execute("delete from emp_view_delete")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("delete from emp_delete")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE081(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE081:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE081:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE081:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table  emp_delete cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("drop view emp_view_delete")
            T1.wait_finish()
            T1.execute("create table emp_delete like employee")
            T1.wait_finish()
            T1.execute("insert into emp_delete select * from employee")
            T1.wait_finish()
            T1.execute("create view emp_view_delete as select * from emp_delete where employeeno >=7839 and employeeno<=7902 ")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("delete from emp_view_delete")
            T1.wait_finish()
            T2.execute("delete from emp_delete where employeeno <7839")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("delete from emp_delete where employeeno > 7902")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("delete from emp_delete")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE082(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE082:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE082:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE082:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table  emp_delete cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("drop view emp_view_delete")
            T1.wait_finish()
            T1.execute("create table emp_delete like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_delete select * from employee")
            T1.wait_finish()
            T1.execute("create view emp_view_delete as select * from emp_delete where employeeno >=7839 and employeeno<=7902 ")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("delete from emp_delete where employeeno <7839")
            T1.wait_finish()
            T2.execute("delete from emp_view_delete where employeeno >=7839")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("delete from emp_view_delete")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("delete from emp_delete")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE083(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE083:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE083:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE083:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table  emp_delete cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("drop view emp_view_delete")
            T1.wait_finish()
            T1.execute("create table emp_delete like employee")
            T1.wait_finish()
            T1.execute("insert into emp_delete  select * from employee")
            T1.wait_finish()
            T1.execute("create view emp_view_delete as select * from emp_delete where employeeno >=7839 and employeeno<=7902 ")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("delete from emp_view_delete")
            T1.wait_finish()
            T2.execute("delete from emp_delete where employeeno <7839")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("delete from emp_delete where employeeno > 7902")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("delete from emp_delete")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE084(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE084:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE084:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE084:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table  emp_delete cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("drop view emp_view_delete")
            T1.wait_finish()
            T1.execute("create table emp_delete like employee")
            T1.wait_finish()
            T1.execute("insert into emp_delete  select * from employee")
            T1.wait_finish()
            T1.execute("create view emp_view_delete as select * from emp_delete where employeeno >=7839 and employeeno<=7902 ")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("delete from emp_delete where employeeno <7839")
            T1.wait_finish()
            T2.execute("delete from emp_view_delete where employeeno >=7839")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("delete from emp_view_delete")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("delete from emp_delete")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE085(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE085:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE085:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE085:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table  emp_insert cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("""create table emp_insert(
    employeeno DECIMAL(4) NOT NULL primary key,
    ename VARCHAR(10),
    job VARCHAR(9),
    mgr DECIMAL(4),
    hiredate DATE,
    sal DECIMAL(7, 2),
    comm DECIMAL(7, 2),
    deptno DECIMAL(2))""")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("insert into emp_insert values(0428, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("insert into emp_insert values(0428, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("insert into emp_insert values(0623, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_insert")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("commit")
            T2.wait_finish()
            T2.execute("insert into emp_insert values(0428, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 8102, "expect statusValue.code == 8102")

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

    def test_CASE086(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE086:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE086:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE086:T2]")
            T2.start()
            terminals.append(T2)
            T1 = QueryTerminal(log_prefix="[test_CASE086:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE086:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table  emp_insert cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("""create table emp_insert(
employeeno DECIMAL(4) NOT NULL unique,
ename VARCHAR(10),
job VARCHAR(9),
mgr DECIMAL(4),
hiredate DATE,
sal DECIMAL(7, 2),
comm DECIMAL(7, 2),
deptno DECIMAL(2))""")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("insert into emp_insert values(0428, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("insert into emp_insert values(0428, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("insert into emp_insert values(0623, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("insert into emp_insert values(0428, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE087(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE087:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE087:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE087:T2]")
            T2.start()
            terminals.append(T2)
            T1 = QueryTerminal(log_prefix="[test_CASE087:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE087:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table  emp_insert cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("""create table emp_insert(
employeeno DECIMAL(4),
ename VARCHAR(10),
job VARCHAR(9),
mgr DECIMAL(4),
hiredate DATE,
sal DECIMAL(7, 2),
comm DECIMAL(7, 2),
deptno DECIMAL(2),
foreign key(deptno) references dept(deptno))""")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("insert into emp_insert values(0428, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("insert into emp_insert values(0428, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from dept where deptno =10 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("insert into emp_insert values(0428, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE088(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE088:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE088:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE088:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table  emp_insert cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_insert like employee")
            T1.wait_finish()
            T1.execute("insert into emp_insert select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("insert into emp_insert values(0428, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from emp_insert where employeeno = 0428")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("delete from emp_insert where employeeno = 0428")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE089(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE089:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE089:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE089:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table  emp_insert cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_insert like employee")
            T1.wait_finish()
            T1.execute("insert into emp_insert select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("insert into emp_insert values(0428, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from emp_insert")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()

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

    def test_CASE090(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE090:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE090:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE090:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_insert cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_insert like employee")
            T1.wait_finish()
            T1.execute("insert into emp_insert select * from employee where employeeno >=7839 and employeeno<=7902")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("insert into emp_insert select * from employee where employeeno < 7839 and employeeno > 7902")
            T1.wait_finish()
            T2.execute("select * from employee where employeeno = 7369 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("select * from employee where employeeno = 7934 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()

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

    def test_CASE091(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE091:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE091:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE091:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table  emp_merge cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("""create table emp_merge(
employeeno DECIMAL(4) NOT NULL primary key,
ename VARCHAR(10),
job VARCHAR(9),
mgr DECIMAL(4),
hiredate DATE,
sal DECIMAL(7, 2),
comm DECIMAL(7, 2),
deptno DECIMAL(2))""")
            T1.wait_finish()
            T1.execute("insert into emp_merge select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("merge into emp_merge on employeeno = '7788' when matched then update set ename = 'xxx'")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_merge where employeeno = 7788 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_merge where employeeno = 7788 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE092(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE092:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE092:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE092:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table  emp_merge cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("""create table emp_merge(
employeeno DECIMAL(4) NOT NULL primary key,
ename VARCHAR(10),
job VARCHAR(9),
mgr DECIMAL(4),
hiredate DATE,
sal DECIMAL(7, 2),
comm DECIMAL(7, 2),
deptno DECIMAL(2))""")
            T1.wait_finish()
            T1.execute("insert into emp_merge select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("merge into emp_merge on employeeno = '7788' when matched then delete")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_merge where employeeno = 7788 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_merge where employeeno = 7369 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("select * from emp_merge where employeeno = 7788 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE093(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE093:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE093:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE093:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table  emp_merge cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("""create table emp_merge(
employeeno DECIMAL(4) NOT NULL primary key,
ename VARCHAR(10),
job VARCHAR(9),
mgr DECIMAL(4),
hiredate DATE,
sal DECIMAL(7, 2),
comm DECIMAL(7, 2),
deptno DECIMAL(2))""")
            T1.wait_finish()
            T1.execute("insert into emp_merge select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""merge into emp_merge on employeeno = '2345' when matched then update set ename ='xx'
	when not matched then insert VALUES(2345, 'testlock', 'CLERK', 7782, DATE '1982-01-23', 1300, NULL, 10)""")
            T1.wait_finish()
            T2.execute("insert into emp_merge VALUES(2345, 'testlock', 'CLERK', 7782, DATE '1982-01-23', 1300, NULL, 10)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("insert into emp_merge VALUES(2345, 'testlock', 'CLERK', 7782, DATE '1982-01-23', 1300, NULL, 10)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 8102, "expect statusValue.code == 8102")

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

    def test_CASE094(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE094:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE094:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE094:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table  emp_merge cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("""create table emp_merge(
employeeno DECIMAL(4) NOT NULL primary key,
ename VARCHAR(10),
job VARCHAR(9),
mgr DECIMAL(4),
hiredate DATE,
sal DECIMAL(7, 2),
comm DECIMAL(7, 2),
deptno DECIMAL(2))""")
            T1.wait_finish()
            T1.execute("insert into emp_merge select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""merge into emp_merge on employeeno = '2345' when matched then delete
	when not matched then insert VALUES(2345, 'testlock', 'CLERK', 7782, DATE '1982-01-23', 1300, NULL, 10)""")
            T1.wait_finish()
            T2.execute("insert into emp_merge VALUES(2345, 'testlock', 'CLERK', 7782, DATE '1982-01-23', 1300, NULL, 10)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            T1.execute("commit")
            T1.wait_finish()

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

    def test_CASE095(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE095:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE095:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE095:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table  emp_merge cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("""create table emp_merge(
employeeno DECIMAL(4) NOT NULL primary key,
ename VARCHAR(10),
job VARCHAR(9),
mgr DECIMAL(4),
hiredate DATE,
sal DECIMAL(7, 2),
comm DECIMAL(7, 2),
deptno DECIMAL(2))""")
            T1.wait_finish()
            T1.execute("insert into emp_merge select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""merge into emp_merge using(select employeeno,ename from employee where employeeno >=7839 and employeeno<=7902) x on employeeno = x.employeeno when matched then update set ename = x.ename """)
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select employeeno,ename from emp_merge where employeeno =7839  for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select employeeno,ename from employee where employeeno =7369 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("select employeeno,ename from emp_merge where employeeno =7839  for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE096(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE096:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE096:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE096:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table  emp_merge cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("""create table emp_merge(
employeeno DECIMAL(4) NOT NULL primary key,
ename VARCHAR(10),
job VARCHAR(9),
mgr DECIMAL(4),
hiredate DATE,
sal DECIMAL(7, 2),
comm DECIMAL(7, 2),
deptno DECIMAL(2))""")
            T1.wait_finish()
            T1.execute("insert into emp_merge select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""merge into emp_merge using(select employeeno,ename from employee where employeeno >=7839 and employeeno<=7902) x on employeeno = x.employeeno when matched then delete""")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select employeeno,ename from emp_merge where employeeno =7839  for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select employeeno,ename from employee where employeeno =7369 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("select employeeno,ename from emp_merge where employeeno =7839  for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE097(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE097:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE097:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE097:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table  emp_merge cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("""create table emp_merge(
employeeno DECIMAL(4) NOT NULL primary key,
ename VARCHAR(10),
job VARCHAR(9),
mgr DECIMAL(4),
hiredate DATE,
sal DECIMAL(7, 2),
comm DECIMAL(7, 2),
deptno DECIMAL(2))""")
            T1.wait_finish()
            T1.execute("insert into emp_merge select * from employee where employeeno >=7839 and employeeno<=7902")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""merge into emp_merge using(select employeeno,ename from employee where employeeno < 7839 or employeeno > 7902 limit 1) x on employeeno = x.employeeno when matched then update set ename = x.ename when not matched then insert VALUES(2345, 'testlock', 'CLERK', 7782, DATE '1982-01-23', 1300, NULL, 10)""")
            T1.wait_finish()
            T1.execute("select * from emp_merge where employeeno =2345")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            rs1 = temp_var
            T2.execute("insert into emp_merge VALUES(2345, 'testlock', 'CLERK', 7782, DATE '1982-01-23', 1300, NULL, 10)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("insert into emp_merge VALUES(2345, 'testlock', 'CLERK', 7782, DATE '1982-01-23', 1300, NULL, 10)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 8102, "expect statusValue.code == 8102")

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

    def test_CASE098(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE098:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE098:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE098:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table  emp_merge cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("""create table emp_merge(
employeeno DECIMAL(4) NOT NULL primary key,
ename VARCHAR(10),
job VARCHAR(9),
mgr DECIMAL(4),
hiredate DATE,
sal DECIMAL(7, 2),
comm DECIMAL(7, 2),
deptno DECIMAL(2))""")
            T1.wait_finish()
            T1.execute("insert into emp_merge select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""merge into emp_merge using(select employeeno,ename from employee where employeeno < 7839 or employeeno > 7902) x on employeeno = x.employeeno when matched then delete when not matched then insert VALUES(2345, 'testlock', 'CLERK', 7782, DATE '1982-01-23', 1300, NULL, 10)""")
            T1.wait_finish()
            T2.execute("insert into emp_merge VALUES(2345, 'testlock', 'CLERK', 7782, DATE '1982-01-23', 1300, NULL, 10)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("insert into emp_merge VALUES(2345, 'testlock', 'CLERK', 7782, DATE '1982-01-23', 1300, NULL, 10)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 8102, "expect statusValue.code == 8102")

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

    def test_CASE099(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE099:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE099:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE099:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table  emp_update cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("""create table emp_update(
employeeno DECIMAL(4) NOT NULL primary key,
ename VARCHAR(10),
job VARCHAR(9),
mgr DECIMAL(4),
hiredate DATE,
sal DECIMAL(7, 2),
comm DECIMAL(7, 2),
deptno DECIMAL(2))""")
            T1.wait_finish()
            T1.execute("insert into emp_update select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""update emp_update set ename = 'testlock' where employeeno = 7369""")
            T1.wait_finish()
            T2.execute("update emp_update set ename = 'testlock' where employeeno = 7369")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("update emp_update set ename = 'testlock' where employeeno = 7499")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("update emp_update set ename = 'testlock' where employeeno >7369")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("update emp_update set ename = 'testlock' where employeeno !=7369")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("update emp_update set ename = 'testlock' where employeeno = 7369")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE100(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE100:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE100:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE100:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table  emp_update cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("""create table emp_update(
employeeno DECIMAL(4) NOT NULL unique,
ename VARCHAR(10),
job VARCHAR(9),
mgr DECIMAL(4),
hiredate DATE,
sal DECIMAL(7, 2),
comm DECIMAL(7, 2),
deptno DECIMAL(2))""")
            T1.wait_finish()
            T1.execute("insert into emp_update select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""update emp_update set ename = 'testlock' where employeeno = 7369""")
            T1.wait_finish()
            T2.execute("update emp_update set ename = 'testlock' where employeeno = 7369")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("update emp_update set ename = 'testlock' where employeeno = 7499")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("update emp_update set ename = 'testlock' where employeeno >7369")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("update emp_update set ename = 'testlock' where employeeno !=7369")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("update emp_update set ename = 'testlock' where employeeno = 7369")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE101(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE101:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE101:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE101:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table  emp_update cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("""create table emp_update(
employeeno DECIMAL(4),
ename VARCHAR(10),
job VARCHAR(9),
mgr DECIMAL(4),
hiredate DATE,
sal DECIMAL(7, 2),
comm DECIMAL(7, 2),
deptno DECIMAL(2))""")
            T1.wait_finish()
            T1.execute("insert into emp_update select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""update emp_update set ename = 'testlock' where employeeno = 7369""")
            T1.wait_finish()
            T2.execute("update emp_update set ename = 'testlock' where employeeno = 7369")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T2.execute("update emp_update set ename = 'testlock' where employeeno != 7369")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()

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

    def test_CASE102(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE102:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE102:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE102:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table  emp_update cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_update like employee")
            T1.wait_finish()
            T1.execute("insert into emp_update select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""update emp_update set ename = '1234' where employeeno = 7788""")
            T1.wait_finish()
            T2.execute("update emp_update set employeeno = 1234 where ename = 'TAC-MD'")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("delete from emp_update where ename = 'TAC-MD'")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("update emp_update set employeeno = 1234 where ename = 'TAC-MD'")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE103(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE103:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE103:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE103:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table  emp_update cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_update like employee")
            T1.wait_finish()
            T1.execute("insert into emp_update select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""update emp_update set employeeno = 1234 where employeeno = 7788""")
            T1.wait_finish()
            T2.execute("update emp_update set employeeno = 1234")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("delete from emp_update")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("delete from emp_update")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE104(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE104:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE104:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE104:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table  emp_update cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_update like employee")
            T1.wait_finish()
            T1.execute("insert into emp_update select * from employee")
            T1.wait_finish()
            T1.execute("""create view emp_view_update as select * from emp_update""")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""update emp_update set sal = 1234 where employeeno = 7788""")
            T1.wait_finish()
            T2.execute("update emp_view_update set sal = 1234 where employeeno = 7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("delete from emp_view_update where employeeno = 7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("update emp_view_update set sal = 1234 where employeeno = 7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE105(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE105:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE105:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE105:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table  emp_update cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_update like employee")
            T1.wait_finish()
            T1.execute("insert into emp_update select * from employee")
            T1.wait_finish()
            T1.execute("""create view emp_view_update as select * from emp_update""")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""update emp_view_update set sal = 1234 where employeeno = 7788""")
            T1.wait_finish()
            T2.execute("update emp_update set sal = 1234 where employeeno = 7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("delete from emp_update where employeeno = 7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("update emp_update set sal = 1234 where employeeno = 7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE106(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE106:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE106:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE106:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table  emp_update cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_update like employee")
            T1.wait_finish()
            T1.execute("insert into emp_update select * from employee")
            T1.wait_finish()
            T1.execute("""create view emp_view_update as select * from emp_update""")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""update emp_view_update set sal = 1234 where employeeno = 7788""")
            T1.wait_finish()
            T2.execute("update emp_update set sal = 1234 where employeeno = 7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("delete from emp_update where employeeno = 7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("update emp_update set sal = 1234 where employeeno = 7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE107(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE107:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE107:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE107:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table  emp_update cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_update like employee")
            T1.wait_finish()
            T1.execute("insert into emp_update select * from employee")
            T1.wait_finish()
            T1.execute("""create view emp_view_update as select * from emp_update""")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""update emp_view_update set sal = 1234 where employeeno = 7788""")
            T1.wait_finish()
            T2.execute("update emp_update set sal = 1234 where employeeno !=7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("delete from emp_update where employeeno !=7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("update emp_update set sal = 1234 where employeeno !=7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE108(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE108:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE108:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE108:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table t0 cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table t0(a int not null primary key, b int, c int)")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("upsert into t0 values(1,2,2)")
            T1.wait_finish()
            T2.execute("upsert into t0 values(1,3,3)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("upsert into t0 values(1,3,3)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE109(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE109:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE109:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE109:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table t0 cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table t0(a int not null unique, b int, c int)")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("upsert into t0 values(1,2,2)")
            T1.wait_finish()
            T2.execute("upsert into t0 values(1,3,3)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("upsert into t0 values(1,3,3)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 8102, "expect statusValue.code == 8102")

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

    def test_CASE110(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE110:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE110:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE110:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table t0 cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table t0(a int, b int, c int)")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("upsert into t0 values(1,2,2)")
            T1.wait_finish()
            T2.execute("upsert into t0 values(1,3,3)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("upsert into t0 values(1,3,3)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE111(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE111:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE111:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE111:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table t0 cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table t0(a int primary key, b int, c int)")
            T1.wait_finish()
            T1.execute("upsert into t0 values(1,2,2)")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("upsert into t0 values(1,3,3)")
            T1.wait_finish()
            T2.execute("delete from t0 where a =1")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("delete from t0 where a =1")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE112(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE112:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE112:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE112:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table t0 cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table t0(a int primary key, b int, c int)")
            T1.wait_finish()
            T1.execute("upsert into t0 values(1,2,2)")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("upsert into t0 values(1,3,3)")
            T1.wait_finish()
            T2.execute("delete from t0")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("delete from t0")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE113(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE113:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE113:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE113:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table t0 cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("drop table t1 cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table t0(a int primary key, b int, c int)")
            T1.wait_finish()
            T1.execute("create table t1(a int primary key, b int, c int)")
            T1.wait_finish()
            T1.execute("upsert into t0 values(1,2,2)")
            T1.wait_finish()
            T1.execute("upsert into t1 values(2,2,4)")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("upsert into t0 select * from t1")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from t1 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("delete from t0")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE114(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE114:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE114:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE114:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table t0 cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("drop view t0_view")
            T1.wait_finish()
            T1.execute("create table t0(a int primary key, b int, c int)")
            T1.wait_finish()
            T1.execute("create view  t0_view as select * from t0 where a <= 3")
            T1.wait_finish()
            T1.execute("upsert into t0 values(1,2,2)")
            T1.wait_finish()
            T1.execute("upsert into t0 values(2,2,2)")
            T1.wait_finish()
            T1.execute("upsert into t0 values(3,2,4)")
            T1.wait_finish()
            T1.execute("upsert into t0 values(4,2,2)")
            T1.wait_finish()
            T1.execute("upsert into t0 values(5,2,4)")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("upsert into t0 values(1,3,2)")
            T1.wait_finish()
            T2.execute("delete from t0_view where a =1 ")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("upsert into t0_view values(1,2,2) ")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("upsert into t0_view values(1,2,2) ")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE115(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE115:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE115:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE115:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table t0 cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("drop view t0_view")
            T1.wait_finish()
            T1.execute("create table t0(a int primary key, b int, c int)")
            T1.wait_finish()
            T1.execute("create view  t0_view as select * from t0 where a <= 3")
            T1.wait_finish()
            T1.execute("upsert into t0 values(1,2,2)")
            T1.wait_finish()
            T1.execute("upsert into t0 values(2,2,2)")
            T1.wait_finish()
            T1.execute("upsert into t0 values(3,2,4)")
            T1.wait_finish()
            T1.execute("upsert into t0 values(4,2,2)")
            T1.wait_finish()
            T1.execute("upsert into t0 values(5,2,4)")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("upsert into t0 values(1,3,2)")
            T1.wait_finish()
            T2.execute("delete from t0_view where a =1 ")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("upsert into t0_view values(1,2,2) ")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("upsert into t0_view values(1,2,2) ")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE116(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE116:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE116:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE116:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table t0 cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("drop view t0_view")
            T1.wait_finish()
            T1.execute("create table t0(a int primary key, b int, c int)")
            T1.wait_finish()
            T1.execute("create view  t0_view as select * from t0 where a <= 3")
            T1.wait_finish()
            T1.execute("upsert into t0 values(1,2,2)")
            T1.wait_finish()
            T1.execute("upsert into t0 values(2,2,2)")
            T1.wait_finish()
            T1.execute("upsert into t0 values(3,2,4)")
            T1.wait_finish()
            T1.execute("upsert into t0 values(4,2,2)")
            T1.wait_finish()
            T1.execute("upsert into t0 values(5,2,4)")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("upsert into t0 values(1,3,2)")
            T1.wait_finish()
            T2.execute("delete from t0_view where a =2")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("upsert into t0_view values(2,2,2)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()

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

    def test_CASE117(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE117:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE117:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE117:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table t0 cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("drop view t0_view")
            T1.wait_finish()
            T1.execute("create table t0(a int primary key, b int, c int)")
            T1.wait_finish()
            T1.execute("create view  t0_view as select * from t0 where a <= 3")
            T1.wait_finish()
            T1.execute("upsert into t0 values(1,2,2)")
            T1.wait_finish()
            T1.execute("upsert into t0 values(2,2,2)")
            T1.wait_finish()
            T1.execute("upsert into t0 values(3,2,4)")
            T1.wait_finish()
            T1.execute("upsert into t0 values(4,2,2)")
            T1.wait_finish()
            T1.execute("upsert into t0 values(5,2,4)")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("upsert into t0_view values(1,3,2)")
            T1.wait_finish()
            T2.execute("delete from t0 where a =2")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("upsert into t0 values(2,2,2) ")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()

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

    def test_CASE118(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE118:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE118:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE118:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table t0 cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table t0(a int primary key, b int, c int)")
            T1.wait_finish()
            T1.execute("upsert into t0 values(1,2,2)")
            T1.wait_finish()
            T1.execute("upsert into t0 values(2,2,2)")
            T1.wait_finish()
            T1.execute("upsert into t0 values(3,2,4)")
            T1.wait_finish()
            T1.execute("upsert into t0 values(4,2,2)")
            T1.wait_finish()
            T1.execute("upsert into t0 values(5,2,4)")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("update using upsert  t0 set b =2 where a=2")
            T1.wait_finish()
            T2.execute("update using upsert  t0 set b =2 where a=2")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("delete from t0 where a=2 ")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("delete from t0 where a=2 ")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE119(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE119:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE119:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE119:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop library spj_test cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("drop table SPJ_NUMERIC cascade")
            T1.wait_finish()
            T1.execute("create library spj_test file '/opt/trafodion/QALibs/SPJ/test_spj.jar'")
            T1.wait_finish()
            T1.execute("drop procedure numeric_insert cascade ")
            T1.wait_finish()
            T1.execute("""create procedure numeric_insert(in value numeric(12,4))
external name 'org.trafodion.test.spj.Numeric.insert(java.math.BigDecimal)'
library spj_test
language  java
PARAMETER STYLE JAVA
modifies sql data""")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("call numeric_insert(1)")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("call numeric_insert(1)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 11220, "expect statusValue.code == 11220")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("showddl procedure numeric_insert")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("drop procedure numeric_insert")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE120(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE120:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE120:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE120:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_partition")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("""CREATE TABLE emp_partition
   (
    employeeno DECIMAL(4) NOT NULL primary key
    )
	salt using 2 partitions on(employeeno)
	""")
            T1.wait_finish()
            T1.execute("INSERT INTO emp_partition VALUES(1)")
            T1.wait_finish()
            T1.execute("INSERT INTO emp_partition VALUES(0623)")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from emp_partition")
            T2.wait_finish()
            T1.execute("delete from emp_partition where employeeno = 1")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("rollback")
            T2.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from emp_partition where employeeno = 1")
            T2.wait_finish()
            T1.execute("delete from emp_partition where employeeno = 1")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("rollback")
            T2.wait_finish()

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

    def test_CASE121(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE121:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE121:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE121:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop sequence seqlock")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create sequence seqlock")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select seqlock.nextval from dual")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select seqlock.nextval from dual")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select seqlock.currval from dual")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select seqlock.currval from dual")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select seqlock.currval from dual")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("select seqlock.nextval from dual")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE122(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE122:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE122:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE122:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("create index idx_scan on emp_temp(employeeno)")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select employeeno from emp_temp where employeeno =7839")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("set parserflags 1")
            T2.wait_finish()
            T2.execute("select * from table(index_table idx_scan) for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select employeeno from emp_temp where employeeno =7839 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("select * from table(index_table idx_scan) for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE123(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE123:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE123:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE123:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("""create table emp_temp
(
    employeeno DECIMAL(4),
    ename VARCHAR(10),
    job VARCHAR(9),
    mgr DECIMAL(4),
    hiredate DATE,
    sal DECIMAL(7, 2),
    comm DECIMAL(7, 2),
    deptno DECIMAL(2),
    primary key(employeeno, deptno)
    )
""")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("create index idx_emp on emp_temp(employeeno)")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select employeeno from emp_temp where deptno =7839")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select employeeno from emp_temp where deptno =7839")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs1 = temp_var
            self.expectEqual(t1rs1, t2rs1, "expect t1rs1 == t2rs1")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE124(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE124:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE124:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE124:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("create index idx_scan on emp_temp(employeeno)")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select employeeno from emp_temp a, emp_temp b where a.employeeno =b.employeeno and a.employeeno = 7788")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select employeeno from emp_temp a, emp_temp b where a.employeeno =b.employeeno and a.employeeno = 7788")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs1 = temp_var
            self.expectEqual(t1rs1, t2rs1, "expect t1rs1 == t2rs1")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE125(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE125:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE125:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE125:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("create index idx_scan on emp_temp(employeeno)")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select employeeno from emp_temp a, emp_temp b where a.employeeno =b.employeeno and a.employeeno = 7788")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select employeeno from emp_temp a, emp_temp b where a.employeeno =b.employeeno and a.employeeno = 7788")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs1 = temp_var
            self.expectEqual(t1rs1, t2rs1, "expect t1rs1 == t2rs1")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE126(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE126:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE126:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE126:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("create index idx_scan on emp_temp(employeeno)")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from emp_temp union  select employeeno from emp_temp where employeeno = 7788")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp union  select employeeno from emp_temp where employeeno = 7788")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_result_set("scope_term_result")
            t2rs1 = temp_var
            self.expectEqual(t1rs1, t2rs1, "expect t1rs1 == t2rs1")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE127(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE127:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE127:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE127:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""select distinct(EMPLOYEENO)  from
 (select * from (select employeeno,ename from EMPLOYEE a
 right join (select * from dept) b on a.deptno = b.deptno
 where a.deptno =10 order by a.employeeno) union all
  select * from (select employeeno,ename from EMPLOYEE a right join
   (select * from dept) b on a.deptno = b.deptno where a.deptno =10  order by a.employeeno)) c group by c.EMPLOYEENO;""")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t1rs1 = temp_var
            T2.execute("begin work")
            T2.wait_finish()
            T1.execute("""select distinct(EMPLOYEENO)  from
 (select * from (select employeeno,ename from EMPLOYEE a
 right join (select * from dept) b on a.deptno = b.deptno
 where a.deptno =10 order by a.employeeno) union all
  select * from (select employeeno,ename from EMPLOYEE a right join
   (select * from dept) b on a.deptno = b.deptno where a.deptno =10  order by a.employeeno)) c group by c.EMPLOYEENO;""")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_result_set("scope_term_result")
            t2rs1 = temp_var
            self.expectEqual(t1rs1, t2rs1, "expect t1rs1 == t2rs1")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE128(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE128:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE128:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE128:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table  emp_composite_pk cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("""create table emp_composite_pk(
    employeeno DECIMAL(4),
    ename VARCHAR(10),
    job VARCHAR(9),
    mgr DECIMAL(4),
    hiredate DATE,
    sal DECIMAL(7, 2),
    comm DECIMAL(7, 2),
    deptno DECIMAL(2),
    primary key(employeeno,deptno)
    )""")
            T1.wait_finish()
            T1.execute("insert into emp_composite_pk select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("update emp_composite_pk set deptno = 50 where employeeno = 7369")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("update emp_composite_pk set deptno = 50 where employeeno = 7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("update emp_composite_pk set deptno = 50 where employeeno = 7369")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("insert into emp_composite_pk values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 60)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("update emp_composite_pk set deptno = 50 where employeeno = 7369 and deptno = 20")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE129(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE129:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE129:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE129:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table  emp_composite_unique cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("""create table emp_composite_unique(
    employeeno DECIMAL(4),
    ename VARCHAR(10),
    job VARCHAR(9),
    mgr DECIMAL(4),
    hiredate DATE,
    sal DECIMAL(7, 2),
    comm DECIMAL(7, 2),
    deptno DECIMAL(2),
    unique(employeeno,deptno)
    )""")
            T1.wait_finish()
            T1.execute("insert into emp_composite_unique select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("update emp_composite_unique set deptno = 50 where employeeno = 7369")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("update emp_composite_unique set deptno = 50 where employeeno = 7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("update emp_composite_unique set deptno = 50 where employeeno = 7369")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("insert into emp_composite_unique values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 60)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("update emp_composite_unique set deptno = 50 where employeeno = 7369 and deptno =20")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE130(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE130:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE130:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE130:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table  emp_check cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("""create table emp_check(
    employeeno DECIMAL(4),
    ename VARCHAR(10),
    job VARCHAR(9),
    mgr DECIMAL(4),
    hiredate DATE,
    sal DECIMAL(7, 2),
    comm DECIMAL(7, 2),
    deptno DECIMAL(2) check(deptno >= 10)
    )""")
            T1.wait_finish()
            T1.execute("insert into emp_check select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("update emp_check set deptno = 50 where employeeno = 7369")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("update emp_check set deptno = 50 where employeeno = 7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("update emp_check set deptno = 9 where employeeno = 7369")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            self.expectTrue(str("ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("insert into emp_check values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 60)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("update emp_check set deptno = 50 where employeeno = 7369")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE131(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE131:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE131:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE131:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table  emp_fk cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("drop table  dept_fk cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("""create table dept_fk like dept""")
            T1.wait_finish()
            T1.execute("""insert into dept_fk select * from dept""")
            T1.wait_finish()
            T1.execute("""create table emp_fk(
    employeeno DECIMAL(4),
    ename VARCHAR(10),
    job VARCHAR(9),
    mgr DECIMAL(4),
    hiredate DATE,
    sal DECIMAL(7, 2),
    comm DECIMAL(7, 2),
    deptno DECIMAL(2) references dept_fk(deptno)
    )""")
            T1.wait_finish()
            T1.execute("insert into emp_fk select * from employee where deptno >10")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("delete from dept_fk where deptno =10")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("insert into emp_fk values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T2.execute("update emp_fk set deptno = 10")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T2.execute("delete from emp_fk where deptno = 10")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("insert into emp_fk values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 20)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("commit")
            T2.wait_finish()
            T2.execute("insert into emp_fk values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE132(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE132:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE132:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE132:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table  emp_fk cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("drop table  dept_fk cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("""create table dept_fk like dept""")
            T1.wait_finish()
            T1.execute("""insert into dept_fk select * from dept""")
            T1.wait_finish()
            T1.execute("""create table emp_fk(
    employeeno DECIMAL(4),
    ename VARCHAR(10),
    job VARCHAR(9),
    mgr DECIMAL(4),
    hiredate DATE,
    sal DECIMAL(7, 2),
    comm DECIMAL(7, 2),
    deptno DECIMAL(2) references dept_fk(deptno)
    )""")
            T1.wait_finish()
            T1.execute("insert into emp_fk select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("INSERT INTO dept_fk VALUES(50, 'ACCOUNTING', 'NEW YORK'); ")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("insert into emp_fk values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 50)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 8103, "expect statusValue.code == 8103")
            T2.execute("update emp_fk set deptno = 50")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 8103, "expect statusValue.code == 8103")
            T2.execute("delete from emp_fk where deptno = 50")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("insert into emp_fk values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 30)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("insert into emp_fk values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 50)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE133(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE133:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE133:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE133:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table  emp_fk cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("drop table  dept_fk cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("""create table dept_fk like dept""")
            T1.wait_finish()
            T1.execute("""insert into dept_fk select * from dept""")
            T1.wait_finish()
            T1.execute("""create table emp_fk(
    employeeno DECIMAL(4),
    ename VARCHAR(10),
    job VARCHAR(9),
    mgr DECIMAL(4),
    hiredate DATE,
    sal DECIMAL(7, 2),
    comm DECIMAL(7, 2),
    deptno DECIMAL(2) references dept_fk(deptno)
    )""")
            T1.wait_finish()
            T1.execute("insert into emp_fk select * from employee where deptno > 10")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("update dept_fk set deptno = 50 where deptno = 10 ")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("insert into emp_fk values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T2.execute("update emp_fk set deptno = 10")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T2.execute("delete from emp_fk where deptno = 10")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("insert into emp_fk values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 50)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("insert into emp_fk values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE134(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE134:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE134:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE134:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table  emp_fk cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("drop table  dept_fk cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("""create table dept_fk like dept""")
            T1.wait_finish()
            T1.execute("""insert into dept_fk select * from dept""")
            T1.wait_finish()
            T1.execute("""create table emp_fk(
    employeeno DECIMAL(4),
    ename VARCHAR(10),
    job VARCHAR(9),
    mgr DECIMAL(4),
    hiredate DATE,
    sal DECIMAL(7, 2),
    comm DECIMAL(7, 2),
    deptno DECIMAL(2) references dept_fk(deptno)
    )""")
            T1.wait_finish()
            T1.execute("insert into emp_fk select * from employee where deptno > 10")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from dept_fk where  deptno = 10 for update ")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("insert into emp_fk values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T2.execute("update emp_fk set deptno = 10")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T2.execute("delete from emp_fk where deptno = 10")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("insert into emp_fk values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 20)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("insert into emp_fk values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE135(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE135:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE135:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE135:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table  emp_fk cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("drop table  dept_fk cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("""create table dept_fk like dept""")
            T1.wait_finish()
            T1.execute("""insert into dept_fk select * from dept""")
            T1.wait_finish()
            T1.execute("""create table emp_fk(
    employeeno DECIMAL(4),
    ename VARCHAR(10),
    job VARCHAR(9),
    mgr DECIMAL(4),
    hiredate DATE,
    sal DECIMAL(7, 2),
    comm DECIMAL(7, 2),
    deptno DECIMAL(2) references dept_fk(deptno)
    )""")
            T1.wait_finish()
            T1.execute("insert into emp_fk select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("insert into emp_fk values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10) ")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from dept_fk where  deptno = 10 for update ")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T2.execute("delete from dept_fk where deptno = 10 ")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T2.execute("update dept_fk set dname ='RESEARCH' where deptno = 10 ")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T2.execute("insert into emp_fk values(7890, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("insert into emp_fk values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE136(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE136:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE136:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE136:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table  emp_fk cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("drop table  dept_fk cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("""create table dept_fk like dept""")
            T1.wait_finish()
            T1.execute("""insert into dept_fk select * from dept""")
            T1.wait_finish()
            T1.execute("""create table emp_fk(
    employeeno DECIMAL(4),
    ename VARCHAR(10),
    job VARCHAR(9),
    mgr DECIMAL(4),
    hiredate DATE,
    sal DECIMAL(7, 2),
    comm DECIMAL(7, 2),
    deptno DECIMAL(2) references dept_fk(deptno)
    )""")
            T1.wait_finish()
            T1.execute("insert into emp_fk select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("update emp_fk set deptno = 20 where deptno = 10")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from dept_fk where  deptno = 10 for update ")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T2.execute("delete from dept_fk where deptno = 20 ")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T2.execute("update dept_fk set dname = 'RESEARCH' where deptno = 10 ")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T2.execute("insert into emp_fk values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 20)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("insert into emp_fk values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("insert into emp_fk values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE137(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE137:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE137:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE137:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table  emp_fk cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("drop table  dept_fk cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("""create table dept_fk like dept""")
            T1.wait_finish()
            T1.execute("""insert into dept_fk select * from dept""")
            T1.wait_finish()
            T1.execute("""create table emp_fk(
    employeeno DECIMAL(4),
    ename VARCHAR(10),
    job VARCHAR(9),
    mgr DECIMAL(4),
    hiredate DATE,
    sal DECIMAL(7, 2),
    comm DECIMAL(7, 2),
    deptno DECIMAL(2) references dept_fk(deptno)
    )""")
            T1.wait_finish()
            T1.execute("insert into emp_fk select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("delete from emp_fk where deptno = 10")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from dept_fk where  deptno = 10 for update ")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("delete from dept_fk where deptno = 10 ")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("update dept_fk set dname = 'RESEARCH' where deptno = 10 ")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("insert into emp_fk values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("insert into emp_fk values(7890, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("rollback")
            T2.wait_finish()
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("insert into emp_fk values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("rollback")
            T2.wait_finish()
            T1.execute("rollback")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from emp_fk where deptno = 10 for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from dept_fk where deptno = 10 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            T2.execute("rollback")
            T2.wait_finish()
            T1.execute("rollback")
            T1.wait_finish()

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

    def test_CASE138(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE138:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE138:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE138:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("cqd traf_savepoints 'on'")
            T1.wait_finish()
            T2.execute("cqd traf_savepoints 'on'")
            T2.wait_finish()
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("begin savepoint")
            T1.wait_finish()
            T1.execute("select * from emp_temp")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("rollback savepoint")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()

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

    def test_CASE139(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE139:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE139:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE139:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("cqd traf_savepoints 'on'")
            T1.wait_finish()
            T2.execute("cqd traf_savepoints 'on'")
            T2.wait_finish()
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("begin savepoint")
            T1.wait_finish()
            T1.execute("select * from emp_temp")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("commit savepoint")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE140(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE140:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE140:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE140:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("cqd traf_savepoints 'on'")
            T1.wait_finish()
            T2.execute("cqd traf_savepoints 'on'")
            T2.wait_finish()
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("begin savepoint")
            T1.wait_finish()
            T1.execute("delete from emp_temp where employeeno = '7788'")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("rollback savepoint")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()

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

    def test_CASE141(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE141:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE141:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE141:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("cqd traf_savepoints 'on'")
            T1.wait_finish()
            T2.execute("cqd traf_savepoints 'on'")
            T2.wait_finish()
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("begin savepoint")
            T1.wait_finish()
            T1.execute("delete from emp_temp where employeeno = '7788'")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("commit savepoint")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE142(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE142:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE142:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE142:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("cqd traf_savepoints 'on'")
            T1.wait_finish()
            T2.execute("cqd traf_savepoints 'on'")
            T2.wait_finish()
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("begin savepoint")
            T1.wait_finish()
            T1.execute("select * from emp_temp where employeeno = '7788' for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno = '7788' for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("rollback savepoint")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno = '7788' for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()

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

    def test_CASE143(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE143:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE143:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE143:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("cqd traf_savepoints 'on'")
            T1.wait_finish()
            T2.execute("cqd traf_savepoints 'on'")
            T2.wait_finish()
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("begin savepoint")
            T1.wait_finish()
            T1.execute("select * from emp_temp where employeeno = '7788' for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno = '7788' for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("commit savepoint")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno = '7788' for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno = '7788' for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE144(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE144:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE144:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE144:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("cqd traf_savepoints 'on'")
            T1.wait_finish()
            T2.execute("cqd traf_savepoints 'on'")
            T2.wait_finish()
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("begin savepoint")
            T1.wait_finish()
            T1.execute("delete from emp_temp where employeeno = '7788'")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from emp_temp where employeeno = '7788'")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("rollback savepoint")
            T1.wait_finish()
            T2.execute("delete from emp_temp where employeeno = '7788'")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()

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

    def test_CASE145(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE145:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE145:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE145:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("cqd traf_savepoints 'on'")
            T1.wait_finish()
            T2.execute("cqd traf_savepoints 'on'")
            T2.wait_finish()
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("begin savepoint")
            T1.wait_finish()
            T1.execute("delete from emp_temp where employeeno = '7788'")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from emp_temp where employeeno = '7788'")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("commit savepoint")
            T1.wait_finish()
            T2.execute("delete from emp_temp where employeeno = '7788'")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("delete from emp_temp where employeeno = '7788'")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE146(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE146:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE146:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE146:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("cqd traf_savepoints 'on'")
            T1.wait_finish()
            T2.execute("cqd traf_savepoints 'on'")
            T2.wait_finish()
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("begin savepoint")
            T1.wait_finish()
            T1.execute("select * from emp_temp for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from emp_temp where employeeno = '7788'")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("rollback savepoint")
            T1.wait_finish()
            T2.execute("delete from emp_temp where employeeno = '7788'")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()

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

    def test_CASE147(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE147:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE147:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE147:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("cqd traf_savepoints 'on'")
            T1.wait_finish()
            T2.execute("cqd traf_savepoints 'on'")
            T2.wait_finish()
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("begin savepoint")
            T1.wait_finish()
            T1.execute("select * from emp_temp for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from emp_temp where employeeno = '7788'")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("commit savepoint")
            T1.wait_finish()
            T2.execute("delete from emp_temp where employeeno = '7788'")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("delete from emp_temp where employeeno = '7788'")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")

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

    def test_CASE148(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE148:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE148:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE148:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("cqd traf_savepoints 'on'")
            T1.wait_finish()
            T2.execute("cqd traf_savepoints 'on'")
            T2.wait_finish()
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from emp_temp")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T1.execute("begin savepoint")
            T1.wait_finish()
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("drop table emp_temp")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE149(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE149:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE149:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE149:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("cqd traf_savepoints 'on'")
            T1.wait_finish()
            T2.execute("cqd traf_savepoints 'on'")
            T2.wait_finish()
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("delete from emp_temp where employeeno=7788")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T1.execute("begin savepoint")
            T1.wait_finish()
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("drop table emp_temp")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE150(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE150:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE150:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE150:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("cqd traf_savepoints 'on'")
            T1.wait_finish()
            T2.execute("cqd traf_savepoints 'on'")
            T2.wait_finish()
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("delete from emp_temp where employeeno=7788")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T1.execute("begin savepoint")
            T1.wait_finish()
            T2.execute("delete from emp_temp where employeeno=7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from emp_temp where employeeno=7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE151(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE151:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE151:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE151:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("cqd traf_savepoints 'on'")
            T1.wait_finish()
            T2.execute("cqd traf_savepoints 'on'")
            T2.wait_finish()
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from emp_temp for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T1.execute("begin savepoint")
            T1.wait_finish()
            T2.execute("delete from emp_temp where employeeno=7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from emp_temp where employeeno=7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE152(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE152:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE152:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE152:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("cqd traf_savepoints 'on'")
            T1.wait_finish()
            T2.execute("cqd traf_savepoints 'on'")
            T2.wait_finish()
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from emp_temp where employeeno =7788 for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T1.execute("begin savepoint")
            T1.wait_finish()
            T2.execute("select * from emp_temp where employeeno =7788 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno =7788 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE153(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE153:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE153:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE153:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("cqd traf_savepoints 'on'")
            T1.wait_finish()
            T2.execute("cqd traf_savepoints 'on'")
            T2.wait_finish()
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("begin savepoint")
            T1.wait_finish()
            T1.execute("select * from emp_temp")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("begin savepoint")
            T2.wait_finish()
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("rollback savepoint")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("begin savepoint")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno =7788 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE154(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE154:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE154:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE154:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("cqd traf_savepoints 'on'")
            T1.wait_finish()
            T2.execute("cqd traf_savepoints 'on'")
            T2.wait_finish()
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("begin savepoint")
            T1.wait_finish()
            T1.execute("update emp_temp set sal = 7800 where employeeno = 7788 ")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("begin savepoint")
            T2.wait_finish()
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("rollback savepoint")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("begin savepoint")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno =7788 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE155(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE155:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE155:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE155:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("cqd traf_savepoints 'on'")
            T1.wait_finish()
            T2.execute("cqd traf_savepoints 'on'")
            T2.wait_finish()
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("begin savepoint")
            T1.wait_finish()
            T1.execute("update emp_temp set sal = 7800 where employeeno = 7788 ")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("begin savepoint")
            T2.wait_finish()
            T2.execute("update emp_temp set sal = 7800 where employeeno = 7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("rollback savepoint")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("begin savepoint")
            T2.wait_finish()
            T2.execute("update emp_temp set sal = 7800 where employeeno = 7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE156(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE156:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE156:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE156:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("cqd traf_savepoints 'on'")
            T1.wait_finish()
            T2.execute("cqd traf_savepoints 'on'")
            T2.wait_finish()
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("begin savepoint")
            T1.wait_finish()
            T1.execute("select * from emp_temp for update ")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("begin savepoint")
            T2.wait_finish()
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("rollback savepoint")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("begin savepoint")
            T2.wait_finish()
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE157(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE157:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE157:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE157:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("cqd traf_savepoints 'on'")
            T1.wait_finish()
            T2.execute("cqd traf_savepoints 'on'")
            T2.wait_finish()
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("begin savepoint")
            T1.wait_finish()
            T1.execute("select * from emp_temp where employeeno =7788 for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("begin savepoint")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno =7788 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("rollback savepoint")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("begin savepoint")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno =7788 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE158(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE158:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE158:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE158:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("cqd traf_savepoints 'on'")
            T1.wait_finish()
            T2.execute("cqd traf_savepoints 'on'")
            T2.wait_finish()
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("begin savepoint")
            T1.wait_finish()
            T1.execute("update emp_temp set sal = 7800 where employeeno = 7788")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("begin savepoint")
            T2.wait_finish()
            T2.execute("update emp_temp set sal = 7800 where employeeno = 7792")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("update emp_temp set sal = 7000 where employeeno=7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("update emp_temp set sal = 7800 where employeeno = 7792")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("rollback savepoint")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("begin savepoint")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno =7788 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE159(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE159:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE159:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE159:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("cqd traf_savepoints 'on'")
            T1.wait_finish()
            T2.execute("cqd traf_savepoints 'on'")
            T2.wait_finish()
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("drop table emp_temp1 cascade")
            T1.wait_finish()
            T1.execute("create table emp_temp1 like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp1 select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("begin savepoint")
            T1.wait_finish()
            T1.execute("update emp_temp set sal = 7800 where employeeno = 7788")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("begin savepoint")
            T2.wait_finish()
            T2.execute("delete from emp_temp1 where employeeno = 7792")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("update emp_temp set sal = 7000 where employeeno=7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("delete from emp_temp1 where employeeno = 7792")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("rollback savepoint")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("begin savepoint")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno =7788 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE160(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE160:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE160:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE160:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("cqd traf_savepoints 'on'")
            T1.wait_finish()
            T2.execute("cqd traf_savepoints 'on'")
            T2.wait_finish()
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("begin savepoint")
            T1.wait_finish()
            T1.execute("select * from emp_temp where employeeno =7788 for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("begin savepoint")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno =7788 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("rollback savepoint")
            T1.wait_finish()
            T1.execute("begin savepoint")
            T1.wait_finish()
            T1.execute("select * from emp_temp where employeeno =7788 for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("begin savepoint")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno =7788 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("rollback savepoint")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("begin savepoint")
            T2.wait_finish()
            T2.execute("select * from emp_temp where employeeno =7788 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE161(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE161:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE161:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE161:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("cqd traf_savepoints 'on'")
            T1.wait_finish()
            T2.execute("cqd traf_savepoints 'on'")
            T2.wait_finish()
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("begin savepoint")
            T1.wait_finish()
            T1.execute("update emp_temp set sal = 7000 where employeeno=7788")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("begin savepoint")
            T2.wait_finish()
            T2.execute("update emp_temp set sal = 7000 where employeeno=7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("rollback savepoint")
            T1.wait_finish()
            T1.execute("begin savepoint")
            T1.wait_finish()
            T1.execute("update emp_temp set sal = 7800 where employeeno = 7788")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("begin savepoint")
            T2.wait_finish()
            T2.execute("update emp_temp set sal = 7800 where employeeno = 7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("rollback savepoint")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("begin savepoint")
            T2.wait_finish()
            T2.execute("update emp_temp set sal = 7000 where employeeno=7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE162(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE162:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE162:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE162:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from emp_temp")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("delete from employee where employeeno =7788 ")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("select * from emp_temp  where employeeno = 7902 for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("select * from emp_temp for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE163(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE163:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE163:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE163:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_temp cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_temp like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_temp select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("begin savepoint")
            T1.wait_finish()
            T1.execute("select * from emp_temp")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("begin savepoint")
            T2.wait_finish()
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("delete from employee where employeeno =7788 ")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("begin savepoint")
            T2.wait_finish()
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T2.execute("begin work")
            T2.wait_finish()
            T1.execute("select * from emp_temp  where employeeno = 7902 for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("begin savepoint")
            T2.wait_finish()
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T2.execute("begin work")
            T2.wait_finish()
            T1.execute("select * from emp_temp for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("begin savepoint")
            T2.wait_finish()
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("rollback savepoint")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("begin savepoint")
            T2.wait_finish()
            T2.execute("select * from emp_temp for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_Case164(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_Case164:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_Case164:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_Case164:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table test_tb cascade")
            T1.wait_finish()
            T1.execute("create table  test_tb(a int primary key)")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("insert into test_tb values (1);")
            T1.wait_finish()
            T1.execute("insert into test_tb values (2);")
            T1.wait_finish()
            T1.execute("begin savepoint")
            T1.wait_finish()
            T1.execute("insert into test_tb values(3);")
            T1.wait_finish()
            T1.execute("rollback savepoint;")
            T1.wait_finish()
            T1.execute("insert into test_tb values(3);")
            T1.wait_finish()
            T1.execute("rollback savepoint;")
            T1.wait_finish()
            T1.execute("insert into test_tb values(3);")
            T1.wait_finish()
            T2.execute("insert into test_tb  values(3);")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("rollback savepoint;")
            T1.wait_finish()
            T1.execute("insert into test_tb values(3);")
            T1.wait_finish()
            T1.execute("rollback savepoint;")
            T1.wait_finish()
            T1.execute("insert into test_tb values(3);")
            T1.wait_finish()
            T1.execute("rollback savepoint;")
            T1.wait_finish()
            T1.execute("insert into test_tb values(3);")
            T1.wait_finish()
            T1.execute("rollback savepoint;")
            T1.wait_finish()
            T2.execute("insert into test_tb  values(3);")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE165(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE165:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE165:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE165:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_split cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_split like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_split select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from emp_split")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            os.system("python RegionSplit.py")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_split for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_split for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE166(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE166:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE166:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE166:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_split cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_split like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_split select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("delete from emp_split where employeeno = 7788")
            T1.wait_finish()
            os.system("python RegionSplit.py")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_split for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_split for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE167(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE167:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE167:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE167:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_split cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_split like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_split select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("update emp_split set sal = 7800 where employeeno = 7788")
            T1.wait_finish()
            os.system("python RegionSplit.py")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("update emp_split set sal = 7800 where employeeno = 7788")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_split for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE168(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE168:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE168:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE168:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_split cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_split like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_split select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from emp_split for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            os.system("python RegionSplit.py")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_split for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_split for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("commit")
            T2.wait_finish()

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

    def test_CASE169(self):
        terminals = []
        try:
            case_terminal = QueryTerminal(log_prefix="[test_CASE169:case_terminal]")
            case_terminal.start()
            terminals.append(case_terminal)
            T1 = QueryTerminal(log_prefix="[test_CASE169:T1]")
            T1.start()
            terminals.append(T1)
            T2 = QueryTerminal(log_prefix="[test_CASE169:T2]")
            T2.start()
            terminals.append(T2)
            T1.execute("drop table emp_split cascade")
            T1.wait_finish()
            temp_var = T1.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            T1.execute("create table emp_split like  employee")
            T1.wait_finish()
            T1.execute("insert into emp_split select * from employee")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from emp_split where employeeno = 7788 for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            os.system("python RegionSplit.py")
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_split where employeeno = 7788 for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 30052, "expect statusValue.code == 30052")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select * from emp_split for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            T2.execute("commit")
            T2.wait_finish()

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
    su.addTest(MyTestCase("test_CASE000"))
    su.addTest(MyTestCase("test_CASE001"))
    su.addTest(MyTestCase("test_CASE002"))
    su.addTest(MyTestCase("test_CASE003"))
    su.addTest(MyTestCase("test_CASE004"))
    su.addTest(MyTestCase("test_CASE005"))
    su.addTest(MyTestCase("test_CASE006"))
    su.addTest(MyTestCase("test_CASE007"))
    su.addTest(MyTestCase("test_CASE008"))
    su.addTest(MyTestCase("test_CASE009"))
    su.addTest(MyTestCase("test_CASE010"))
    su.addTest(MyTestCase("test_CASE011"))
    su.addTest(MyTestCase("test_CASE012"))
    su.addTest(MyTestCase("test_CASE013"))
    su.addTest(MyTestCase("test_CASE014"))
    su.addTest(MyTestCase("test_CASE015"))
    su.addTest(MyTestCase("test_CASE016"))
    su.addTest(MyTestCase("test_CASE017"))
    su.addTest(MyTestCase("test_CASE018"))
    su.addTest(MyTestCase("test_CASE019"))
    su.addTest(MyTestCase("test_CASE020"))
    su.addTest(MyTestCase("test_CASE021"))
    su.addTest(MyTestCase("test_CASE022"))
    su.addTest(MyTestCase("test_CASE023"))
    su.addTest(MyTestCase("test_CASE024"))
    su.addTest(MyTestCase("test_CASE025"))
    su.addTest(MyTestCase("test_CASE026"))
    su.addTest(MyTestCase("test_CASE027"))
    su.addTest(MyTestCase("test_CASE028"))
    su.addTest(MyTestCase("test_CASE029"))
    su.addTest(MyTestCase("test_CASE030"))
    su.addTest(MyTestCase("test_CASE031"))
    su.addTest(MyTestCase("test_CASE032"))
    su.addTest(MyTestCase("test_CASE033"))
    su.addTest(MyTestCase("test_CASE034"))
    su.addTest(MyTestCase("test_CASE035"))
    su.addTest(MyTestCase("test_CASE036"))
    su.addTest(MyTestCase("test_CASE037"))
    su.addTest(MyTestCase("test_CASE038"))
    su.addTest(MyTestCase("test_CASE039"))
    su.addTest(MyTestCase("test_CASE040"))
    su.addTest(MyTestCase("test_CASE041"))
    su.addTest(MyTestCase("test_CASE042"))
    su.addTest(MyTestCase("test_CASE043"))
    su.addTest(MyTestCase("test_CASE044"))
    su.addTest(MyTestCase("test_CASE045"))
    su.addTest(MyTestCase("test_CASE046"))
    su.addTest(MyTestCase("test_CASE047"))
    su.addTest(MyTestCase("test_CASE048"))
    su.addTest(MyTestCase("test_CASE049"))
    su.addTest(MyTestCase("test_CASE050"))
    su.addTest(MyTestCase("test_CASE051"))
    su.addTest(MyTestCase("test_CASE052"))
    su.addTest(MyTestCase("test_CASE053"))
    su.addTest(MyTestCase("test_CASE054"))
    su.addTest(MyTestCase("test_CASE055"))
    su.addTest(MyTestCase("test_CASE056"))
    su.addTest(MyTestCase("test_CASE057"))
    su.addTest(MyTestCase("test_CASE058"))
    su.addTest(MyTestCase("test_CASE059"))
    su.addTest(MyTestCase("test_CASE060"))
    su.addTest(MyTestCase("test_CASE061"))
    su.addTest(MyTestCase("test_CASE062"))
    su.addTest(MyTestCase("test_CASE063"))
    su.addTest(MyTestCase("test_CASE064"))
    su.addTest(MyTestCase("test_CASE065"))
    su.addTest(MyTestCase("test_CASE066"))
    su.addTest(MyTestCase("test_CASE067"))
    su.addTest(MyTestCase("test_CASE068"))
    su.addTest(MyTestCase("test_CASE069"))
    su.addTest(MyTestCase("test_CASE070"))
    su.addTest(MyTestCase("test_CASE071"))
    su.addTest(MyTestCase("test_CASE072"))
    su.addTest(MyTestCase("test_CASE073"))
    su.addTest(MyTestCase("test_CASE074"))
    su.addTest(MyTestCase("test_CASE075"))
    su.addTest(MyTestCase("test_CASE076"))
    su.addTest(MyTestCase("test_CASE077"))
    su.addTest(MyTestCase("test_CASE078"))
    su.addTest(MyTestCase("test_CASE079"))
    su.addTest(MyTestCase("test_CASE080"))
    su.addTest(MyTestCase("test_CASE081"))
    su.addTest(MyTestCase("test_CASE082"))
    su.addTest(MyTestCase("test_CASE083"))
    su.addTest(MyTestCase("test_CASE084"))
    su.addTest(MyTestCase("test_CASE085"))
    su.addTest(MyTestCase("test_CASE086"))
    su.addTest(MyTestCase("test_CASE087"))
    su.addTest(MyTestCase("test_CASE088"))
    su.addTest(MyTestCase("test_CASE089"))
    su.addTest(MyTestCase("test_CASE090"))
    su.addTest(MyTestCase("test_CASE091"))
    su.addTest(MyTestCase("test_CASE092"))
    su.addTest(MyTestCase("test_CASE093"))
    su.addTest(MyTestCase("test_CASE094"))
    su.addTest(MyTestCase("test_CASE095"))
    su.addTest(MyTestCase("test_CASE096"))
    su.addTest(MyTestCase("test_CASE097"))
    su.addTest(MyTestCase("test_CASE098"))
    su.addTest(MyTestCase("test_CASE099"))
    su.addTest(MyTestCase("test_CASE100"))
    su.addTest(MyTestCase("test_CASE101"))
    su.addTest(MyTestCase("test_CASE102"))
    su.addTest(MyTestCase("test_CASE103"))
    su.addTest(MyTestCase("test_CASE104"))
    su.addTest(MyTestCase("test_CASE105"))
    su.addTest(MyTestCase("test_CASE106"))
    su.addTest(MyTestCase("test_CASE107"))
    su.addTest(MyTestCase("test_CASE108"))
    su.addTest(MyTestCase("test_CASE109"))
    su.addTest(MyTestCase("test_CASE110"))
    su.addTest(MyTestCase("test_CASE111"))
    su.addTest(MyTestCase("test_CASE112"))
    su.addTest(MyTestCase("test_CASE113"))
    su.addTest(MyTestCase("test_CASE114"))
    su.addTest(MyTestCase("test_CASE115"))
    su.addTest(MyTestCase("test_CASE116"))
    su.addTest(MyTestCase("test_CASE117"))
    su.addTest(MyTestCase("test_CASE118"))
    su.addTest(MyTestCase("test_CASE119"))
    su.addTest(MyTestCase("test_CASE120"))
    su.addTest(MyTestCase("test_CASE121"))
    su.addTest(MyTestCase("test_CASE122"))
    su.addTest(MyTestCase("test_CASE123"))
    su.addTest(MyTestCase("test_CASE124"))
    su.addTest(MyTestCase("test_CASE125"))
    su.addTest(MyTestCase("test_CASE126"))
    su.addTest(MyTestCase("test_CASE127"))
    su.addTest(MyTestCase("test_CASE128"))
    su.addTest(MyTestCase("test_CASE129"))
    su.addTest(MyTestCase("test_CASE130"))
    su.addTest(MyTestCase("test_CASE131"))
    su.addTest(MyTestCase("test_CASE132"))
    su.addTest(MyTestCase("test_CASE133"))
    su.addTest(MyTestCase("test_CASE134"))
    su.addTest(MyTestCase("test_CASE135"))
    su.addTest(MyTestCase("test_CASE136"))
    su.addTest(MyTestCase("test_CASE137"))
    su.addTest(MyTestCase("test_CASE138"))
    su.addTest(MyTestCase("test_CASE139"))
    su.addTest(MyTestCase("test_CASE140"))
    su.addTest(MyTestCase("test_CASE141"))
    su.addTest(MyTestCase("test_CASE142"))
    su.addTest(MyTestCase("test_CASE143"))
    su.addTest(MyTestCase("test_CASE144"))
    su.addTest(MyTestCase("test_CASE145"))
    su.addTest(MyTestCase("test_CASE146"))
    su.addTest(MyTestCase("test_CASE147"))
    su.addTest(MyTestCase("test_CASE148"))
    su.addTest(MyTestCase("test_CASE149"))
    su.addTest(MyTestCase("test_CASE150"))
    su.addTest(MyTestCase("test_CASE151"))
    su.addTest(MyTestCase("test_CASE152"))
    su.addTest(MyTestCase("test_CASE153"))
    su.addTest(MyTestCase("test_CASE154"))
    su.addTest(MyTestCase("test_CASE155"))
    su.addTest(MyTestCase("test_CASE156"))
    su.addTest(MyTestCase("test_CASE157"))
    su.addTest(MyTestCase("test_CASE158"))
    su.addTest(MyTestCase("test_CASE159"))
    su.addTest(MyTestCase("test_CASE160"))
    su.addTest(MyTestCase("test_CASE161"))
    su.addTest(MyTestCase("test_CASE162"))
    su.addTest(MyTestCase("test_CASE163"))
    su.addTest(MyTestCase("test_Case164"))
    su.addTest(MyTestCase("test_CASE165"))
    su.addTest(MyTestCase("test_CASE166"))
    su.addTest(MyTestCase("test_CASE167"))
    su.addTest(MyTestCase("test_CASE168"))
    su.addTest(MyTestCase("test_CASE169"))
    unittest.TextTestRunner(verbosity=1).run(su)
