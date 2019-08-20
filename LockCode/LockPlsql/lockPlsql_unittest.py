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
    'schema': 's_lockplsql',
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
            case_terminal.execute("drop schema s_lockplsql cascade")
            case_terminal.wait_finish()
            temp_var = case_terminal.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
            case_terminal.execute("cleanup schema s_lockplsql")
            case_terminal.wait_finish()
            case_terminal.execute("create schema  if not exists s_lockplsql")
            case_terminal.wait_finish()
            case_terminal.execute("set schema s_lockplsql")
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
            case_terminal.execute("create index idx_plsql on employee(employeeno);")
            case_terminal.wait_finish()
            case_terminal.execute("create view viewplsql as select * from employee where employeeno >= 7788;")
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
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""begin
 for c in (select employeeno , ename from employee)
  loop
    dbms_output.put_line(c.employeeno || '   ' || c.ename);
 end loop;
 end;
 /""")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""begin
 for c in (select employeeno , ename from employee for update)
  loop
    dbms_output.put_line(c.employeeno || '   ' || c.ename);
 end loop;
 end;
 /""")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("commit")
            T2.wait_finish()
            T2.execute("select * from employee for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("select * from employee for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")

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
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""begin
 for c in (select employeeno , ename from employee)
  loop
    dbms_output.put_line(c.employeeno || '   ' || c.ename);
 end loop;
 end;
 /""")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""begin
 for c in (select employeeno , ename from employee for update)
  loop
    dbms_output.put_line(c.employeeno || '   ' || c.ename);
 end loop;
 end;
 /""")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("rollback")
            T2.wait_finish()
            T2.execute("select * from employee for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("select * from employee for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")

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
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""BEGIN
   DECLARE IXname char(20) :='ix_lock';
   DBMS_OUTPUT.PUT_LINE('Add IX lock in AnonymoUs');
   exec 'UPDATE employee SET ENAME = '''||IXname||'''  WHERE EMPLOYEENO = 7788 '; /*add X-row lock*/
END;
/""")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""begin
 for c in (select employeeno , ename from employee for update)
  loop
    dbms_output.put_line(c.employeeno || '   ' || c.ename);
 end loop;
 end;
 /""")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("commit")
            T2.wait_finish()
            T2.execute("select * from employee for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("select * from employee for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")

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
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""BEGIN
   DECLARE IXname char(20) :='ix_lock';
   DBMS_OUTPUT.PUT_LINE('Add IX lock in AnonymoUs');
   exec 'UPDATE employee SET ENAME = '''||IXname||'''  WHERE EMPLOYEENO = 7788'; /*add X-row lock*/
END;
/""")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""begin
 for c in (select employeeno , ename from employee for update)
  loop
    dbms_output.put_line(c.employeeno || '   ' || c.ename);
 end loop;
 end;
 /""")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("rollback")
            T2.wait_finish()
            T2.execute("select * from employee for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("select * from employee for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")

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
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""begin
 for c in (select employeeno , ename from employee for update)
  loop
    dbms_output.put_line(c.employeeno || '   ' || c.ename);
 end loop;
 end;
 /""")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""begin
 for c in (select employeeno , ename from employee for update)
  loop
    dbms_output.put_line(c.employeeno || '   ' || c.ename);
 end loop;
 end;
 /""")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("commit")
            T2.wait_finish()
            T2.execute("select * from employee for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("select * from employee for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")

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
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""begin
 for c in (select employeeno , ename from employee for update)
  loop
    dbms_output.put_line(c.employeeno || '   ' || c.ename);
 end loop;
 end;
 /""")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""begin
 for c in (select employeeno , ename from employee for update)
  loop
    dbms_output.put_line(c.employeeno || '   ' || c.ename);
 end loop;
 end;
 /""")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("rollback")
            T2.wait_finish()
            T2.execute("select * from employee for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("select * from employee for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")

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
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""BEGIN
   DECLARE IXname char(20) :='Xiang';
   DBMS_OUTPUT.PUT_LINE('X row lock AnonymoUs test');
   exec 'UPDATE employee SET ENAME = '''||IXname||'''  WHERE EMPLOYEENO = 7788 '; /*add X-row lock*/
END;
/""")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""BEGIN
   DECLARE IXname char(20) :='Xiang';
   DBMS_OUTPUT.PUT_LINE('X row lock AnonymoUs test');
   exec 'UPDATE employee SET ENAME = '''||IXname||'''  WHERE EMPLOYEENO = 7788 '; /*add X-row lock*/
END;
/""")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("commit")
            T2.wait_finish()
            T2.execute("select * from employee for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("select * from employee for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")

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
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""BEGIN
   DECLARE IXname char(20) :='Xiang';
   DBMS_OUTPUT.PUT_LINE('X row lock AnonymoUs test');
   exec 'UPDATE employee SET ENAME = '''||IXname||'''  WHERE EMPLOYEENO = 7788 '; /*add X-row lock*/
END;
/""")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""BEGIN
   DECLARE IXname char(20) :='Xiang';
   DBMS_OUTPUT.PUT_LINE('X row lock AnonymoUs test');
   exec 'UPDATE employee SET ENAME = '''||IXname||'''  WHERE EMPLOYEENO = 7788 '; /*add X-row lock*/
END;
/""")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("rollback")
            T2.wait_finish()
            T2.execute("select * from employee for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("select * from employee for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")

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
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""begin
 for c in (select employeeno , ename from employee where employeeno = 7788  for update)
  loop
    dbms_output.put_line(c.employeeno || '   ' || c.ename);
 end loop;
 end;
 /""")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""begin
 for c in (select employeeno , ename from employee where employeeno = 7788  for update)
  loop
    dbms_output.put_line(c.employeeno || '   ' || c.ename);
 end loop;
 end;
 /""")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("commit")
            T2.wait_finish()
            T2.execute("select * from employee for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("select * from employee for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")

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
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""begin
 for c in (select employeeno , ename from employee where employeeno = 7788  for update)
  loop
    dbms_output.put_line(c.employeeno || '   ' || c.ename);
 end loop;
 end;
 /""")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""begin
 for c in (select employeeno , ename from employee where employeeno = 7788  for update)
  loop
    dbms_output.put_line(c.employeeno || '   ' || c.ename);
 end loop;
 end;
 /""")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("rollback")
            T2.wait_finish()
            T2.execute("select * from employee for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("select * from employee for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectEqual(statusValue.code, 0, "expect statusValue.code == 0")
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")

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
            case_terminal.execute("""create or replace procedure test_is_lock() as
begin
 for c in (select employeeno , ename from employee)
  loop
    dbms_output.put_line(c.employeeno || '   ' || c.ename);
 end loop;
 end;
/""")
            case_terminal.wait_finish()
            case_terminal.execute("""CREATE OR REPLACE PROCEDURE test_x_table_lock() AS
begin
 for c in (select employeeno , ename from employee for update)
  loop
    dbms_output.put_line(c.employeeno || '   ' || c.ename);
 end loop;
 end;
/""")
            case_terminal.wait_finish()
            case_terminal.execute("""create or replace procedure test_Ix_lock() as
DECLARE
   c1 VARCHAR(10);
BEGIN
   SELECT 'Ix_LOCK' INTO c1 FROM DUAL ;
   exec 'UPDATE employee SET ENAME = '''||c1||'''  WHERE EMPLOYEENO = 7788 '; /*add X-row lock*/
   DBMS_OUTPUT.PUT_LINE('Ix lock procedure test');
END;
/""")
            case_terminal.wait_finish()
            case_terminal.execute("""create or replace procedure test_x_row_lock() as
declare
	c1 varchar(10);
begin
	select 'x_r_lock' into c1;
	exec 'UPDATE employee SET ENAME = '''||c1||'''  WHERE EMPLOYEENO = 7788 '; /*add X-row lock*/
	dbms_output.put_line('x row lock procedure test');
end;
/""")
            case_terminal.wait_finish()
            case_terminal.execute("""create or replace procedure test_u_lock() as
begin
	for c in (select employeeno , ename from employee  WHERE EMPLOYEENO = '7788' for update)
	loop
		dbms_output.put_line(c.employeeno || '   ' || c.ename);
	end loop;
end;
/""")
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
            T1.execute("drop function get_avg_islock cascade")
            T1.wait_finish()
            T1.execute("""CREATE FUNCTION get_avg_islock() RETURNS (avg_lock INT) AS
BEGIN
 DECLARE cnt INT = 0;
 SELECT avg(sal) INTO cnt FROM employee
 WHERE JOB LIKE '%CLERK';

 RETURN cnt;
END;
/""")
            T1.wait_finish()
            T1.execute("drop function get_avg_x_Tablelock cascade")
            T1.wait_finish()
            T1.execute("""create function get_avg_x_Tablelock() return(avg_lock INT) as
begin
	declare cnt int = 0;
	select avg(sal) into cnt from employee for update;
	return cnt;
END;
/""")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select get_avg_islock() from dual")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select get_avg_x_Tablelock() from dual;")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("select * from employee for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("select * from employee for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")

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
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select get_avg_islock() from dual")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select get_avg_x_Tablelock() from dual;")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("select * from employee for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("select * from employee for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")

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
            T1.execute("drop function get_avg_ixlock cascade")
            T1.wait_finish()
            T1.execute("""create function get_avg_ixlock() RETURNS(avg_lock INT) as
begin
	declare cnt int = 0;
	update employee set ename ='ix_lock' where employeeno = '7788';
	select avg(sal) into cnt from employee where employeeno = '7788';
	return cnt;
end;
/""")
            T1.wait_finish()
            T1.execute("drop function get_avg_x_Tablelock cascade")
            T1.wait_finish()
            T1.execute("""create function get_avg_x_Tablelock() return(avg_lock INT) as
begin
	declare cnt int = 0;
	select avg(sal) into cnt from employee for update;
	return cnt;
END;
/""")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select get_avg_ixlock() from dual;")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select get_avg_x_Tablelock() from dual;")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("select * from employee for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("select * from employee for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")

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
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select get_avg_ixlock() from dual;")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select get_avg_x_Tablelock() from dual;")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("select * from employee for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("select * from employee for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")

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
            T1.execute("drop function get_avg_x_rowtablelock cascade")
            T1.wait_finish()
            T1.execute("""create function get_avg_x_rowtablelock() return(avg_lock INT) as
begin
	declare cnt int = 0;
	update employee set ename ='ix_lock' where employeeno = '7788';
	select avg(sal) into cnt from employee where employeeno = '7788';
	return cnt;
end;
/""")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select get_avg_x_rowtablelock() from dual;")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select get_avg_x_rowtablelock() from dual;")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("update employee set ename ='ix_lock' where employeeno = '7788';")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("update employee set ename ='ix_lock' where employeeno = '7788';")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")

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
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select get_avg_x_rowtablelock() from dual;")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select get_avg_x_rowtablelock() from dual;")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("update employee set ename ='ix_lock' where employeeno = '7788';")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("update employee set ename ='ix_lock' where employeeno = '7788';")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")

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
            T1.execute("drop function get_avg_ulock cascade")
            T1.wait_finish()
            T1.execute("""create function get_avg_ulock() return(avg_lock INT) as
begin
	declare cnt int = 0;
	select avg(sal) into cnt from employee where employeeno = '7788' for update;
	return cnt;
end;
/""")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select get_avg_ulock() from dual;")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select get_avg_ulock() from dual;")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("select * from employee where employeeno = '7788' for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("select * from employee where employeeno = '7788' for update;")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")

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
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select get_avg_ulock() from dual;")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select get_avg_ulock() from dual;")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("select * from employee where employeeno = '7788' for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("select * from employee where employeeno = '7788' for update;")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")

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
            T1.execute("drop function get_avg_x_Tablelock cascade")
            T1.wait_finish()
            T1.execute("""create function get_avg_x_Tablelock() return(avg_lock INT) as
begin
	declare cnt int = 0;
	select avg(sal) into cnt from employee for update;
	return cnt;
end;
/""")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select get_avg_x_Tablelock() from dual;")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select get_avg_x_Tablelock() from dual;")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("select * from employee for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("select * from employee for update;")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")

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
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select get_avg_x_Tablelock() from dual;")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("select get_avg_x_Tablelock() from dual;")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("select * from employee for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("select * from employee for update;")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")

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
            case_terminal.execute("""CREATE OR REPLACE PACKAGE BODY test_pack_islock AS //
FUNCTION get_avg_islock() RETURNS INT
BEGIN
 DECLARE cnt INT = 0;
 SELECT avg(sal)INTO cnt FROM employee
 WHERE JOB LIKE '%CLERK';

 RETURN cnt;
END;
END//;""")
            case_terminal.wait_finish()
            case_terminal.execute("""CREATE OR REPLACE PACKAGE BODY test_pack_xtablelock AS //
function get_avg_x_Tablelock() return int
begin
	declare cnt int = 0;
	select avg(sal)into cnt from employee for update;
	return cnt;
end;
end//;""")
            case_terminal.wait_finish()
            case_terminal.execute("""CREATE OR REPLACE PACKAGE BODY test_pack_ixlock AS //
function get_avg_ixlock() RETURNS int
begin
	declare cnt int = 0;
	update employee set ename ='ix_lock' where employeeno = '7788';
	select avg(sal)into cnt from employee where employeeno = '7788';
	return cnt;
end;
end//;""")
            case_terminal.wait_finish()
            case_terminal.execute("""CREATE OR REPLACE PACKAGE BODY test_pack_xrowlock AS //
function get_avg_xlock() RETURNS int
begin
	declare cnt int = 0;
	update employee set ename ='ix_lock' where employeeno = '7788';
	select avg(sal)into cnt from employee where employeeno = '7788';
	return cnt;
end;
end//;""")
            case_terminal.wait_finish()
            case_terminal.execute("""CREATE OR REPLACE PACKAGE BODY test_pack_ulock AS //
function get_avg_ulock() return  int
begin
	declare cnt int = 0;
	select avg(sal)into cnt from employee where employeeno = '7788' for update;
	return cnt;
end;
end//;""")
            case_terminal.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""BEGIN
  DBMS_OUTPUT.PUT_LINE('is_lock test:  '||test_pack_islock.get_avg_islock());
END;
/""")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""BEGIN
  DBMS_OUTPUT.PUT_LINE('table check confict  '|| test_pack_xtablelock.get_avg_x_Tablelock());
END;
/""")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("select * from employee for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("select * from employee for update ;")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")

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
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""BEGIN
  DBMS_OUTPUT.PUT_LINE('is_lock test:  '||test_pack_islock.get_avg_islock());
END;
/""")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""BEGIN
  DBMS_OUTPUT.PUT_LINE('table check confict  '|| test_pack_xtablelock.get_avg_x_Tablelock());
END;
/""")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("select * from employee for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("select * from employee for update ;")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")

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
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""BEGIN
  DBMS_OUTPUT.PUT_LINE('ix_lock test '||test_pack_ixlock.get_avg_ixlock());
END;
/""")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""BEGIN
  DBMS_OUTPUT.PUT_LINE('table check confict  '|| test_pack_xtablelock.get_avg_x_Tablelock());
END;
/""")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("select * from employee for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("select * from employee for update;")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")

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
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""BEGIN
  DBMS_OUTPUT.PUT_LINE('ix_lock test '||test_pack_ixlock.get_avg_ixlock());
END;
/""")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""BEGIN
  DBMS_OUTPUT.PUT_LINE('table check confict  '|| test_pack_xtablelock.get_avg_x_Tablelock());
END;
/""")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("select * from employee for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("select * from employee for update;")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")

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
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""BEGIN
  DBMS_OUTPUT.PUT_LINE('ix_lock test '||test_pack_xrowlock.get_avg_xlock());
END;
/""")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""BEGIN
  DBMS_OUTPUT.PUT_LINE('ix_lock test '||test_pack_xrowlock.get_avg_xlock());
END;
/""")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("update employee set ename ='ix_lock' where employeeno = '7788';")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("update employee set ename ='ix_lock' where employeeno = '7788';")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")

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
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""BEGIN
  DBMS_OUTPUT.PUT_LINE('ix_lock test '||test_pack_xrowlock.get_avg_xlock());
END;
/""")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""BEGIN
  DBMS_OUTPUT.PUT_LINE('ix_lock test '||test_pack_xrowlock.get_avg_xlock());
END;
/""")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("update employee set ename ='ix_lock' where employeeno = '7788';")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("update employee set ename ='ix_lock' where employeeno = '7788';")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")

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
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""BEGIN
  DBMS_OUTPUT.PUT_LINE('u rowlock test '|| test_pack_ulock.get_avg_ulock());
END;
/""")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""BEGIN
  DBMS_OUTPUT.PUT_LINE('u rowlock test '|| test_pack_ulock.get_avg_ulock());
END;
/""")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("select sal from employee where employeeno = '7788' for update;")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("select sal from employee where employeeno = '7788' for update;")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")

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
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""BEGIN
  DBMS_OUTPUT.PUT_LINE('u rowlock test '|| test_pack_ulock.get_avg_ulock());
END;
/""")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""BEGIN
  DBMS_OUTPUT.PUT_LINE('u rowlock test '|| test_pack_ulock.get_avg_ulock());
END;
/""")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("select sal from employee where employeeno = '7788' for update;")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("select sal from employee where employeeno = '7788' for update;")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")

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
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""BEGIN
  DBMS_OUTPUT.PUT_LINE('x_table_lock test '||test_pack_xtablelock.get_avg_x_Tablelock());
END;
/""")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""BEGIN
  DBMS_OUTPUT.PUT_LINE('x_table_lock test '||test_pack_xtablelock.get_avg_x_Tablelock());
END;
/""")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("select sal from employee for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("select sal from employee for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")

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
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""BEGIN
  DBMS_OUTPUT.PUT_LINE('x_table_lock test '||test_pack_xtablelock.get_avg_x_Tablelock());
END;
/""")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""BEGIN
  DBMS_OUTPUT.PUT_LINE('x_table_lock test '||test_pack_xtablelock.get_avg_x_Tablelock());
END;
/""")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T2.execute("select sal from employee for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("select sal from employee for update")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")

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
    unittest.TextTestRunner(verbosity=1).run(su)
