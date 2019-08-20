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
    'schema': 'LOCK_TRIGGER',
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
            case_terminal.execute("drop schema lock_trigger cascade;")
            case_terminal.wait_finish()
            case_terminal.execute("create schema lock_trigger;")
            case_terminal.wait_finish()
            case_terminal.execute("set schema lock_trigger;")
            case_terminal.wait_finish()
            case_terminal.execute("drop table TE_RULE_HISTORY cascade")
            case_terminal.wait_finish()
            case_terminal.execute("""create table TE_RULE_HISTORY 
( 
  OPERTLR      varchar(10) CHARACTER SET UTF8, 
  OPERTIME     varchar(20) CHARACTER SET UTF8, 
  OPERDESC     varchar(128) CHARACTER SET UTF8, 
  UPTABLE      varchar(30) CHARACTER SET UTF8, 
  UPDATA       varchar(1024) CHARACTER SET UTF8 
);""")
            case_terminal.wait_finish()
            case_terminal.execute("""drop table TE_AU_MODE cascade""")
            case_terminal.wait_finish()
            case_terminal.execute(""" create table TE_AU_MODE
(
  MODEID       varchar(10) CHARACTER SET UTF8 not null,
  AUTHTYPE     varchar(1)  CHARACTER SET UTF8 not null,
  AUTHLEVEL    varchar(4)  CHARACTER SET UTF8 ,
  AUTHLEVELD   varchar(2)  CHARACTER SET UTF8 ,
  AUTHBRNOTYPE varchar(2)  CHARACTER SET UTF8 ,
  AUTHBRNO     varchar(8) CHARACTER SET UTF8, 
  AUTHPOST     varchar(20) CHARACTER SET UTF8, 
  URGENTFLAG   CHAR(1) CHARACTER SET UTF8, 
  AUTHDESC     varchar(128) CHARACTER SET UTF8 not null,
  HXAUTHFLAG   varchar(2) CHARACTER SET UTF8, 
  HXAUTHTYPE   varchar(2) CHARACTER SET UTF8, 
  REMARK       varchar(50) CHARACTER SET UTF8, 
  REMARK1      varchar(100) CHARACTER SET UTF8, 
  JZAUTHBNK    varchar(20) CHARACTER SET UTF8, 
  JZAUTHLVL    varchar(10) CHARACTER SET UTF8
)
primary key (MODEID);""")
            case_terminal.wait_finish()
            case_terminal.execute(""" INSERT INTO TE_AU_MODE (MODEID,AUTHTYPE,AUTHLEVEL,AUTHLEVELD,AUTHBRNOTYPE,AUTHBRNO,AUTHPOST,URGENTFLAG,AUTHDESC,HXAUTHFLAG,HXAUTHTYPE,REMARK,REMARK1,JZAUTHBNK,JZAUTHLVL) VALUES (
 'AU00001', '4', NULL, NULL, NULL, NULL, NULL, NULL, '累计取现金额达到100万', NULL, NULL, NULL, NULL, NULL, NULL);""")
            case_terminal.wait_finish()
            case_terminal.execute(""" INSERT INTO TE_AU_MODE (MODEID,AUTHTYPE,AUTHLEVEL,AUTHLEVELD,AUTHBRNOTYPE,AUTHBRNO,AUTHPOST,URGENTFLAG,AUTHDESC,HXAUTHFLAG,HXAUTHTYPE,REMARK,REMARK1,JZAUTHBNK,JZAUTHLVL) VALUES (
'AU00002', '4', NULL, NULL, NULL, NULL, NULL, NULL, '累计转账金额达到100万', NULL, NULL, NULL, NULL, NULL, NULL);""")
            case_terminal.wait_finish()
            case_terminal.execute(""" INSERT INTO TE_AU_MODE(MODEID,AUTHTYPE,AUTHLEVEL,AUTHLEVELD,AUTHBRNOTYPE,AUTHBRNO,AUTHPOST,URGENTFLAG,AUTHDESC,HXAUTHFLAG,HXAUTHTYPE,REMARK,REMARK1,JZAUTHBNK,JZAUTHLVL) VALUES (
  'AU00003', '1', '1', NULL, NULL, NULL, 'GW006', NULL, '此交易必须授权', NULL, NULL, NULL, NULL, NULL, NULL);""")
            case_terminal.wait_finish()
            case_terminal.execute(""" INSERT INTO TE_AU_MODE(MODEID,AUTHTYPE,AUTHLEVEL,AUTHLEVELD,AUTHBRNOTYPE,AUTHBRNO,AUTHPOST,URGENTFLAG,AUTHDESC,HXAUTHFLAG,HXAUTHTYPE,REMARK,REMARK1,JZAUTHBNK,JZAUTHLVL) VALUES (
  'AU00004', '2', '1', NULL, NULL, NULL, 'GW006', NULL, '此交易必须授权', NULL, NULL, NULL, NULL, NULL, NULL);""")
            case_terminal.wait_finish()
            case_terminal.execute(""" INSERT INTO TE_AU_MODE(MODEID,AUTHTYPE,AUTHLEVEL,AUTHLEVELD,AUTHBRNOTYPE,AUTHBRNO,AUTHPOST,URGENTFLAG,AUTHDESC,HXAUTHFLAG,HXAUTHTYPE,REMARK,REMARK1,JZAUTHBNK,JZAUTHLVL) VALUES (
  'AU00005', '3', '1', NULL, NULL, NULL, 'GW006', NULL, '此交易必须授权', NULL, NULL, NULL, NULL, NULL, NULL);""")
            case_terminal.wait_finish()
            case_terminal.execute(""" INSERT INTO TE_AU_MODE(MODEID,AUTHTYPE,AUTHLEVEL,AUTHLEVELD,AUTHBRNOTYPE,AUTHBRNO,AUTHPOST,URGENTFLAG,AUTHDESC,HXAUTHFLAG,HXAUTHTYPE,REMARK,REMARK1,JZAUTHBNK,JZAUTHLVL) VALUES (
  'AU00006', '4', NULL, NULL, NULL, NULL, NULL, NULL, '此交易必须授权', NULL, NULL, NULL, NULL, NULL, NULL);""")
            case_terminal.wait_finish()
            case_terminal.execute(""" INSERT INTO TE_AU_MODE(MODEID,AUTHTYPE,AUTHLEVEL,AUTHLEVELD,AUTHBRNOTYPE,AUTHBRNO,AUTHPOST,URGENTFLAG,AUTHDESC,HXAUTHFLAG,HXAUTHTYPE,REMARK,REMARK1,JZAUTHBNK,JZAUTHLVL) VALUES (
  'AU00007', '5', NULL, NULL, NULL, NULL, NULL, NULL, '此交易必须授权', NULL, NULL, NULL, NULL, NULL, NULL);""")
            case_terminal.wait_finish()
            case_terminal.execute(""" INSERT INTO TE_AU_MODE(MODEID,AUTHTYPE,AUTHLEVEL,AUTHLEVELD,AUTHBRNOTYPE,AUTHBRNO,AUTHPOST,URGENTFLAG,AUTHDESC,HXAUTHFLAG,HXAUTHTYPE,REMARK,REMARK1,JZAUTHBNK,JZAUTHLVL) VALUES (
  'AU00012', '1', '1', NULL, NULL, NULL, 'GW006', NULL, '个人存款账户开户金额大于等于RMB50000元', NULL, NULL, '该账户有未追回的利息', NULL, NULL, NULL);""")
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
            case_terminal.execute("""CREATE OR REPLACE TRIGGER TE_AU_MODE_TRIG before INSERT
  OR UPDATE OR DELETE ON TRAFODION.LOCK_TRIGGER.TE_AU_MODE FOR EACH ROW AS
    begin
if inserting then /*插入操作时*/
insert into TE_RULE_HISTORY

         values

      (:new.
      MODEID,to_char(systimestamp,'yyyymmddhh24Miss'),'插入','TE_AU
      MODE',
      :new.MODEID||','||:new.AUTHTYPE||','||:new.AUTHLEVEL||','||:new.AUTHLEVELD||','||:new.AUTHBRNOTYPE||','||:new.AUTHBRNO||','||:new.AUTHPOST||','||:new.URGENTFLAG||','||:new.AUTHDESC||','||:new.HXAUTHFLAG||','||:new.HXAUTHTYPE||','||:new.REMARK||','||:new.REMARK1||','||:new.JZAUTHBNK||','||:new.JZAUTHLVL);
            elsif updating then /*更新操作时*/
insert into TE_RULE_HISTORY
            values

      (:old.MODEID,to_char(systimestamp,'yyyymmddhh24Miss'),'更新','TE_AU
      MODE',
      :old.MODEID||','||:old.AUTHTYPE||','||:old.AUTHLEVEL||','||:old.AUTHLEVELD||','||:old.AUTHBRNOTYPE||','||:old.AUTHBRNO||','||:old.AUTHPOST||','||:old.URGENTFLAG||','||:old.AUTHDESC||','||:old.HXAUTHFLAG||','||:old.HXAUTHTYPE||','||:old.REMARK||','||:old.REMARK1||','||:old.JZAUTHBNK||','||:old.JZAUTHLVL);
            elsif deleting then /*删除操作时*/
insert into TE_RULE_HISTORY
            values

      (:old.
      MODEID,to_char(systimestamp,'yyyymmddhh24Miss'),'删除','TE_AU
      MODE',
      :old.MODEID||','||:old.AUTHTYPE||','||:old.AUTHLEVEL||','||:old.AUTHLEVELD||','||:old.AUTHBRNOTYPE||','||:old.AUTHBRNO||','||:old.AUTHPOST||','||:old.URGENTFLAG||','||:old.AUTHDESC||','||:old.HXAUTHFLAG||','||:old.HXAUTHTYPE||','||:old.REMARK||','||:old.REMARK1||','||:old.JZAUTHBNK||','||:old.JZAUTHLVL);
            end if;
end;
/""")
            case_terminal.wait_finish()
            T1.execute("delete from TE_RULE_HISTORY")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("update TE_AU_MODE set AUTHTYPE = '1' where MODEID = 'AU00001';")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""select * from TE_RULE_HISTORY for update""")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            self.expectTrue(str("LockTimeOutException") not in str(statusValue.message), "expect str(statusValue.message) no str(\"LockTimeOutException\")")
            T2.execute("commit")
            T2.wait_finish()
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("select * from TE_RULE_HISTORY for update")
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
            T1.execute("delete from TE_RULE_HISTORY")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from TE_RULE_HISTORY for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""update TE_AU_MODE set AUTHTYPE = '1' where MODEID = 'AU00001'""")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            self.expectTrue(str("LockTimeOutException") not in str(statusValue.message), "expect str(statusValue.message) no str(\"LockTimeOutException\")")
            T2.execute("commit")
            T2.wait_finish()
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("update TE_AU_MODE set AUTHTYPE = '1' where MODEID = 'AU00001'")
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
            T1.execute("delete from TE_RULE_HISTORY")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("delete from TE_AU_MODE where MODEID = 'AU00001';")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""select * from TE_RULE_HISTORY for update""")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            self.expectTrue(str("LockTimeOutException") not in str(statusValue.message), "expect str(statusValue.message) no str(\"LockTimeOutException\")")
            T2.execute("commit")
            T2.wait_finish()
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("select * from TE_RULE_HISTORY for update")
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
            T1.execute("delete from TE_RULE_HISTORY")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from TE_RULE_HISTORY for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""delete from TE_AU_MODE where MODEID = 'AU00001'""")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            self.expectTrue(str("LockTimeOutException") not in str(statusValue.message), "expect str(statusValue.message) no str(\"LockTimeOutException\")")
            T2.execute("commit")
            T2.wait_finish()
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from TE_AU_MODE where MODEID = 'AU00001'")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
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
            T1.execute("delete from TE_AU_MODE where MODEID = 'AU00161'")
            T1.wait_finish()
            T1.execute("delete from TE_RULE_HISTORY")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""INSERT INTO TE_AU_MODE (MODEID,AUTHTYPE,AUTHLEVEL,AUTHLEVELD,AUTHBRNOTYPE,AUTHBRNO,AUTHPOST,URGENTFLAG,AUTHDESC,HXAUTHFLAG,HXAUTHTYPE,REMARK,REMARK1,JZAUTHBNK,JZAUTHLVL) VALUES (
'AU00161','1','1',NULL,NULL,NULL,'GW006',NULL,'本转他：付款账户类型为个人且交易金额大于等于5万',NULL,NULL,NULL,NULL,NULL,NULL);""")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""select * from TE_RULE_HISTORY for update""")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            self.expectTrue(str("LockTimeOutException") not in str(statusValue.message), "expect str(statusValue.message) no str(\"LockTimeOutException\")")
            T2.execute("commit")
            T2.wait_finish()
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("select * from TE_RULE_HISTORY for update")
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
            T1.execute("delete from TE_AU_MODE where MODEID = 'AU00161'")
            T1.wait_finish()
            T1.execute("delete from TE_RULE_HISTORY")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from TE_RULE_HISTORY for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""INSERT INTO TE_AU_MODE (MODEID,AUTHTYPE,AUTHLEVEL,AUTHLEVELD,AUTHBRNOTYPE,AUTHBRNO,AUTHPOST,URGENTFLAG,AUTHDESC,HXAUTHFLAG,HXAUTHTYPE,REMARK,REMARK1,JZAUTHBNK,JZAUTHLVL) VALUES (
'AU00161','1','1',NULL,NULL,NULL,'GW006',NULL,'本转他：付款账户类型为个人且交易金额大于等于5万',NULL,NULL,NULL,NULL,NULL,NULL);""")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            self.expectTrue(str("LockTimeOutException") not in str(statusValue.message), "expect str(statusValue.message) no str(\"LockTimeOutException\")")
            T2.execute("commit")
            T2.wait_finish()
            T1.execute("commit")
            T1.wait_finish()
            T1.execute("delete from TE_RULE_HISTORY")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T2.execute("""INSERT INTO TE_AU_MODE (MODEID,AUTHTYPE,AUTHLEVEL,AUTHLEVELD,AUTHBRNOTYPE,AUTHBRNO,AUTHPOST,URGENTFLAG,AUTHDESC,HXAUTHFLAG,HXAUTHTYPE,REMARK,REMARK1,JZAUTHBNK,JZAUTHLVL) VALUES (
'AU00161','1','1',NULL,NULL,NULL,'GW006',NULL,'本转他：付款账户类型为个人且交易金额大于等于5万',NULL,NULL,NULL,NULL,NULL,NULL);""")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
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
            case_terminal.execute("""CREATE OR REPLACE TRIGGER TE_AU_MODE_TRIG after INSERT
  OR UPDATE OR DELETE ON TRAFODION.LOCK_TRIGGER.TE_AU_MODE FOR EACH ROW AS
    begin
if inserting then /*插入操作时*/
insert into TE_RULE_HISTORY

         values

      (:new.
      MODEID,to_char(systimestamp,'yyyymmddhh24Miss'),'插入','TE_AU
      MODE',
      :new.MODEID||','||:new.AUTHTYPE||','||:new.AUTHLEVEL||','||:new.AUTHLEVELD||','||:new.AUTHBRNOTYPE||','||:new.AUTHBRNO||','||:new.AUTHPOST||','||:new.URGENTFLAG||','||:new.AUTHDESC||','||:new.HXAUTHFLAG||','||:new.HXAUTHTYPE||','||:new.REMARK||','||:new.REMARK1||','||:new.JZAUTHBNK||','||:new.JZAUTHLVL);
            elsif updating then /*更新操作时*/
insert into TE_RULE_HISTORY
            values

      (:old.MODEID,to_char(systimestamp,'yyyymmddhh24Miss'),'更新','TE_AU
      MODE',
      :old.MODEID||','||:old.AUTHTYPE||','||:old.AUTHLEVEL||','||:old.AUTHLEVELD||','||:old.AUTHBRNOTYPE||','||:old.AUTHBRNO||','||:old.AUTHPOST||','||:old.URGENTFLAG||','||:old.AUTHDESC||','||:old.HXAUTHFLAG||','||:old.HXAUTHTYPE||','||:old.REMARK||','||:old.REMARK1||','||:old.JZAUTHBNK||','||:old.JZAUTHLVL);
            elsif deleting then /*删除操作时*/
insert into TE_RULE_HISTORY
            values

      (:old.
      MODEID,to_char(systimestamp,'yyyymmddhh24Miss'),'删除','TE_AU
      MODE',
      :old.MODEID||','||:old.AUTHTYPE||','||:old.AUTHLEVEL||','||:old.AUTHLEVELD||','||:old.AUTHBRNOTYPE||','||:old.AUTHBRNO||','||:old.AUTHPOST||','||:old.URGENTFLAG||','||:old.AUTHDESC||','||:old.HXAUTHFLAG||','||:old.HXAUTHTYPE||','||:old.REMARK||','||:old.REMARK1||','||:old.JZAUTHBNK||','||:old.JZAUTHLVL);
            end if;
end;
/""")
            case_terminal.wait_finish()
            temp_var = case_terminal.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str(0) in str(statusValue.code), "expect str(statusValue.code) has str(0)")
            T1.execute("delete from TE_RULE_HISTORY")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("update TE_AU_MODE set AUTHTYPE = '1' where MODEID = 'AU00001';")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""select * from TE_RULE_HISTORY for update""")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            self.expectTrue(str("LockTimeOutException") not in str(statusValue.message), "expect str(statusValue.message) no str(\"LockTimeOutException\")")
            T2.execute("commit")
            T2.wait_finish()
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("select * from TE_RULE_HISTORY for update")
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
            T1.execute("delete from TE_RULE_HISTORY")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from TE_RULE_HISTORY for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""update TE_AU_MODE set AUTHTYPE = '1' where MODEID = 'AU00001'""")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            self.expectTrue(str("LockTimeOutException") not in str(statusValue.message), "expect str(statusValue.message) no str(\"LockTimeOutException\")")
            T2.execute("commit")
            T2.wait_finish()
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("update TE_AU_MODE set AUTHTYPE = '1' where MODEID = 'AU00001'")
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
            T1.execute("delete from TE_RULE_HISTORY")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("delete from TE_AU_MODE where MODEID = 'AU00001';")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""select * from TE_RULE_HISTORY for update""")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            self.expectTrue(str("LockTimeOutException") not in str(statusValue.message), "expect str(statusValue.message) no str(\"LockTimeOutException\")")
            T2.execute("commit")
            T2.wait_finish()
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("select * from TE_RULE_HISTORY for update")
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
            T1.execute("delete from TE_RULE_HISTORY")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from TE_RULE_HISTORY for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""delete from TE_AU_MODE where MODEID = 'AU00001'""")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            self.expectTrue(str("LockTimeOutException") not in str(statusValue.message), "expect str(statusValue.message) no str(\"LockTimeOutException\")")
            T2.execute("commit")
            T2.wait_finish()
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from TE_AU_MODE where MODEID = 'AU00001'")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
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
            T1.execute("delete from TE_AU_MODE where MODEID = 'AU00161'")
            T1.wait_finish()
            T1.execute("delete from TE_RULE_HISTORY")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""INSERT INTO TE_AU_MODE (MODEID,AUTHTYPE,AUTHLEVEL,AUTHLEVELD,AUTHBRNOTYPE,AUTHBRNO,AUTHPOST,URGENTFLAG,AUTHDESC,HXAUTHFLAG,HXAUTHTYPE,REMARK,REMARK1,JZAUTHBNK,JZAUTHLVL) VALUES (
'AU00161','1','1',NULL,NULL,NULL,'GW006',NULL,'本转他：付款账户类型为个人且交易金额大于等于5万',NULL,NULL,NULL,NULL,NULL,NULL);""")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""select * from TE_RULE_HISTORY for update""")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            self.expectTrue(str("LockTimeOutException") not in str(statusValue.message), "expect str(statusValue.message) no str(\"LockTimeOutException\")")
            T2.execute("commit")
            T2.wait_finish()
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("select * from TE_RULE_HISTORY for update")
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
            T1.execute("delete from TE_AU_MODE where MODEID = 'AU00161'")
            T1.wait_finish()
            T1.execute("delete from TE_RULE_HISTORY")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from TE_RULE_HISTORY for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""INSERT INTO TE_AU_MODE (MODEID,AUTHTYPE,AUTHLEVEL,AUTHLEVELD,AUTHBRNOTYPE,AUTHBRNO,AUTHPOST,URGENTFLAG,AUTHDESC,HXAUTHFLAG,HXAUTHTYPE,REMARK,REMARK1,JZAUTHBNK,JZAUTHLVL) VALUES (
'AU00161','1','1',NULL,NULL,NULL,'GW006',NULL,'本转他：付款账户类型为个人且交易金额大于等于5万',NULL,NULL,NULL,NULL,NULL,NULL);""")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            self.expectTrue(str("LockTimeOutException") not in str(statusValue.message), "expect str(statusValue.message) no str(\"LockTimeOutException\")")
            T2.execute("commit")
            T2.wait_finish()
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("""INSERT INTO TE_AU_MODE (MODEID,AUTHTYPE,AUTHLEVEL,AUTHLEVELD,AUTHBRNOTYPE,AUTHBRNO,AUTHPOST,URGENTFLAG,AUTHDESC,HXAUTHFLAG,HXAUTHTYPE,REMARK,REMARK1,JZAUTHBNK,JZAUTHLVL) VALUES (
'AU00161','1','1',NULL,NULL,NULL,'GW006',NULL,'本转他：付款账户类型为个人且交易金额大于等于5万',NULL,NULL,NULL,NULL,NULL,NULL);""")
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
            case_terminal.execute("""CREATE OR REPLACE TRIGGER TE_AU_MODE_TRIG after INSERT
  OR UPDATE OR DELETE ON TRAFODION.LOCK_TRIGGER.TE_AU_MODE FOR EACH STATEMENT AS
    begin
    INSERT INTO TE_RULE_HISTORY VALUES  ('lock', to_char(SYSDATE,'YYYYMMDDHH24MISS') ,'语句级trigger','TE_AU MODE','AU00161,1,1,,,,GW006,,,,,,,,');
end;
/""")
            case_terminal.wait_finish()
            T1.execute("delete from TE_RULE_HISTORY")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("update TE_AU_MODE set AUTHTYPE = '1' where MODEID = 'AU00001';")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""select * from TE_RULE_HISTORY for update""")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            self.expectTrue(str("LockTimeOutException") not in str(statusValue.message), "expect str(statusValue.message) no str(\"LockTimeOutException\")")
            T2.execute("commit")
            T2.wait_finish()
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("select * from TE_RULE_HISTORY for update")
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
            T1.execute("delete from TE_RULE_HISTORY")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from TE_RULE_HISTORY for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""update TE_AU_MODE set AUTHTYPE = '1' where MODEID = 'AU00001'""")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            self.expectTrue(str("LockTimeOutException") not in str(statusValue.message), "expect str(statusValue.message) no str(\"LockTimeOutException\")")
            T2.execute("commit")
            T2.wait_finish()
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("update TE_AU_MODE set AUTHTYPE = '1' where MODEID = 'AU00001'")
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
            T1.execute("delete from TE_RULE_HISTORY")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("delete from TE_AU_MODE where MODEID = 'AU00001';")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""select * from TE_RULE_HISTORY for update""")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            self.expectTrue(str("LockTimeOutException") not in str(statusValue.message), "expect str(statusValue.message) no str(\"LockTimeOutException\")")
            T2.execute("commit")
            T2.wait_finish()
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("select * from TE_RULE_HISTORY for update")
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
            T1.execute("delete from TE_RULE_HISTORY")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from TE_RULE_HISTORY for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""delete from TE_AU_MODE where MODEID = 'AU00001'""")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            self.expectTrue(str("LockTimeOutException") not in str(statusValue.message), "expect str(statusValue.message) no str(\"LockTimeOutException\")")
            T2.execute("commit")
            T2.wait_finish()
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from TE_AU_MODE where MODEID = 'AU00001'")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
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
            T1.execute("delete from TE_AU_MODE where MODEID = 'AU00161'")
            T1.wait_finish()
            T1.execute("delete from TE_RULE_HISTORY")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""INSERT INTO TE_AU_MODE (MODEID,AUTHTYPE,AUTHLEVEL,AUTHLEVELD,AUTHBRNOTYPE,AUTHBRNO,AUTHPOST,URGENTFLAG,AUTHDESC,HXAUTHFLAG,HXAUTHTYPE,REMARK,REMARK1,JZAUTHBNK,JZAUTHLVL) VALUES (
'AU00161','1','1',NULL,NULL,NULL,'GW006',NULL,'本转他：付款账户类型为个人且交易金额大于等于5万',NULL,NULL,NULL,NULL,NULL,NULL);""")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""select * from TE_RULE_HISTORY for update""")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            self.expectTrue(str("LockTimeOutException") not in str(statusValue.message), "expect str(statusValue.message) no str(\"LockTimeOutException\")")
            T2.execute("commit")
            T2.wait_finish()
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("select * from TE_RULE_HISTORY for update")
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
            T1.execute("delete from TE_AU_MODE where MODEID = 'AU00161'")
            T1.wait_finish()
            T1.execute("delete from TE_RULE_HISTORY")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from TE_RULE_HISTORY for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""INSERT INTO TE_AU_MODE (MODEID,AUTHTYPE,AUTHLEVEL,AUTHLEVELD,AUTHBRNOTYPE,AUTHBRNO,AUTHPOST,URGENTFLAG,AUTHDESC,HXAUTHFLAG,HXAUTHTYPE,REMARK,REMARK1,JZAUTHBNK,JZAUTHLVL) VALUES (
'AU00161','1','1',NULL,NULL,NULL,'GW006',NULL,'本转他：付款账户类型为个人且交易金额大于等于5万',NULL,NULL,NULL,NULL,NULL,NULL);""")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            self.expectTrue(str("LockTimeOutException") not in str(statusValue.message), "expect str(statusValue.message) no str(\"LockTimeOutException\")")
            T2.execute("commit")
            T2.wait_finish()
            T1.execute("commit")
            T1.wait_finish()
            T1.execute("delete from TE_RULE_HISTORY")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T2.execute("""INSERT INTO TE_AU_MODE (MODEID,AUTHTYPE,AUTHLEVEL,AUTHLEVELD,AUTHBRNOTYPE,AUTHBRNO,AUTHPOST,URGENTFLAG,AUTHDESC,HXAUTHFLAG,HXAUTHTYPE,REMARK,REMARK1,JZAUTHBNK,JZAUTHLVL) VALUES (
'AU00161','1','1',NULL,NULL,NULL,'GW006',NULL,'本转他：付款账户类型为个人且交易金额大于等于5万',NULL,NULL,NULL,NULL,NULL,NULL);""")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
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
            case_terminal.execute("""CREATE OR REPLACE TRIGGER TE_AU_MODE_TRIG before INSERT
  OR UPDATE OR DELETE ON TRAFODION.LOCK_TRIGGER.TE_AU_MODE FOR EACH STATEMENT AS
    begin
    INSERT INTO TE_RULE_HISTORY VALUES  ('lock', to_char(SYSDATE,'YYYYMMDDHH24MISS') ,'语句级trigger','TE_AU MODE','AU00161,1,1,,,,GW006,,,,,,,,');
end;
/""")
            case_terminal.wait_finish()
            temp_var = case_terminal.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str(0) in str(statusValue.code), "expect str(statusValue.code) has str(0)")
            T1.execute("delete from TE_RULE_HISTORY")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("update TE_AU_MODE set AUTHTYPE = '1' where MODEID = 'AU00001';")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""select * from TE_RULE_HISTORY for update""")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            self.expectTrue(str("LockTimeOutException") not in str(statusValue.message), "expect str(statusValue.message) no str(\"LockTimeOutException\")")
            T2.execute("commit")
            T2.wait_finish()
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("select * from TE_RULE_HISTORY for update")
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
            T1.execute("delete from TE_RULE_HISTORY")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from TE_RULE_HISTORY for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""update TE_AU_MODE set AUTHTYPE = '1' where MODEID = 'AU00001'""")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            self.expectTrue(str("LockTimeOutException") not in str(statusValue.message), "expect str(statusValue.message) no str(\"LockTimeOutException\")")
            T2.execute("commit")
            T2.wait_finish()
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("update TE_AU_MODE set AUTHTYPE = '1' where MODEID = 'AU00001'")
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
            T1.execute("delete from TE_RULE_HISTORY")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("delete from TE_AU_MODE where MODEID = 'AU00001';")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""select * from TE_RULE_HISTORY for update""")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            self.expectTrue(str("LockTimeOutException") not in str(statusValue.message), "expect str(statusValue.message) no str(\"LockTimeOutException\")")
            T2.execute("commit")
            T2.wait_finish()
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("select * from TE_RULE_HISTORY for update")
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
            T1.execute("delete from TE_RULE_HISTORY")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from TE_RULE_HISTORY for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""delete from TE_AU_MODE where MODEID = 'AU00001'""")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            self.expectTrue(str("LockTimeOutException") not in str(statusValue.message), "expect str(statusValue.message) no str(\"LockTimeOutException\")")
            T2.execute("commit")
            T2.wait_finish()
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("delete from TE_AU_MODE where MODEID = 'AU00001'")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR 30052") not in str(statusValue.message), "expect str(statusValue.message) no str(\"ERROR 30052\")")
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
            T1.execute("delete from TE_AU_MODE where MODEID = 'AU00161'")
            T1.wait_finish()
            T1.execute("delete from TE_RULE_HISTORY")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("""INSERT INTO TE_AU_MODE (MODEID,AUTHTYPE,AUTHLEVEL,AUTHLEVELD,AUTHBRNOTYPE,AUTHBRNO,AUTHPOST,URGENTFLAG,AUTHDESC,HXAUTHFLAG,HXAUTHTYPE,REMARK,REMARK1,JZAUTHBNK,JZAUTHLVL) VALUES (
'AU00161','1','1',NULL,NULL,NULL,'GW006',NULL,'本转他：付款账户类型为个人且交易金额大于等于5万',NULL,NULL,NULL,NULL,NULL,NULL);""")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""select * from TE_RULE_HISTORY for update""")
            T2.store_result("scope_term_result")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            self.expectTrue(str("LockTimeOutException") not in str(statusValue.message), "expect str(statusValue.message) no str(\"LockTimeOutException\")")
            T2.execute("commit")
            T2.wait_finish()
            T1.execute("rollback")
            T1.wait_finish()
            T2.execute("select * from TE_RULE_HISTORY for update")
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
            T1.execute("delete from TE_AU_MODE where MODEID = 'AU00161'")
            T1.wait_finish()
            T1.execute("delete from TE_RULE_HISTORY")
            T1.wait_finish()
            T1.execute("begin work")
            T1.wait_finish()
            T1.execute("select * from TE_RULE_HISTORY for update")
            T1.store_result("scope_term_result")
            T1.wait_finish()
            T2.execute("begin work")
            T2.wait_finish()
            T2.execute("""INSERT INTO TE_AU_MODE (MODEID,AUTHTYPE,AUTHLEVEL,AUTHLEVELD,AUTHBRNOTYPE,AUTHBRNO,AUTHPOST,URGENTFLAG,AUTHDESC,HXAUTHFLAG,HXAUTHTYPE,REMARK,REMARK1,JZAUTHBNK,JZAUTHLVL) VALUES (
'AU00161','1','1',NULL,NULL,NULL,'GW006',NULL,'本转他：付款账户类型为个人且交易金额大于等于5万',NULL,NULL,NULL,NULL,NULL,NULL);""")
            T2.wait_finish()
            temp_var = T2.get_last_execution_result()
            statusValue = temp_var
            self.expectTrue(str("ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR") in str(statusValue.message), "expect str(statusValue.message) has str(\"ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR\")")
            self.expectTrue(str("LockTimeOutException") not in str(statusValue.message), "expect str(statusValue.message) no str(\"LockTimeOutException\")")
            T2.execute("commit")
            T2.wait_finish()
            T1.execute("commit")
            T1.wait_finish()
            T2.execute("""INSERT INTO TE_AU_MODE (MODEID,AUTHTYPE,AUTHLEVEL,AUTHLEVELD,AUTHBRNOTYPE,AUTHBRNO,AUTHPOST,URGENTFLAG,AUTHDESC,HXAUTHFLAG,HXAUTHTYPE,REMARK,REMARK1,JZAUTHBNK,JZAUTHLVL) VALUES (
'AU00161','1','1',NULL,NULL,NULL,'GW006',NULL,'本转他：付款账户类型为个人且交易金额大于等于5万',NULL,NULL,NULL,NULL,NULL,NULL);""")
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
    unittest.TextTestRunner(verbosity=1).run(su)
