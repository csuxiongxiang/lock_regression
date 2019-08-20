Config
{
    """
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
    """
}

TestCase CASE000
{
# Create common tables required for the test
statusValue=:"drop schema S_LOCKREGRESSION cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
:"cleanup schema S_LOCKREGRESSION";
:"create schema  if not exists S_LOCKREGRESSION";
:"set schema S_LOCKREGRESSION";

:"drop table dept cascade";
:"CREATE TABLE dept(deptno DECIMAL(2) not null primary key, dname VARCHAR(14),loc VARCHAR(13))";
:"showddl dept";
:"INSERT INTO dept VALUES(10, 'ACCOUNTING', 'NEW YORK')";
:"INSERT INTO dept VALUES(20, 'RESEARCH', 'DALLAS')";
:"INSERT INTO dept VALUES(30, 'SALES', 'CHICAGO')";
:"INSERT INTO dept VALUES(40, 'OPERATIONS', 'BOSTON')";

t2rs1 =:ResultSet("select * from dept where deptno = 10 for update");
expect_equal(t2rs1, Tuple("((10,'ACCOUNTING','NEW YORK'),)"));

:"drop table employee cascade";
:"""CREATE TABLE employee
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
""";

:"INSERT INTO employee VALUES(7369, 'SMITH', 'CLERK', 7902, DATE '1980-12-17', 800, NULL, 20)";
:"INSERT INTO employee VALUES(7499, 'ALLEN', 'SALESMAN', 7698, DATE '1981-02-20', 1600, 300, 30)";
:"INSERT INTO employee VALUES(7521, 'WARD', 'SALESMAN', 7698, DATE '1981-02-22', 1250, 500, 30)";
:"INSERT INTO employee VALUES(7566, 'JONES', 'MANAGER', 7839, DATE '1981-04-02', 2975, NULL, 20)";
:"INSERT INTO employee VALUES(7654, 'MARTIN', 'SALESMAN', 7698, DATE '1981-09-28', 1250, 1400, 30)";
:"INSERT INTO employee VALUES(7698, 'BLAKE', 'MANAGER', 7839, DATE '1981-05-01', 2850, NULL, 30)";
:"INSERT INTO employee VALUES(7782, 'CLARK', 'MANAGER', 7839, DATE '1981-07-09', 2450, NULL, 10)";
:"INSERT INTO employee VALUES(7788, 'TAC-MD', 'ANALYST', 7566, DATE '1982-12-09', 3000, NULL, 20)";
:"INSERT INTO employee VALUES(7839, 'KING', 'PRESIDENT', 7788, DATE '1981-11-17', 5000, NULL, 10)";
:"INSERT INTO employee VALUES(7844, 'TURNER', 'SALESMAN', 7698, DATE '1981-09-08', 1500, 0, 30)";
:"INSERT INTO employee VALUES(7876, 'ADAMS', 'CLERK', 7788, DATE '1983-01-12', 1100, NULL, 20)";
:"INSERT INTO employee VALUES(7900, 'JAMES', 'CLERK', 7698, DATE '1981-12-03', 950, NULL, 30)";
:"INSERT INTO employee VALUES(7902, 'FORD', 'ANALYST', 7566, DATE '1981-12-03', 3000, NULL, 20)";
:"INSERT INTO employee VALUES(7934, 'MILLER', 'CLERK', 7782, DATE '1982-01-23', 1300, NULL, 10)";
:"create index employee_index on employee(employeeno)";
:"select * from employee";

:"drop table salgrade cascade";
:"""CREATE TABLE salgrade
   (grade DECIMAL primary key,
    losal DECIMAL,
    hisal DECIMAL)""";

:"showddl salgrade";

:"INSERT INTO salgrade VALUES(1, 700, 1200)";
:"INSERT INTO salgrade VALUES(2, 1201, 1400)";
:"INSERT INTO salgrade VALUES(3, 1401, 2000)";
:"INSERT INTO salgrade VALUES(4, 2001, 3000)";
:"INSERT INTO salgrade VALUES(5, 3001, 9999)";

:"SELECT * FROM salgrade";

# large table
:"create table largetable(id int not null primary key, name varchar(20))";
:"upsert using load into largetable select element, cast('lock' || element as varchar(20)) from udf(series(1,150))";

}

 TestCase CASE001
 {
     # IS lock should block X lock for read committed level, Hbase.get / delete   TABLE_LOCK
 Terminal T1 T2;
 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table emp_temp like  employee";
 T1: "insert into emp_temp select * from employee";

 T1: "begin work";
 t1rs1 = T1:ResultSet("select employeeno, ename, job  from emp_temp where employeeno=7788");

 T2: "begin work";
 statusValue = T2:"drop table emp_temp";
 expect_equal(statusValue.code, 30052);
 expect_substr(statusValue.message, "LOCK TIMEOUT ERROR");

 T1: "commit";

 T2: "begin work";
 t2rs1 = T2:ResultSet("select employeeno, ename, job from emp_temp where employeeno=7788");
 expect_equal(t1rs1, t2rs1);

 }

 TestCase CASE002
 {
     # IS lock should block X lock for read committed level . hbase.scan/delete   TABLE_LOCK
 Terminal T1 T2;
 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table emp_temp like  employee";
 T1: "insert into emp_temp select * from employee";

 T1: "begin work";
 t1rs1 = T1:ResultSet("select employeeno, ename, job  from emp_temp");

 T2: "begin work";
 statusValue = T2:"drop table emp_temp";
 expect_equal(statusValue.code, 30052);
 expect_substr(statusValue.message, "LOCK TIMEOUT ERROR");

 T1: "commit";

 T2: "begin work";
 t2rs1 = T2:ResultSet("select employeeno, ename, job from emp_temp");
 expect_equal(t1rs1, t2rs1);
 T2: "commit";

 }

 TestCase CASE003
 {
     # IS lock should block X lock for read committed level . hbase.scan/delete /  part of rows  TABLE_LOCK
 Terminal T1 T2;
 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table emp_temp like  employee";
 T1: "insert into emp_temp select * from employee";

 T1: "begin work";
 t1rs1 = T1:ResultSet("select * from emp_temp where employeeno >=7839 and employeeno<=7902");

 T2: "begin work";
 statusValue = T2:"drop table emp_temp";
 expect_equal(statusValue.code, 30052);
 expect_substr(statusValue.message, "LOCK TIMEOUT ERROR");

 T1: "commit";

 T2: "begin work";
 t2rs1 = T2:ResultSet("select * from emp_temp where employeeno >=7839 and employeeno<=7902");
 expect_equal(t1rs1, t2rs1);
 T2: "commit";

 }

 TestCase CASE004
 {
     # IS lock should  block X lock(dml) for read committed level. hbase.get  TABLE_LOCK  - no primary key
 Terminal T1 T2;
 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table emp_temp as select * from employee";

 T1: "begin work";
 T1: "select * from emp_temp where employeeno = 7788";

 T2: "begin work";
 statusValue = T2:"select * from emp_temp for update";
 expect_equal(statusValue.code, 30052);
 expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

 T1: "commit";
 T2: "commit";

 }

 TestCase CASE005
 {
     # IS lock should  block X lock(dml) for read committed level. hbase.get  TABLE_LOCK  - no primary key
 Terminal T1 T2;
 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table emp_temp as select * from employee";

 T1: "begin work";
 T1: "select * from emp_temp";

 T2: "begin work";
 statusValue = T2:"select * from emp_temp for update";

 expect_equal(statusValue.code, 30052);
 expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

 T1: "commit";
 T2: "commit";

 }

 TestCase CASE006
 {
     # IS lock should not block X  lock for read committed level, hbase.scan part of rows, no primary key
 Terminal T1 T2;
 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table emp_temp as select * from employee";

 T1: "begin work";
 T1: "select * from emp_temp where employeeno >=7566 and employeeno<=7788";

 T2: "begin work";
 statusValue = T2:"select * from emp_temp  for update";

 expect_equal(statusValue.code, 30052);
 expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

 T1: "commit";
 T2: "commit";

 }

 TestCase CASE007
 {
     # IS lock should  block X lock(dml) for read committed level. hbase.get  TABLE_LOCK  - contain primary key
 Terminal T1 T2;
 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table  emp_temp like employee";
 T1: "insert into emp_temp select * from employee";

 T1: "begin work";
 T1: "select * from emp_temp where employeeno = 7788";

 T2: "begin work";
 statusValue = T2:"select * from emp_temp for update";
 expect_equal(statusValue.code, 30052);
 expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

 T1: "commit";
 T2: "commit";

 }

 TestCase CASE008
 {
     # IS lock should  block X lock(dml) for read committed level. hbase.get  TABLE_LOCK  - no primary key
 Terminal T1 T2;
 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table  emp_temp like employee";
 T1: "insert into emp_temp select * from employee";

 T1: "begin work";
 T1: "select * from emp_temp";

 T2: "begin work";
 statusValue = T2:"select * from emp_temp for update";

 expect_equal(statusValue.code, 30052);
 expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

 T1: "commit";
 T2: "commit";

 }

 TestCase CASE009
 {
     # IS lock should not block X  lock for read committed level, hbase.scan part of rows, no primary key
 Terminal T1 T2;
 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table  emp_temp like employee";
 T1: "insert into emp_temp select * from employee";

 T1: "begin work";
 T1: "select * from emp_temp where employeeno >=7566 and employeeno<=7788";

 T2: "begin work";
 statusValue = T2:"select * from emp_temp  for update";

 expect_equal(statusValue.code, 30052);
 expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

 T1: "commit";
 T2: "commit";

 }

 TestCase CASE010
 {
     # IS lock should't block IX lock for read committed level, Hbase.get / delete  TABLE_LOCK  no pk
 Terminal T1 T2;
 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table emp_temp as select * from employee";

 T1: "begin work";
 T1: "select employeeno, ename, job  from emp_temp where employeeno=7788";

 T2: "begin work";
 statusValue = T2:"delete from emp_temp where employeeno = 7788";
 expect_equal(statusValue.code, 0);

 T1: "commit";
 T2: "rollback";

 # s-lock 1 row, but x-lock full table
 T1: "begin work";
 t1rs1 = T1:ResultSet("select employeeno, ename, job  from emp_temp where employeeno=7788");

 T2: "begin work";
 statusValue = T2:"delete from emp_temp";
 expect_equal(statusValue.code, 0);

 T1: "commit";
 T2: "rollback";

 }

 TestCase CASE011
 {
     # IS lock should block X lock for read committed level . hbase.scan/delete TABLE_LOCK  - no pk
 Terminal T1 T2;
 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table emp_temp as select * from employee";

 T1: "begin work";
 T1: "select employeeno, ename, job  from emp_temp";

 T2: "begin work";
 statusValue = T2:"delete from emp_temp";
 expect_equal(statusValue.code, 0);

 T1: "commit";
 T2: "rollback";

 # s-lock table , but x-lock 1 rows
 T1: "begin work";
 T1: "select employeeno, ename, job  from emp_temp";

 T2: "begin work";
 statusValue = T2:"delete from emp_temp  where employeeno=7788";
 expect_equal(statusValue.code, 0);

 T1: "commit";
 T2: "rollback";

 }

 TestCase CASE012
 {
     # IS lock should block X lock for read committed level . hbase.scan/delete /  part of rows TABLE_LOCK  -no pk
 Terminal T1 T2;
 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table emp_temp as select * from employee";

 T1: "begin work";
 T1: "select * from emp_temp where employeeno >=7839 and employeeno<=7902";

 T2: "begin work";
 statusValue = T2:"delete from emp_temp where employeeno >=7839 and employeeno<=7902";
 expect_equal(statusValue.code, 0);

 T1: "commit";
 T2: "rollback";

 # s-lock part of rows , but x-lock full table
 T1: "begin work";
 t1rs1 = T1:ResultSet("select * from emp_temp where employeeno >=7839 and employeeno<=7902");

 T2: "begin work";
 statusValue = T2:"delete from emp_temp";
 expect_equal(statusValue.code, 0);

 T1: "commit";
 T2: "rollback";
 }

 TestCase CASE013
 {
     # IS lock should't block IX lock for read committed level, Hbase.get / delete  TABLE_LOCK -pk
 Terminal T1 T2;
 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table  emp_temp like employee";
 T1: "insert into emp_temp select * from employee";

 T1: "begin work";
 T1: "select employeeno, ename, job  from emp_temp where employeeno=7788";

 T2: "begin work";
 statusValue = T2:"delete from emp_temp where employeeno = 7788";
 expect_equal(statusValue.code, 0);

 T1: "commit";
 T2: "rollback";

 # s-lock 1 row, but x-lock full table
 T1: "begin work";
 t1rs1 = T1:ResultSet("select employeeno, ename, job  from emp_temp where employeeno=7788");

 T2: "begin work";
 statusValue = T2:"delete from emp_temp";
 expect_equal(statusValue.code, 0);

 T1: "commit";
 T2: "rollback";

 }

 TestCase CASE014
 {
     # IS lock should block X lock for read committed level . hbase.scan/delete TABLE_LOCK  -pk
 Terminal T1 T2;
 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table  emp_temp like employee";
 T1: "insert into emp_temp select * from employee";

 T1: "begin work";
 T1: "select employeeno, ename, job  from emp_temp";

 T2: "begin work";
 statusValue = T2:"delete from emp_temp";
 expect_equal(statusValue.code, 0);

 T1: "commit";
 T2: "rollback";

 # s-lock table , but x-lock 1 rows
 T1: "begin work";
 T1: "select employeeno, ename, job  from emp_temp";

 T2: "begin work";
 statusValue = T2:"delete from emp_temp  where employeeno=7788";
 expect_equal(statusValue.code, 0);

 T1: "commit";
 T2: "rollback";

 }

 TestCase CASE015
 {
     # IS lock should block X lock for read committed level . hbase.scan/delete /  part of rows TABLE_LOCK  -pk
 Terminal T1 T2;
 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table  emp_temp like employee";
 T1: "insert into emp_temp select * from employee";

 T1: "begin work";
 T1: "select * from emp_temp where employeeno >=7839 and employeeno<=7902";

 T2: "begin work";
 statusValue = T2:"delete from emp_temp where employeeno >=7839 and employeeno<=7902";
 expect_equal(statusValue.code, 0);

 T1: "commit";
 T2: "rollback";

 # s-lock part of rows , but x-lock full table
 T1: "begin work";
 t1rs1 = T1:ResultSet("select * from emp_temp where employeeno >=7839 and employeeno<=7902");

 T2: "begin work";
 statusValue = T2:"delete from emp_temp";
 expect_equal(statusValue.code, 0);

 T1: "commit";
 T2: "rollback";
 }

 TestCase CASE016
 {
     # IS lock should not block IS lock. HBASE:GET TABLE_LOCK  -no pk
     # start transaction
 Terminal T1 T2;
 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table emp_temp as select * from employee";

 T1: "begin work";
 t1rs1 = T1:ResultSet("select * from emp_temp where employeeno = 7788");
 t1rs2 = T1:ResultSet("select employeeno, ename, job from emp_temp where ename = 'TAC-MD'");

 T2: "begin work";
 t2rs1 = T2:ResultSet("select * from emp_temp where employeeno = 7788");
 t2rs2 = T2:ResultSet("select employeeno, ename, job from emp_temp where ename = 'TAC-MD'");

 expect_equal(t1rs1, t2rs1);
 expect_equal(t1rs2, t2rs2);

 T1: "commit";
 T2: "commit";

 }

 TestCase CASE017
 {
     # IS lock should not block IS lock. HBASE:SCAN TABLE_LOCK, no pk
 Terminal T1 T2;
 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table emp_temp as select * from employee";

 T1: "begin work";
 t1rs1 = T1:ResultSet("select * from emp_temp");
 t1rs2 = T1:ResultSet("select employeeno, ename, job from emp_temp");

 T2: "begin work";
 t2rs1 = T2:ResultSet("select * from emp_temp");
 t2rs2 = T2:ResultSet("select employeeno, ename, job from emp_temp");

 expect_equal(t1rs1, t2rs1);

 T1: "commit";
 T2: "commit";

 }

 TestCase CASE018
 {
     # IS lock should not block IS lock. HBASE:SCAN part of rows TABLE_LOCK  no pk
 Terminal T1 T2;
 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table emp_temp as select * from employee";

 T1: "begin work";
 t1rs1 = T1:ResultSet("select * from emp_temp where employeeno >=7566 and employeeno<=7788");
 t1rs2 = T1:ResultSet("select employeeno, ename,job from emp_temp where employeeno >=7839 and employeeno<=7902");

 T2: "begin work";
 t2rs1 = T2:ResultSet("select * from emp_temp where employeeno >=7566 and employeeno<=7788");
 t2rs2 = T2:ResultSet("select employeeno, ename,job from emp_temp where employeeno >=7839 and employeeno<=7902");

 expect_equal(t1rs1, t2rs1);

 T1: "commit";
 T2: "commit";

 }

 TestCase CASE019
 {
     # IS lock should not block IS lock. HBASE:GET TABLE_LOCK  -pk
     # start transaction
 Terminal T1 T2;
 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table  emp_temp like employee";
 T1: "insert into emp_temp select * from employee";

 T1: "begin work";
 t1rs1 = T1:ResultSet("select * from emp_temp where employeeno = 7788");
 t1rs2 = T1:ResultSet("select employeeno, ename, job from emp_temp where ename = 'TAC-MD'");

 T2: "begin work";
 t2rs1 = T2:ResultSet("select * from emp_temp where employeeno = 7788");
 t2rs2 = T2:ResultSet("select employeeno, ename, job from emp_temp where ename = 'TAC-MD'");

 expect_equal(t1rs1, t2rs1);
 expect_equal(t1rs2, t2rs2);

 T1: "commit";
 T2: "commit";

 }

 TestCase CASE020
 {
     # IS lock should not block IS lock. HBASE:SCAN TABLE_LOCK,  pk
 Terminal T1 T2;
 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table  emp_temp like employee";
 T1: "insert into emp_temp select * from employee";

 T1: "begin work";
 t1rs1 = T1:ResultSet("select * from emp_temp");
 t1rs2 = T1:ResultSet("select employeeno, ename, job from emp_temp");

 T2: "begin work";
 t2rs1 = T2:ResultSet("select * from emp_temp");
 t2rs2 = T2:ResultSet("select employeeno, ename, job from emp_temp");

 expect_equal(t1rs1, t2rs1);

 T1: "commit";
 T2: "commit";

 }

 TestCase CASE021
 {
     # IS lock should not block IS lock. HBASE:SCAN part of rows TABLE_LOCK  pk
 Terminal T1 T2;
 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table  emp_temp like employee";
 T1: "insert into emp_temp select * from employee";

 T1: "begin work";
 t1rs1 = T1:ResultSet("select * from emp_temp where employeeno >=7566 and employeeno<=7788");
 t1rs2 = T1:ResultSet("select employeeno, ename,job from emp_temp where employeeno >=7839 and employeeno<=7902");

 T2: "begin work";
 t2rs1 = T2:ResultSet("select * from emp_temp where employeeno >=7566 and employeeno<=7788");
 t2rs2 = T2:ResultSet("select employeeno, ename,job from emp_temp where employeeno >=7839 and employeeno<=7902");

 expect_equal(t1rs1, t2rs1);

 T1: "commit";
 T2: "commit";

 }

 TestCase CASE022
 {
     # IX lock should block X lock for read committed level, hbase.delete  1 row table lock -no pk
 Terminal T1 T2;
 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table emp_temp as select * from employee";

 T1: "begin work";
 T1: "delete from emp_temp where employeeno =7788";

 T2: "begin work";
 statusValue = T2:"drop table emp_temp";
 expect_equal(statusValue.code, 30052);

 T1: "commit";
 T2: "commit";

 }

 TestCase CASE023
 {
     # IX lock should block X lock for read committed level, hbase.delete  full table  table lock  -no pk
 Terminal T1 T2;
 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table emp_temp as select * from employee";

 T1: "begin work";
 T1: "delete from emp_temp";

 T2: "begin work";
 statusValue = T2:"drop table emp_temp";
 expect_equal(statusValue.code, 30052);

 T1: "commit";
 T2: "commit";

 }

 TestCase CASE024
 {
     # IX lock should block X lock for read committed level, hbase.delete  part of rows  TABLE_LOCK -no pk
 Terminal T1 T2;
 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table emp_temp as select * from employee";

 T1: "begin work";
 T1: "delete from emp_temp  where employeeno >=7839 and employeeno<=7902";

 T2: "begin work";
 statusValue = T2:"drop table emp_temp";
 expect_equal(statusValue.code, 30052);

 T1: "commit";
 T2: "commit";

 }

 TestCase CASE025
 {
     # IX lock should block X lock for read committed level, hbase.delete  1 row table lock -pk
 Terminal T1 T2;
 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table emp_temp like  employee";
 T1: "insert into emp_temp select * from employee";

 T1: "begin work";
 T1: "delete from emp_temp where employeeno =7788";

 T2: "begin work";
 statusValue = T2:"drop table emp_temp";
 expect_equal(statusValue.code, 30052);

 T1: "commit";
 T2: "commit";

 }

 TestCase CASE026
 {
     # IX lock should block X lock for read committed level, hbase.delete  full table  table lock  -pk
 Terminal T1 T2;
 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table emp_temp like  employee";
 T1: "insert into emp_temp select * from employee";

 T1: "begin work";
 T1: "delete from emp_temp";

 T2: "begin work";
 statusValue = T2:"drop table emp_temp";
 expect_equal(statusValue.code, 30052);

 T1: "commit";
 T2: "commit";

 }

 TestCase CASE027
 {
     # IX lock should block X lock for read committed level, hbase.delete  part of rows  TABLE_LOCK -pk
 Terminal T1 T2;
 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table emp_temp like  employee";
 T1: "insert into emp_temp select * from employee";

 T1: "begin work";
 T1: "delete from emp_temp  where employeeno >=7839 and employeeno<=7902";

 T2: "begin work";
 statusValue = T2:"drop table emp_temp";
 expect_equal(statusValue.code, 30052);

 T1: "commit";
 T2: "commit";

 }


 TestCase CASE028
 {
     # IX lock should not block IX lock for read committed level, hbase.delete  1 row  -no primary key
 Terminal T1 T2;
 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table emp_temp as select * from employee";

 T1: "begin work";
 T1: "delete from emp_temp where employeeno =7788";

 T2: "begin work";
 statusValue = T2:"delete from emp_temp where employeeno = 7902";
 expect_equal(statusValue.code, 0);

 T1: "commit";
 T2: "commit";

 }


 TestCase CASE029
 {
     # IX lock should not block IX lock for read committed level, hbase.delete  1 row  -primary key
 Terminal T1 T2;
 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table emp_temp like  employee";
 T1: "insert into emp_temp select * from employee";

 T1: "begin work";
 T1: "delete from emp_temp where employeeno =7788";

 T2: "begin work";
 statusValue = T2:"delete from emp_temp where employeeno = 7902";
 expect_equal(statusValue.code, 0);

 T1: "commit";
 T2: "commit";

 }

 TestCase CASE030
 {
     # IX lock should not block IX lock for read committed level, hbase.delete  part of rows - no primary key
 Terminal T1 T2;
 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table emp_temp as select * from employee";

 T1: "begin work";
 T1: "delete from emp_temp  where employeeno >=7839 ";

 T2: "begin work";
 statusValue = T2:"delete from emp_temp  where employeeno <7839";
 expect_equal(statusValue.code, 0);

 T1: "commit";
 T2: "commit";
 }

 TestCase CASE031
 {
     # IX lock should not block IX lock for read committed level, hbase.delete  part of rows - primary key
 Terminal T1 T2;
 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table emp_temp like  employee";
 T1: "insert into emp_temp select * from employee";

 T1: "begin work";
 T1: "delete from emp_temp  where employeeno >=7839 ";

 T2: "begin work";
 statusValue = T2:"delete from emp_temp  where employeeno <7839";
 expect_equal(statusValue.code, 0);

 T1: "commit";
 T2: "commit";
 }

 TestCase CASE032
 {
     # IX lock should block IS lock for read committed level  delete/get   TABLE_LOCK  -no primary key
 Terminal T1 T2;
 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table emp_temp as select * from employee";

 t1rs1 = T1:ResultSet("select * from emp_temp where employeeno =7902");
 T1: "begin work";
 T1: "delete from emp_temp where employeeno = 7788";

 T2: "begin work";
 statusValue = T2:"select * from emp_temp where employeeno =7902";
 expect_equal(statusValue.code, 0);

 t2rs1 = T2:ResultSet("select * from emp_temp where employeeno =7902");

 T1: "commit";
 expect_equal(t1rs1, t2rs1);
 T2: "commit";

 }

 TestCase CASE033
 {
     # IX lock should block IS lock for read committed level  delete/scan. part of rows   TABLE_LOCK  -- no primary key
 Terminal T1 T2;
 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table emp_temp as select * from employee";

 t1rs1 = T1:ResultSet("select * from emp_temp where employeeno >=7839");
 T1: "begin work";
 T1: "delete from emp_temp where employeeno < 7839";

 T2: "begin work";
 statusValue = T2:"select * from emp_temp where employeeno >=7839";
 expect_equal(statusValue.code, 0);

 t2rs1 = T2:ResultSet("select * from emp_temp where employeeno >=7839");

 T1: "commit";
 expect_equal(t1rs1, t2rs1);
 T2: "commit";

 }

 TestCase CASE034
 {
     # IX lock should block IS lock for read committed level  delete/get   TABLE_LOCK pk
 Terminal T1 T2;
 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table emp_temp like  employee";
 T1: "insert into emp_temp select * from employee";

 t1rs1 = T1:ResultSet("select * from emp_temp where employeeno =7902");
 T1: "begin work";
 T1: "delete from emp_temp where employeeno = 7788";

 T2: "begin work";
 statusValue = T2:"select * from emp_temp where employeeno =7902";
 expect_equal(statusValue.code, 0);

 t2rs1 = T2:ResultSet("select * from emp_temp where employeeno =7902");

 T1: "commit";
 expect_equal(t1rs1, t2rs1);
 T2: "commit";

 }

 TestCase CASE035
 {
     # IX lock should block IS lock for read committed level  delete/scan. part of rows   TABLE_LOCK -pk
 Terminal T1 T2;
 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table emp_temp like  employee";
 T1: "insert into emp_temp select * from employee";

 t1rs1 = T1:ResultSet("select * from emp_temp where employeeno >=7839");
 T1: "begin work";
 T1: "delete from emp_temp where employeeno < 7839";

 T2: "begin work";
 statusValue = T2:"select * from emp_temp where employeeno >=7839";
 expect_equal(statusValue.code, 0);

 t2rs1 = T2:ResultSet("select * from emp_temp where employeeno >=7839");

 T1: "commit";
 expect_equal(t1rs1, t2rs1);
 T2: "commit";

 }

 TestCase CASE036
 {
     # U lock should block X lock for read committed level, HBASE get/delete   ROW_LOCK  no pk
 Terminal T1 T2;

 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table emp_temp as select * from employee";

 T1: "begin work";
 t1rs1 = T1:ResultSet("select * from emp_temp where employeeno = 7788 for update");
 # if not contain pk, will lock region

 T2: "begin work";
 statusValue = T2:"delete from emp_temp where employeeno =7788";
 expect_equal(statusValue.code, 30052);
 expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

 statusValue = T2:"delete from emp_temp";
 expect_equal(statusValue.code, 30052);
 expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

 statusValue = T2:"delete from emp_temp where employeeno !=7788";
 expect_equal(statusValue.code, 30052);
 expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

 T1: "commit";

 T2: "begin work";
 t2rs1 = T2:ResultSet("select * from emp_temp where employeeno = 7788 for update");

 T2: "commit";

 }

 TestCase CASE037
 {
     # U lock should block X lock for read committed level, HBASE get/delete   ROW_LOCK  -pk
 Terminal T1 T2;

 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table emp_temp like  employee";
 T1: "insert into emp_temp select * from employee";

 T1: "begin work";
 t1rs1 = T1:ResultSet("select * from emp_temp where employeeno = 7788 for update");

 T2: "begin work";
 statusValue = T2:"delete from emp_temp where employeeno =7788";
 expect_equal(statusValue.code, 30052);
 expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

 statusValue = T2:"delete from emp_temp";
 expect_equal(statusValue.code, 30052);
 expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

 statusValue = T2:"delete from emp_temp where employeeno !=7788";
 expect_equal(statusValue.code, 0);

 T1: "commit";

 T2: "begin work";
 t2rs1 = T2:ResultSet("select * from emp_temp where employeeno = 7788 for update");
 expect_equal(t1rs1, t2rs1);
 T2: "commit";

 }

 TestCase CASE038
 {
     # X lock should block X lock for read committed level, HBASE scan/delete  TABLE_LOCK
 Terminal T1 T2;
 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table emp_temp like  employee";
 T1: "insert into emp_temp select * from employee";

 T1: "begin work";
 t1rs1 = T1:ResultSet("select * from emp_temp for update");

 T2: "begin work";
 statusValue = T2:"drop table  emp_temp";
 expect_equal(statusValue.code, 30052);
 expect_substr(statusValue.message, "LOCK TIMEOUT ERROR");

 T1: "commit";

 T2: "begin work";
 t2rs1 = T2:ResultSet("select * from emp_temp for update");
 expect_equal(t1rs1, t2rs1);
 T2: "commit";

 }

 TestCase CASE039
 {
     # U lock should block X lock for read committed level, HBASE scan/delete  parts of rows  ROW_LOCK  -no pk
 Terminal T1 T2;
 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table emp_temp as select * from employee";

 T1: "begin work";
 t1rs1 = T1:ResultSet("select * from emp_temp  where employeeno >=7839 and employeeno<=7902 for update");

 T2: "begin work";
 statusValue = T2:"delete from emp_temp where employeeno >=7839 and employeeno<=7902";
 expect_equal(statusValue.code, 30052);
 expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

 statusValue = T2:"delete from emp_temp where employeeno =7839";
 expect_equal(statusValue.code, 30052);

 statusValue = T2:"delete from emp_temp";
 expect_equal(statusValue.code, 30052);
 expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

 T1: "commit";

 T2: "begin work";
 t2rs1 = T2:ResultSet("select * from emp_temp  where employeeno >=7839 and employeeno<=7902 for update");
 expect_equal(t1rs1, t2rs1);
 T2: "commit";

 }

 TestCase CASE040
 {
     # U lock should block X lock for read committed level, HBASE scan/delete  parts of rows  ROW_LOCK  - pk
 Terminal T1 T2;
 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table emp_temp like  employee";
 T1: "insert into emp_temp select * from employee";

 T1: "begin work";
 t1rs1 = T1:ResultSet("select * from emp_temp  where employeeno >=7839 and employeeno<=7902 for update");

 T2: "begin work";
 statusValue = T2:"delete from emp_temp where employeeno >=7839 and employeeno<=7902";
 expect_equal(statusValue.code, 30052);
 expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

 statusValue = T2:"delete from emp_temp where employeeno =7839";
 expect_equal(statusValue.code, 30052);

 statusValue = T2:"delete from emp_temp";
 expect_equal(statusValue.code, 30052);
 expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

 T1: "commit";

 T2: "begin work";
 t2rs1 = T2:ResultSet("select * from emp_temp  where employeeno >=7839 and employeeno<=7902 for update");
 expect_equal(t1rs1, t2rs1);
 T2: "commit";

 }

 TestCase CASE041
 {
     # U lock should block U lock for read committed level , HBASE.GET  ROW_LOCK no pk
 Terminal T1 T2;
 statusValue = T1:"drop table emp_temp cascade";
 expect_no_substr(statusValue.message, "ERROR 30052");
 T1: "create table emp_temp as select * from employee";

 T1: "begin work";
 t1rs1 = T1:ResultSet("select * from emp_temp where employeeno = 7788  for update");

 T2: "begin work";
 statusValue = T2:"select * from emp_temp where employeeno =7788 for update";
 expect_equal(statusValue.code, 30052);
 expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

 T2: "begin work";
 statusValue = T2:"select employeeno, ename, job from emp_temp  where employeeno = 7902 for update";
 expect_equal(statusValue.code, 30052);

 T2: "begin work";
 statusValue = T2:"select employeeno, ename, job from emp_temp for update";
 expect_equal(statusValue.code, 30052);
 expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

 T1: "commit";

 T2: "begin work";
 t2rs1 = T2:ResultSet("select * from emp_temp where employeeno = 7788 for update");
expect_equal(t1rs1, t2rs1);
T2: "commit";

}

TestCase CASE042
{
    # U lock should block U lock for read committed level , HBASE.GET  ROW_LOCK  pk
    Terminal T1 T2;
statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

T1: "begin work";
t1rs1 = T1:ResultSet("select * from emp_temp where employeeno = 7788  for update");

T2: "begin work";
statusValue = T2:"select * from emp_temp where employeeno =7788 for update";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T2: "begin work";
statusValue = T2:"select employeeno, ename, job from emp_temp  where employeeno =7902 for update";
expect_equal(statusValue.code, 0);

T2: "begin work";
statusValue = T2:"select employeeno, ename, job from emp_temp for update";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T1: "commit";
T2: "begin work";
t2rs1 = T2:ResultSet("select * from emp_temp where employeeno = 7788 for update");
expect_equal(t1rs1, t2rs1);
T2: "commit";

}

TestCase CASE043
{
    # U lock should block U lock for read committed level , HBASE.SCAN  TABLE_LOCK  -pk
    Terminal T1 T2;
statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

T1: "begin work";
t1rs1 = T1:ResultSet("select * from emp_temp for update");

T2: "begin work";
statusValue = T2:"select * from emp_temp for update";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T2: "begin work";
statusValue = T2:"select employeeno, ename, job from emp_temp where employeeno = 7788 for update";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T1: "commit";

T2: "begin work";
t2rs1 = T2:ResultSet("select * from emp_temp for update");
expect_equal(t1rs1, t2rs1);

T2: "commit";

}

TestCase CASE044
{
    # U lock should block U lock for read committed level , HBASE.SCAN , part of rows  ROW_LOCK
    Terminal T1 T2;

statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

T1: "begin work";
t1rs1 = T1:ResultSet("select * from emp_temp where employeeno >=7839 and employeeno<=7902 for update");

T2: "begin work";
statusValue = T2:"select * from emp_temp where employeeno >=7839 and employeeno<=7902 for update";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T2: "begin work";
statusValue = T2:"select employeeno, ename, job from emp_temp where employeeno = 7839 for update";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T2: "begin work";
statusValue = T2:"select employeeno, ename, job from emp_temp where employeeno > 7902 for update";
expect_equal(statusValue.code, 0);

T2: "begin work";
statusValue = T2:"select * from emp_temp where employeeno = 7934 for update";
expect_equal(statusValue.code, 0);

statusValue = T2:"select * from emp_temp for update";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T1: "commit";

T2: "begin work";
t2rs1 = T2:ResultSet("select * from emp_temp where employeeno >=7839 and employeeno<=7902 for update");
expect_equal(t1rs1, t2rs1);

T2: "commit";

}

TestCase CASE045
{
    # U lock should block IX lock for read committed level, HBASE scan/delete  TABLE_LOCK
    Terminal T1 T2;

statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

T1: "begin work";
t1rs1 = T1:ResultSet("select * from emp_temp for update");

T2: "begin work";
statusValue = T2:"delete from emp_temp";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T1: "commit";

T2: "begin work";
t2rs1 = T2:ResultSet("select * from emp_temp for update");
expect_equal(t1rs1, t2rs1);
T2: "commit";

}

TestCase CASE046
{
    # X lock should not block IS lock for read committed level , HBASE.SCAN TABLE_LOCK -pk
    Terminal T1 T2;
statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

T1: "begin work";
t1rs1 = T1:ResultSet("select * from emp_temp for update");

T2: "begin work";
statusValue = T2:"select * from emp_temp";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");
# full table scan

T1: "commit";
T2: "commit";

}

TestCase CASE047
{
    # X lock should block X lock for read committed level, hbase.delete  1 row ROW_LOCK  pk
    Terminal T1 T2;
statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

t1rs1 = T1:ResultSet("select * from emp_temp where employeeno = 7788");

T1: "begin work";
T1: "delete from emp_temp where employeeno =7788";

T2: "begin work";
statusValue = T2:"delete from emp_temp where employeeno =7788";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"delete from emp_temp where employeeno = 7902";
expect_equal(statusValue.code, 0);
statusValue = T2:"delete from emp_temp where employeeno !=7788";
expect_equal(statusValue.code, 0);

statusValue = T2:"delete from emp_temp";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T1: "rollback";

T2: "begin work";
t2rs1 = T2: ResultSet("select * from emp_temp where employeeno = 7788");
expect_equal(t1rs1, t2rs1);

T2: "commit";

}

TestCase CASE048
{
    # X lock should block X lock for read committed level, hbase.delete  1 row ROW_LOCK  no pk
    Terminal T1 T2;
statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp as select * from employee";

t1rs1 = T1:ResultSet("select * from emp_temp where employeeno = 7788");

T1: "begin work";
T1: "delete from emp_temp where employeeno =7788";

T2: "begin work";
statusValue = T2:"delete from emp_temp where employeeno =7788";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"delete from emp_temp where employeeno = 7902";
expect_equal(statusValue.code, 0);
statusValue = T2:"delete from emp_temp where employeeno !=7788";
expect_equal(statusValue.code, 0);

statusValue = T2:"delete from emp_temp";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T1: "rollback";

T2: "begin work";
t2rs1 = T2: ResultSet("select * from emp_temp where employeeno = 7788");
expect_equal(t1rs1, t2rs1);

T2: "commit";

}


TestCase CASE049
{
    # X lock should block X lock for read committed level, hbase.delete  full table ROW_LOCK- pk
    Terminal T1 T2;
statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

t1rs1 = T1:ResultSet("select * from emp_temp");

T1: "begin work";
T1: "delete from emp_temp";

T2: "begin work";
statusValue = T2:"delete from emp_temp ";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"delete from emp_temp where employeeno =7788";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T1: "rollback";

T2: "begin work";
t2rs1 = T2: ResultSet("select * from emp_temp");
expect_equal(t1rs1, t2rs1);

T2: "commit";

}


TestCase CASE050
{
    # X lock should block X lock for read committed level, hbase.delete  full table ROW_LOCK- no pk
    Terminal T1 T2;
statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp as select * from employee";

t1rs1 = T1:ResultSet("select * from emp_temp");

T1: "begin work";
T1: "delete from emp_temp";

T2: "begin work";
statusValue = T2:"delete from emp_temp ";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"delete from emp_temp where employeeno =7788";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T1: "rollback";

t2rs1 = T2: ResultSet("select * from emp_temp");
expect_equal(t1rs1, t2rs1);

T2: "commit";

}

TestCase CASE051
{
    # X lock should block X lock for read committed level, hbase. ddl TABLE_LOCK
    Terminal T1 T2;
statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

T1: "begin work";
statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");

T2: "begin work";
statusValue = T2:"drop table emp_temp";
expect_equal(statusValue.code, 30052);

T1: "commit";
T2: "commit";

T2: "begin work";
statusValue = T2:"select * from emp_temp";
expect_equal(statusValue.code, 4082);

}

TestCase CASE052
{
    # X lock should block U lock for read committed level, hbase.detele/get     ROW_LOCK  -pk
    Terminal T1 T2;
statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

T1: "begin work";
t1rs1 = T1:ResultSet("select * from emp_temp where employeeno =7788");
T1: "delete from emp_temp where employeeno = 7788";

T2: "begin work";
statusValue = T2:"select * from emp_temp where employeeno =7788  for update";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T2: "begin work";
statusValue = T2:"select * from emp_temp where employeeno = 7902  for update";
expect_equal(statusValue.code, 0);

statusValue = T2:"select * from emp_temp for update";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T1: "rollback";

T2: "begin work";
t2rs1 = T2:ResultSet("select * from emp_temp where employeeno =7788 for update");
expect_equal(t1rs1, t2rs1);

T2: "commit";

}

TestCase CASE053
{
    # X lock should block U lock for read committed level, hbase.detele/get     ROW_LOCK  -no pk
    Terminal T1 T2;
statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp as select * from employee";

T1: "begin work";
t1rs1 = T1:ResultSet("select * from emp_temp where employeeno =7788");
T1: "delete from emp_temp where employeeno = 7788";

T2: "begin work";
statusValue = T2:"select * from emp_temp where employeeno =7788  for update";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"select * from emp_temp where employeeno = 7902  for update";
expect_no_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"select * from emp_temp for update";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T1: "rollback";

T2: "begin work";
t2rs1 = T2:ResultSet("select * from emp_temp where employeeno =7788 for update");
expect_equal(t1rs1, t2rs1);

T2: "commit";

}

TestCase CASE054
{
    # X lock should block U lock for read committed level, hbase .ddl TABLE_LOCK -pk
    Terminal T1 T2;
statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

t1rs1 = T1:ResultSet("select * from emp_temp");

T1: "begin work";
statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");

T2: "begin work";
statusValue = T2:"select * from emp_temp for update";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T2: "begin work";
statusValue = T2:"select * from emp_temp where employeeno =7788  for update";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T2: "begin work";
statusValue = T2:"select * from emp_temp where employeeno = 7902  for update";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T1: "rollback";

T2: "begin work";
t2rs1 = T2:ResultSet("select * from emp_temp for update");

expect_equal(t1rs1, t2rs1);

T2: "commit";

}

TestCase CASE055
{
    # X lock should block U lock for read committed level  hbase.delete/scan. part of rows  ROW_LOCK
    Terminal T1 T2;
statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";
t1rs1 = T1:ResultSet("select * from emp_temp where employeeno >=7839 and employeeno<=7902");

T1: "begin work";
T1: "delete from emp_temp where employeeno >=7839 and employeeno<=7902";

T2: "begin work";
statusValue = T2:"select * from emp_temp where employeeno >=7839 and employeeno<=7902  for update";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T2: "begin work";
statusValue = T2:"select * from emp_temp where employeeno =7839  for update";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T2: "begin work";
statusValue = T2:"select * from emp_temp where employeeno =7369 for update";
expect_equal(statusValue.code, 0);

statusValue = T2:"select * from emp_temp where employeeno =7788 for update";
expect_equal(statusValue.code, 0);

statusValue = T2:"select * from emp_temp for update";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T1: "rollback";

T2: "begin work";
t2rs1 = T2:ResultSet("select * from emp_temp where employeeno >=7839 and employeeno<=7902 for update");

expect_equal(t1rs1, t2rs1);

T2: "commit";

}

TestCase CASE056
{
    # X lock should block IX lock for read committed level,ddl  hbase.delete   TABLE_LOCK
    Terminal T1 T2;
statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

t1rs1 = T1:ResultSet("select * from emp_temp where employeeno = 7788");

T1: "begin work";
statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");

T2: "begin work";
statusValue = T2:"delete from emp_temp where employeeno =7788";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"update emp_temp set ename = 'lock' where employeeno =7788";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T1: "rollback";

T2: "begin work";
t2rs1 = T2: ResultSet("select * from emp_temp where employeeno = 7788");
expect_equal(t1rs1, t2rs1);

T2: "commit";

}

TestCase CASE057
{
    # table level X lock should block IS
    Terminal T1 T2;
T1: "drop table emp_salgrade";
T1: "create table emp_salgrade as select * from salgrade";

T1: "begin work";
T1: "drop table emp_salgrade";

T2: "begin work";
statusValue = T2:"select * from emp_salgrade";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T2: "begin work";
statusValue = T2:"select * from emp_salgrade where  grade =1";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");
T1: "commit";
T2: "commit";

}

# compatible
TestCase CASE058
{
    # when x row lock exceeds 100, table will add x lock . hbase.get/scan  row to table lock
    Terminal T1 T2;
T1: "begin work";
T1: "delete from largetable where id < 102";

T2: "begin work";
statusValue = T2:"update largetable set name = 'locktest' where id = 102";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T1: "rollback";
statusValue = T2:"update largetable set name = 'locktest' where id = 102";
expect_equal(statusValue.code, 0);

T2: "commit";

}

TestCase CASE059
{
    # upgrade table lock to X lock  + IX-lock, X lock should block IX lock.
    Terminal T1 T2;
T1: "begin work";
T1: "select count(*) from largetable where id < 102";

T1: "select count(*) from largetable where id < 102 for update";
T1: "delete from largetable where id < 102";

T2: "begin work";
statusValue = T2:"delete from largetable where id = 102";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T1: "rollback";
t2rs1 = T2:ResultSet("select * from largetable where id = 100");

T2: "commit";

}

TestCase CASE060
{
    # upgrade table lock to ix lock  -> x-lock, u lock should block u lock.
    Terminal T1 T2;
T1: "begin work";
T1: "update using upsert largetable set name = 'lock' where id < 102";
T1: "select count(*) from largetable where id < 102 for update";

T2: "begin work";
statusValue = T2:"select  * from  largetable where id = 102 for update";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T1: "rollback";

T2: "begin work";
statusValue = T2:"select * from largetable where id = 100 for update";
expect_equal(statusValue.code, 0);

T2: "commit";

}

# dead lock
TestCase CASE061
{
    # dead lock, in dead lock scenarios, one transaction should success.Single table
    Terminal T1 T2;
T1: "begin work";
T1: "select * from dept where deptno = 10 for update";

T2: "begin work";
T2: "select * from dept where deptno = 20 for update";

statusValue = T1:"select * from dept where deptno = 20 for update";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");
# Transaction T1 will abort

T2: "begin work";
t2rs1 = T2:ResultSet("select * from dept where deptno = 10 for update");
expect_equal(t2rs1, Tuple("((10,'ACCOUNTING','NEW YORK'),)"));

T2: "commit";

}

TestCase CASE062
{
    # in dead lock scenarios, one transaction should success. Multi-Table, different region.
    Terminal T1 T2;
T1: "begin work";
T1: "select * from employee where employeeno = 7788 for update";

T2: "begin work";
T2: "select * from dept where deptno =10 for update";

statusValue = T2:"select * from employee where employeeno = 7788 for update";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T2: "begin work";
t1rs1 = T1:ResultSet("select * from dept where deptno =10 for update");
expect_equal(t1rs1, Tuple("((10,'ACCOUNTING','NEW YORK'),)"));

T1: "commit";

}

TestCase CASE063
{
    # "in dead lock scenarios, one transaction should success.Circle lock scenarios"
    Terminal
T1
T2
T3
T4;
T1: "begin work";
t1rs1 = T1:ResultSet("select * from employee where employeeno = 7788 for update");

T2: "begin work";
T2: "select * from dept where deptno = 10 for update";

T3: "begin work";
T3: "select * from salgrade where grade = 1 for update";

T4: "begin work";
T4: "select * from largetable where id = 100 for update";

statusValue = T1:"select * from dept where deptno = 10 for update";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"select * from salgrade where grade =1 for update ";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T3:"select * from largetable where id = 100 for update";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

t4rs1 = T4:ResultSet("select * from employee where employeeno = 7788 for update");
expect_equal(t1rs1, t4rs1);

T4: "commit";

}

# dml/ddl
TestCase CASE064
{
    # showddl  -IS-lock  TABLE_LOCK add is lock to md, add x row-lock to md-row, so not conflict
    Terminal T1 T2;
T1: "begin work";
t1rs1 = T1:ResultSet("showddl dept");

T2: "begin work";
t2rs1 = T2:ResultSet("showddl dept");
expect_equal(t1rs1, t2rs1);

statusValue = T2:"alter table dept add if not exists column deptno decimal(2,0)";
expect_equal(statusValue.code, 0);
# add column such as insert in md table, so it't will no conflict

statusValue = T2:"alter table dept alter dname varchar(15)";
expect_equal(statusValue.code, 0);

T1: "commit";
statusValue = T2:"alter table dept add if not exists column deptno decimal(2,0)";
expect_equal(statusValue.code, 0);
T2: "commit";

}

TestCase CASE065
{
    # Alter table - X-lock
    Terminal T1 T2;
statusValue = T1:"drop table dept_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table dept_temp like  dept";
T1: "insert into dept_temp select * from dept";

T1: "begin work";
T1: "alter table dept_temp add column newcolumnlock varchar(20) default 'testLock'";

T2: "begin work";
statusValue = T2:"alter table dept_temp add column newcolumnlock varchar(20) default 'testLock'";
expect_equal(statusValue.code, 30052);

T1: "commit";

t2rs1 = T2:ResultSet("select newcolumnlock from dept_temp");
expect_substr(t2rs1, "testLock");

T2: "alter table dept_temp drop column newcolumnlock";

T2: "commit";

T2: "begin work";
t1rs1 = T1:ResultSet("select * from dept_temp");
expect_no_substr(t1rs1, "testLock");

}

TestCase CASE066
{
    # create/drop index  -X-lock
    Terminal T1 T2;
T1: "drop index idxsal";
rs = T1:ResultSet("select * from salgrade");

T1: "begin work";
T1: "create index idxsal on salgrade(GRADE)";

T2: "begin work";
statusValue = T2:"create index idxsal on salgrade(GRADE)";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "LOCK TIMEOUT ERROR");

T1: "commit";

T2: "begin work";
T2: "drop index idxsal";

T1: "begin work";
# trafodion_scan
statusValue = T1:"select * from salgrade";
expect_equal(statusValue.code, 0);

# index_scan
statusValue = T1:"select grade from salgrade where grade = 1";
expect_equal(statusValue.code, 30052);

# select index table
T1: "begin work";
T1: "set parserflags 1";
statusValue = T1:"select * from table(index_table idxsal)";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T2: "commit";

}

TestCase CASE067
{
    # Create/drop table - x-lock
    Terminal T1 T2;
T1: "drop table emp cascade";
T1: "begin work";
# emp - x-lock ,  employee with s -lock
T1: """create table emp(
    employeeno DECIMAL(4) NOT NULL primary key,
    ename VARCHAR(10),
    job VARCHAR(9),
    mgr DECIMAL(4),
    hiredate DATE,
    sal DECIMAL(7, 2),
    comm DECIMAL(7, 2),
    deptno DECIMAL(2)
    ) """;

T2: "begin work";
statusValue = T2: """create table emp(
    employeeno DECIMAL(4) NOT NULL primary key,
    ename VARCHAR(10),
    job VARCHAR(9),
    mgr DECIMAL(4),
    hiredate DATE,
    sal DECIMAL(7, 2),
    comm DECIMAL(7, 2),
    deptno DECIMAL(2)
    ) """;
expect_equal(statusValue.code, 30052);

T1: "commit";

T2: "begin work";
T2: "drop table emp";

T1: "begin work";
statusValue = T1: "select * from emp";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T2: "commit";

statusValue = T1:"select * from emp";
expect_equal(statusValue.code, 4082);

}

TestCase CASE068
{
    # create/drop view with x-lock
    Terminal T1 T2;
T1: "drop view viewemp";

T1: "begin work";
T1: "create view viewemp as select * from employee where employeeno >= 7839 and employeeno <= 7902";

T2: "begin work";
statusValue = T2:"create view viewemp as select * from employee where employeeno >= 7839 and employeeno <= 7902";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "LOCK TIMEOUT ERROR");

T1: "commit";

T2: "begin work";
T2: "drop view viewemp";

T1: "begin work";
statusValue = T1:"drop view viewemp";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

}

TestCase CASE069
{
    # invoke with s-lock
    Terminal T1 T2;
T1: "begin work";
T1: "invoke dept";

T2: "begin work";
T2: "invoke dept";

statusValue = T2:"alter table dept add if not exists column deptno decimal(2,0)";
expect_equal(statusValue.code, 0);
T1: "commit";
T2: "commit";

}

TestCase CASE070
{
    # CREATE LIBRAAY with x-lock
    Terminal T1 T2;
statusValue = T1:"drop library spj_test cascade";
expect_no_substr(statusValue.message, "ERROR 30052");

T1: "begin work";
T1: "create library spj_test file '/opt/trafodion/QALibs/SPJ/test_spj.jar'";

T2: "begin work";
statusValue = T2:"create library spj_test file '/opt/trafodion/QALibs/SPJ/test_spj.jar'";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "LOCK TIMEOUT ERROR");

T1: "commit";

T2: "begin work";
statusValue = T2:"drop library spj_test";
expect_equal(statusValue.code, 0);

T1: "begin work";
statusValue = T1:"drop library spj_test";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "LOCK TIMEOUT ERROR");

}

TestCase CASE071
{
    # create procedure with x-lock
    Terminal T1 T2;
statusValue = T1:"drop library spj_test cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create library spj_test file '/opt/trafodion/QALibs/SPJ/test_spj.jar'";

T1: "begin work";
statusValue = T1:"""create procedure numeric_insert(in value numeric(12,4))
external name 'org.trafodion.test.spj.Numeric.insert(java.math.BigDecimal)'
library spj_test
language  java
PARAMETER STYLE JAVA
modifies sql data""";
expect_equal(statusValue.code, 0);

T2: "begin work";
statusValue = T2:"""create procedure numeric_insert(in value numeric(12,4))
external name 'org.trafodion.test.spj.Numeric.insert(java.math.BigDecimal)'
library spj_test
language  java
PARAMETER STYLE JAVA
modifies sql data""";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "LOCK TIMEOUT ERROR");

T1: "commit";

T2: "begin work";
statusValue = T2:"drop procedure numeric_insert";
expect_equal(statusValue.code, 0);

T1: "begin work";
statusValue = T1:"drop procedure numeric_insert";
expect_equal(statusValue.code, 30052);

}

TestCase CASE072
{
    # create procedure with x-lock
    Terminal T1 T2;
T1: "drop library qa_udf_lib cascade";
T1: "create library qa_udf_lib file '/opt/trafodion/QALibs/UDF/qaUdfTest.so'";

T1: "begin work";
statusValue = T1:"""create function qa_udf_char
(INVAL char(50))
returns(c_char char(50))
language c
parameter style sql
external name 'qa_func_char'
library qa_udf_lib
deterministic
state area size 1024
allow any parallelism
no sql""";
expect_equal(statusValue.code, 0);

T2: "begin work";
statusValue = T2:"""create function qa_udf_char
(INVAL char(50))
returns(c_char char(50))
language c
parameter style sql
external name 'qa_func_char'
library qa_udf_lib
deterministic
state area size 1024
allow any parallelism
no sql""";
expect_equal(statusValue.code, 30052);

T1: "commit";

T2: "begin work";
T2: "drop function qa_udf_char";

T1: "begin work";

statusValue = T1:"drop function qa_udf_char";
expect_equal(statusValue.code, 30052);

}

TestCase CASE073
{
    # create sequence with x-lock
    Terminal T1 T2;
T1: "drop sequence seqlock";

T1: "begin work";
statusValue = T1:"create sequence seqlock";
expect_equal(statusValue.code, 0);

T2: "begin work";
statusValue = T2:"create sequence seqlock";
expect_equal(statusValue.code, 30052);

T1: "commit";

T2: "begin work";
statusValue = T2:"drop sequence seqlock";
expect_equal(statusValue.code, 0);

T1: "begin work";
statusValue = T1:"drop sequence seqlock";
expect_equal(statusValue.code, 30052);

T1: "begin work";
statusValue = T1:"select seqlock.nextval from dual";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

}

TestCase CASE074
{
    # alter sequence with x-lock
    Terminal T1 T2;

T1: "drop sequence seqlock";
T1: "create sequence seqlock";

T1: "begin work";
statusValue = T1:"alter sequence seqlock increment by 10";
expect_equal(statusValue.code, 0);

T2: "begin work";
statusValue = T2:"drop sequence seqlock";
expect_equal(statusValue.code, 30052);

T2: "begin work";
statusValue = T2:"showddl sequence seqlock";
expect_equal(statusValue.code, 0);

statusValue = T2:"select seqlock.nextval from dual";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T1: "commit";
statusValue = T2:"drop sequence seqlock";
expect_equal(statusValue.code, 0);

}

TestCase CASE075
{
    # comment on table/column/view/index/spj/udf
    Terminal T1 T2;
# Construction test data
T1: "drop table table_comment cascade";
T1: "drop view view_comment  cascade";
T1: "drop index index_comment  cascade";
T1: "drop library qa_udf_lib  cascade";
T1: "drop library  spj_test cascade";
T1: "drop procedure numeric_insert cascade";
T1: "drop function qa_udf_char cascade";

T1: "create table table_comment as select * from dept";
T1: "create view view_comment as select * from dept where deptno =20";
T1: "create index index_comment on table_comment(deptno)";
T1: "create library qa_udf_lib file '/opt/trafodion/QALibs/UDF/qaUdfTest.so'";
T1: "create library spj_test file '/opt/trafodion/QALibs/SPJ/test_spj.jar'";
T1: """create procedure numeric_insert(in value numeric(12,4))
external name 'org.trafodion.test.spj.Numeric.insert(java.math.BigDecimal)'
library spj_test
language  java
PARAMETER STYLE JAVA
modifies sql data""";
T1: """create function qa_udf_char
(INVAL char(50))
returns(c_char char(50))
language c
parameter style sql
external name 'qa_func_char'
library qa_udf_lib
deterministic
state area size 1024
allow any parallelism
no sql""";

T1: "comment on table table_comment is 'table comment x-lock test'";
# comment on table
T1: "begin work";
T1: "comment on table table_comment is 'table comment x-lock test'";

statusValue = T2:"comment on table table_comment is ''";
expect_equal(statusValue.code, 30052);

T1: "commit";

T2: "begin work";
statusValue = T2:"comment on table table_comment is ''";
expect_equal(statusValue.code, 0);

T1: "comment on column table_comment.deptno is 'column comment x-lock test'";
# comment on column
T1: "begin work";
T1: "comment on column table_comment.deptno is 'column comment x-lock test'";

statusValue = T2:"comment on column table_comment.deptno is ''";
expect_equal(statusValue.code, 30052);

T1: "commit";

T2: "begin work";
statusValue = T2:"comment on column table_comment.deptno is ''";
expect_equal(statusValue.code, 0);

T1: "comment on view view_comment is 'view comment x-lock test'";
# comment on view
T1: "begin work";
T1: "comment on view view_comment is 'view comment x-lock test'";

statusValue = T2:"comment on view view_comment is ''";
expect_equal(statusValue.code, 30052);

T1: "commit";

T2: "begin work";
statusValue = T2:"comment on view view_comment is ''";
expect_equal(statusValue.code, 0);

T1: "comment on index index_comment is 'index comment x-lock test'";
# comment on index
T1: "begin work";
T1: "comment on index index_comment is 'index comment x-lock test'";

statusValue = T2:"comment on index index_comment is ''";
expect_equal(statusValue.code, 30052);

T1: "commit";

T2: "begin work";
statusValue = T2:"comment on index index_comment is ''";
expect_equal(statusValue.code, 0);

T1: "comment on library spj_test is 'library comment x-lock test'";
# comment on library
T1: "begin work";
T1: "comment on library spj_test is 'library comment x-lock test'";

statusValue = T2:"comment on library spj_test is ''";
expect_equal(statusValue.code, 30052);

T1: "commit";

T2: "begin work";
statusValue = T2:"comment on library spj_test is ''";
expect_equal(statusValue.code, 0);

T1: "comment on procedure numeric_insert is 'procedure comment x-lock test'";
# comment on procedure
T1: "begin work";
T1: "comment on procedure numeric_insert is 'procedure comment x-lock test'";

statusValue = T2:"comment on procedure numeric_insert is ''";
expect_equal(statusValue.code, 30052);

T1: "commit";

T2: "begin work";
statusValue = T2:"comment on procedure numeric_insert is ''";
expect_equal(statusValue.code, 0);

T1: "comment on function qa_udf_char is 'function comment x-lock test'";
# comment on funciton
T1: "begin work";
T1: "comment on function qa_udf_char is 'function comment x-lock test'";

statusValue = T2:"comment on function qa_udf_char is ''";
expect_equal(statusValue.code, 30052);

T1: "commit";

T2: "begin work";
statusValue = T2:"comment on function qa_udf_char is ''";
expect_equal(statusValue.code, 0);

# recovery date
T1: "drop table table_comment cascade";
T1: "drop library qa_udf_lib  cascade";
T1: "drop library  spj_test cascade";

}


TestCase CASE076
{
    # truncate table with x-lock
    Terminal T1 T2;
T1: "drop table truncate_table cascade";
T1: "create table truncate_table as select * from dept";

T1: "begin work";
T1: "drop table truncate_table";

statusValue = T2:"""truncate table truncate_table""";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T1: "commit";

statusValue = T2:"""truncate table truncate_table""";
expect_equal(statusValue.code, 4082);

}

# DML delete
TestCase CASE077
{
    # DML DELETE FORM TEST_TABLE
    Terminal T1 T2;
statusValue = T1:"drop table  emp_delete cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_delete like employee";
T1: "insert into emp_delete  select * from employee";

T1: "begin work";
T1: "delete from emp_delete where employeeno = 7788";
statusValue = T2:"delete from emp_delete";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"delete from emp_delete where employeeno = 7788";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"delete from emp_delete where employeeno = 7369";
expect_equal(statusValue.code, 0);

statusValue = T2:"delete from emp_delete where employeeno > 7369 and employeeno <7839";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"delete from emp_delete";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"delete from emp_delete where employeeno != 7788;";
expect_equal(statusValue.code, 0);

T1: "commit";
# Verify that the lock is released
statusValue = T2:"delete from emp_delete";
expect_equal(statusValue.code, 0);
}

TestCase CASE078
{
    # DELETE: delete from test_table where conditionz( =/and/<>/
    # subquery)    subquery with no lock subquery table
    Terminal T1 T2;
statusValue = T1:"drop table  emp_delete cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "drop table emp_delete1 cascade";

T1: "create table emp_delete like employee";
T1: "insert into emp_delete  select * from employee";
T1: "create table emp_delete1 like employee";
T1: "insert into emp_delete1  select * from employee";

T1: "begin work";
T1: "delete from emp_delete where employeeno in(select employeeno from emp_delete1 where employeeno >= 7788 ) and deptno in(select deptno from dept where deptno !=10) and job  = 'ANALYST'";

statusValue = T2:"select employeeno from emp_delete1 where employeeno = 7788 for update";
expect_equal(statusValue.code, 0);

statusValue = T2:"select deptno from dept where deptno =20 for update";
expect_equal(statusValue.code, 0);

statusValue = T2:"delete from emp_delete where  job  = 'ANALYST'";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T1: "commit";
# Verify that the lock is released
statusValue = T2:"delete from emp_delete";
expect_equal(statusValue.code, 0);
}

TestCase CASE079
{
    # DELETE: delete view will lock base table
    Terminal T1 T2;
statusValue = T1:"drop table  emp_delete cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "drop view emp_view_delete";

T1: "create table emp_delete like employee";
T1: "insert into emp_delete  select * from employee";

T1: "create view emp_view_delete as select * from emp_delete where employeeno >=7839 and employeeno<=7902 ";

T1: "begin work";
T1: "delete from emp_view_delete";

statusValue = T2:"delete from emp_delete where employeeno >=7839 and employeeno<=7902 ";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"delete from emp_delete";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T1: "commit";
# Verify that the lock is released
statusValue = T2:"delete from emp_delete";
expect_equal(statusValue.code, 0);

}

TestCase CASE080
{
    # DELETE: delete table will  lock view
    Terminal T1 T2;
statusValue = T1:"drop table  emp_delete cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "drop view emp_view_delete";

T1: "create table emp_delete like employee";
T1: "insert into emp_delete  select * from employee";
T1: "create view emp_view_delete as select * from emp_delete where employeeno >=7839 and employeeno<=7902 ";

T1: "begin work";
T1: "delete from emp_delete";

statusValue = T2:"delete from emp_view_delete";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T1: "commit";
# Verify that the lock is released
statusValue = T2:"delete from emp_delete";
expect_equal(statusValue.code, 0);

}

TestCase CASE081
{
    # DELETE: delete table where row is not in view
    Terminal T1 T2;
statusValue = T1:"drop table  emp_delete cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "drop view emp_view_delete";

T1: "create table emp_delete like employee";
T1: "insert into emp_delete select * from employee";
T1: "create view emp_view_delete as select * from emp_delete where employeeno >=7839 and employeeno<=7902 ";

T1: "begin work";
T1: "delete from emp_view_delete";

statusValue = T2:"delete from emp_delete where employeeno <7839";
expect_equal(statusValue.code, 0);

statusValue = T2:"delete from emp_delete where employeeno > 7902";
expect_equal(statusValue.code, 0);

T1: "commit";
# Verify that the lock is released
statusValue = T2:"delete from emp_delete";
expect_equal(statusValue.code, 0);

}

TestCase CASE082
{
    # DELETE: delete view shouldn't lock rows in table where not in views
    Terminal T1 T2;
statusValue = T1:"drop table  emp_delete cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "drop view emp_view_delete";

T1: "create table emp_delete like  employee";
T1: "insert into emp_delete select * from employee";
T1: "create view emp_view_delete as select * from emp_delete where employeeno >=7839 and employeeno<=7902 ";

T1: "begin work";
T1: "delete from emp_delete where employeeno <7839";

statusValue = T2:"delete from emp_view_delete where employeeno >=7839";
expect_equal(statusValue.code, 0);

statusValue = T2:"delete from emp_view_delete";
expect_equal(statusValue.code, 0);

T1: "commit";
# Verify that the lock is released
statusValue = T2:"delete from emp_delete";
expect_equal(statusValue.code, 0);

}

TestCase CASE083
{
    # DELETE: delete table where row is not in view
    Terminal T1 T2;
statusValue = T1:"drop table  emp_delete cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "drop view emp_view_delete";

T1: "create table emp_delete like employee";
T1: "insert into emp_delete  select * from employee";
T1: "create view emp_view_delete as select * from emp_delete where employeeno >=7839 and employeeno<=7902 ";

T1: "begin work";
T1: "delete from emp_view_delete";

statusValue = T2:"delete from emp_delete where employeeno <7839";
expect_equal(statusValue.code, 0);

statusValue = T2:"delete from emp_delete where employeeno > 7902";
expect_equal(statusValue.code, 0);

T1: "commit";
# Verify that the lock is released
statusValue = T2:"delete from emp_delete";
expect_equal(statusValue.code, 0);
}

TestCase CASE084
{
    # DELETE: delete view shouldn't lock rows in table where not in views
    Terminal T1 T2;
statusValue = T1:"drop table  emp_delete cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "drop view emp_view_delete";

T1: "create table emp_delete like employee";
T1: "insert into emp_delete  select * from employee";
T1: "create view emp_view_delete as select * from emp_delete where employeeno >=7839 and employeeno<=7902 ";

T1: "begin work";
T1: "delete from emp_delete where employeeno <7839";

statusValue = T2:"delete from emp_view_delete where employeeno >=7839";
expect_equal(statusValue.code, 0);

statusValue = T2:"delete from emp_view_delete";
expect_equal(statusValue.code, 0);

T1: "commit";
# Verify that the lock is released
statusValue = T2:"delete from emp_delete";
expect_equal(statusValue.code, 0);
}

TestCase CASE085
{
    # INSERT: insert duplicate primary key
    Terminal T1 T2;
statusValue = T1:"drop table  emp_insert cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: """create table emp_insert(
    employeeno DECIMAL(4) NOT NULL primary key,
    ename VARCHAR(10),
    job VARCHAR(9),
    mgr DECIMAL(4),
    hiredate DATE,
    sal DECIMAL(7, 2),
    comm DECIMAL(7, 2),
    deptno DECIMAL(2))""";

T1: "begin work";
T1: "insert into emp_insert values(0428, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)";

T2: "begin work";
statusValue = T2:"insert into emp_insert values(0428, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"insert into emp_insert values(0623, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)";
expect_equal(statusValue.code, 0);
T2: "begin work";
T2: "select * from emp_insert";

T1: "commit";
T2: "commit";

statusValue = T2:"insert into emp_insert values(0428, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)";
expect_equal(statusValue.code, 8102);

}

TestCase CASE086
{
    # INSERT: insert into duplicate unique value
    Terminal T1 T2;
Terminal T1 T2;
statusValue = T1:"drop table  emp_insert cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: """create table emp_insert(
employeeno DECIMAL(4) NOT NULL unique,
ename VARCHAR(10),
job VARCHAR(9),
mgr DECIMAL(4),
hiredate DATE,
sal DECIMAL(7, 2),
comm DECIMAL(7, 2),
deptno DECIMAL(2))""";

T1: "begin work";
T1: "insert into emp_insert values(0428, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)";

T2: "begin work";
statusValue = T2:"insert into emp_insert values(0428, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"insert into emp_insert values(0623, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)";
expect_equal(statusValue.code, 0);

T1: "rollback";
statusValue = T2:"insert into emp_insert values(0428, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)";
expect_equal(statusValue.code, 0);

}

TestCase CASE087
{
    # INSERT: insert into duplicate  value when not has primary key
    Terminal T1 T2;
Terminal T1 T2;
statusValue = T1:"drop table  emp_insert cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: """create table emp_insert(
employeeno DECIMAL(4),
ename VARCHAR(10),
job VARCHAR(9),
mgr DECIMAL(4),
hiredate DATE,
sal DECIMAL(7, 2),
comm DECIMAL(7, 2),
deptno DECIMAL(2),
foreign key(deptno) references dept(deptno))""";

T1: "begin work";
T1: "insert into emp_insert values(0428, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)";

T2: "begin work";
statusValue = T2:"insert into emp_insert values(0428, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)";
expect_equal(statusValue.code, 0);

#change fk
T2:"begin work";
statusValue = T2:"select * from dept where deptno =10 for update";
expect_equal(statusValue.code, 30052);

T1: "rollback";
statusValue = T2:"insert into emp_insert values(0428, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)";
expect_equal(statusValue.code, 0);

}

TestCase CASE088
{
    # INSERT: T1: Insert 1,  T2: Delete 1
    Terminal T1 T2;
statusValue = T1:"drop table  emp_insert cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_insert like employee";
T1: "insert into emp_insert select * from employee";

T1: "begin work";
T1: "insert into emp_insert values(0428, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)";

T2: "begin work";

statusValue = T2:"delete from emp_insert where employeeno = 0428";
expect_equal(statusValue.code, 30052);

T1: "commit";
# Verify that the lock is released
statusValue = T2:"delete from emp_insert where employeeno = 0428";
expect_equal(statusValue.code, 0);

}

TestCase CASE089
{
    # INSERT: T1: Insert 1,  T2: Delete table
    Terminal T1 T2;
statusValue = T1:"drop table  emp_insert cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_insert like employee";
T1: "insert into emp_insert select * from employee";

T1: "begin work";
T1: "insert into emp_insert values(0428, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)";

T2: "begin work";

statusValue = T2:"delete from emp_insert";
expect_equal(statusValue.code, 0);

T1: "commit";
}


TestCase CASE090
{
    # INSERT: insert into a  select * from table b
    Terminal T1 T2;
statusValue = T1:"drop table emp_insert cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_insert like employee";
T1: "insert into emp_insert select * from employee where employeeno >=7839 and employeeno<=7902";

T1: "begin work";
T1: "insert into emp_insert select * from employee where employeeno < 7839 and employeeno > 7902";

statusValue = T2:"select * from employee where employeeno = 7369 for update";
expect_equal(statusValue.code, 0);

statusValue = T2:"select * from employee where employeeno = 7934 for update";
expect_equal(statusValue.code, 0);

T1: "commit";

}

#merge
TestCase CASE091
{
    # MERGE: merge into t when matched then update
    Terminal T1 T2;
statusValue = T1:"drop table  emp_merge cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: """create table emp_merge(
employeeno DECIMAL(4) NOT NULL primary key,
ename VARCHAR(10),
job VARCHAR(9),
mgr DECIMAL(4),
hiredate DATE,
sal DECIMAL(7, 2),
comm DECIMAL(7, 2),
deptno DECIMAL(2))""";

T1: "insert into emp_merge select * from employee";

T1: "begin work";
T1: "merge into emp_merge on employeeno = '7788' when matched then update set ename = 'xxx'";

T2:"begin work";
statusValue = T2:"select * from emp_merge where employeeno = 7788 for update";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T1: "commit";

T2: "begin work";
statusValue = T2:"select * from emp_merge where employeeno = 7788 for update";
expect_equal(statusValue.code, 0);

}

TestCase CASE092
{
    # MERGE: merge into t when matched then delete
    Terminal T1 T2;
statusValue = T1:"drop table  emp_merge cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: """create table emp_merge(
employeeno DECIMAL(4) NOT NULL primary key,
ename VARCHAR(10),
job VARCHAR(9),
mgr DECIMAL(4),
hiredate DATE,
sal DECIMAL(7, 2),
comm DECIMAL(7, 2),
deptno DECIMAL(2))""";

T1: "insert into emp_merge select * from employee";

T1: "begin work";
T1: "merge into emp_merge on employeeno = '7788' when matched then delete";

T2:"begin work";
statusValue = T2:"select * from emp_merge where employeeno = 7788 for update";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T2: "begin work";
statusValue = T2:"select * from emp_merge where employeeno = 7369 for update";
expect_equal(statusValue.code, 0);

T1: "commit";
statusValue = T2:"select * from emp_merge where employeeno = 7788 for update";
expect_equal(statusValue.code, 0);
}

TestCase CASE093
{
    # MERGE: merge into t when matched then update when not matched then insert 1
    Terminal T1 T2;

statusValue = T1:"drop table  emp_merge cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: """create table emp_merge(
employeeno DECIMAL(4) NOT NULL primary key,
ename VARCHAR(10),
job VARCHAR(9),
mgr DECIMAL(4),
hiredate DATE,
sal DECIMAL(7, 2),
comm DECIMAL(7, 2),
deptno DECIMAL(2))""";

T1: "insert into emp_merge select * from employee";

T1: "begin work";
T1: """merge into emp_merge on employeeno = '2345' when matched then update set ename ='xx'
	when not matched then insert VALUES(2345, 'testlock', 'CLERK', 7782, DATE '1982-01-23', 1300, NULL, 10)""";

statusValue = T2:"insert into emp_merge VALUES(2345, 'testlock', 'CLERK', 7782, DATE '1982-01-23', 1300, NULL, 10)";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T1: "commit";
statusValue = T2:"insert into emp_merge VALUES(2345, 'testlock', 'CLERK', 7782, DATE '1982-01-23', 1300, NULL, 10)";
expect_equal(statusValue.code, 8102);
}

TestCase CASE094
{
    # syntax do not support
    # MERGE: merge into t when matched then delete when not matched then insert select * from t1
    Terminal T1 T2;
statusValue = T1:"drop table  emp_merge cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: """create table emp_merge(
employeeno DECIMAL(4) NOT NULL primary key,
ename VARCHAR(10),
job VARCHAR(9),
mgr DECIMAL(4),
hiredate DATE,
sal DECIMAL(7, 2),
comm DECIMAL(7, 2),
deptno DECIMAL(2))""";

T1: "insert into emp_merge select * from employee";

T1: "begin work";
T1: """merge into emp_merge on employeeno = '2345' when matched then delete
	when not matched then insert VALUES(2345, 'testlock', 'CLERK', 7782, DATE '1982-01-23', 1300, NULL, 10)""";

statusValue = T2:"insert into emp_merge VALUES(2345, 'testlock', 'CLERK', 7782, DATE '1982-01-23', 1300, NULL, 10)";
# expect_equal(statusValue.code,30052);
# expect_substr(statusValue.message,"ROW LEVEL LOCK TIMEOUT ERROR");

T1: "commit";
}

TestCase CASE095
{
    # MERGE: merge into t when matched then update when not matched then insert select * from t1
    Terminal T1 T2;
statusValue = T1:"drop table  emp_merge cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: """create table emp_merge(
employeeno DECIMAL(4) NOT NULL primary key,
ename VARCHAR(10),
job VARCHAR(9),
mgr DECIMAL(4),
hiredate DATE,
sal DECIMAL(7, 2),
comm DECIMAL(7, 2),
deptno DECIMAL(2))""";

T1: "insert into emp_merge select * from employee";

T1: "begin work";
T1: """merge into emp_merge using(select employeeno,ename from employee where employeeno >=7839 and employeeno<=7902) x on employeeno = x.employeeno when matched then update set ename = x.ename """;

T2:"begin work";
statusValue = T2:"select employeeno,ename from emp_merge where employeeno =7839  for update";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T2: "begin work";
statusValue = T2:"select employeeno,ename from employee where employeeno =7369 for update";
expect_equal(statusValue.code, 0);

T1: "commit";
statusValue = T2:"select employeeno,ename from emp_merge where employeeno =7839  for update";
expect_equal(statusValue.code, 0);
}

TestCase CASE096
{
    # MERGE INTO t USING(SELECT a,b FROM t1) x ON t.a=x.a WHEN MATCHED THEN DELETE;
    Terminal T1 T2;
statusValue = T1:"drop table  emp_merge cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: """create table emp_merge(
employeeno DECIMAL(4) NOT NULL primary key,
ename VARCHAR(10),
job VARCHAR(9),
mgr DECIMAL(4),
hiredate DATE,
sal DECIMAL(7, 2),
comm DECIMAL(7, 2),
deptno DECIMAL(2))""";

T1: "insert into emp_merge select * from employee";

T1: "begin work";
T1: """merge into emp_merge using(select employeeno,ename from employee where employeeno >=7839 and employeeno<=7902) x on employeeno = x.employeeno when matched then delete""";

T2: "begin work";
statusValue = T2:"select employeeno,ename from emp_merge where employeeno =7839  for update";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T2: "begin work";
statusValue = T2:"select employeeno,ename from employee where employeeno =7369 for update";
expect_equal(statusValue.code, 0);

T1: "commit";
statusValue = T2:"select employeeno,ename from emp_merge where employeeno =7839  for update";
expect_equal(statusValue.code, 0);
}

TestCase CASE097
{
    # "MERGE INTO t USING(SELECT a,b FROM t1) x ON t.a=x.a WHEN MATCHED THEN UPDATE SET b=x.b  WHEN NOT MATCHED THEN INSERT SELECT * FROM T1;"
    Terminal T1 T2;
statusValue = T1:"drop table  emp_merge cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: """create table emp_merge(
employeeno DECIMAL(4) NOT NULL primary key,
ename VARCHAR(10),
job VARCHAR(9),
mgr DECIMAL(4),
hiredate DATE,
sal DECIMAL(7, 2),
comm DECIMAL(7, 2),
deptno DECIMAL(2))""";

T1: "insert into emp_merge select * from employee where employeeno >=7839 and employeeno<=7902";

T1: "begin work";
T1: """merge into emp_merge using(select employeeno,ename from employee where employeeno < 7839 or employeeno > 7902 limit 1) x on employeeno = x.employeeno when matched then update set ename = x.ename when not matched then insert VALUES(2345, 'testlock', 'CLERK', 7782, DATE '1982-01-23', 1300, NULL, 10)""";

rs1 = T1:ResultSet("select * from emp_merge where employeeno =2345");

statusValue = T2:"insert into emp_merge VALUES(2345, 'testlock', 'CLERK', 7782, DATE '1982-01-23', 1300, NULL, 10)";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T1: "commit";
statusValue = T2:"insert into emp_merge VALUES(2345, 'testlock', 'CLERK', 7782, DATE '1982-01-23', 1300, NULL, 10)";
expect_equal(statusValue.code, 8102);
}

# delete  the syntax didn't support
TestCase CASE098
{
    # "MERGE INTO t USING(SELECT a,b FROM t1) x ON t.a=x.a WHEN MATCHED THEN detele  WHEN NOT MATCHED THEN INSERT SELECT * FROM T1;"
    Terminal T1 T2;
statusValue = T1:"drop table  emp_merge cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: """create table emp_merge(
employeeno DECIMAL(4) NOT NULL primary key,
ename VARCHAR(10),
job VARCHAR(9),
mgr DECIMAL(4),
hiredate DATE,
sal DECIMAL(7, 2),
comm DECIMAL(7, 2),
deptno DECIMAL(2))""";

T1: "insert into emp_merge select * from employee";

T1: "begin work";
T1: """merge into emp_merge using(select employeeno,ename from employee where employeeno < 7839 or employeeno > 7902) x on employeeno = x.employeeno when matched then delete when not matched then insert VALUES(2345, 'testlock', 'CLERK', 7782, DATE '1982-01-23', 1300, NULL, 10)""";

statusValue = T2:"insert into emp_merge VALUES(2345, 'testlock', 'CLERK', 7782, DATE '1982-01-23', 1300, NULL, 10)";
# expect_equal(statusValue.code,30052);
# expect_substr(statusValue.message,"ROW LEVEL LOCK TIMEOUT ERROR");

T1: "commit";
statusValue = T2:"insert into emp_merge VALUES(2345, 'testlock', 'CLERK', 7782, DATE '1982-01-23', 1300, NULL, 10)";
expect_equal(statusValue.code, 8102);
}

TestCase CASE099
{
    # UPDATE: UPDATE conflict
    Terminal T1 T2;
statusValue = T1:"drop table  emp_update cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: """create table emp_update(
employeeno DECIMAL(4) NOT NULL primary key,
ename VARCHAR(10),
job VARCHAR(9),
mgr DECIMAL(4),
hiredate DATE,
sal DECIMAL(7, 2),
comm DECIMAL(7, 2),
deptno DECIMAL(2))""";

T1: "insert into emp_update select * from employee";

T1: "begin work";
T1: """update emp_update set ename = 'testlock' where employeeno = 7369""";

statusValue = T2:"update emp_update set ename = 'testlock' where employeeno = 7369";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"update emp_update set ename = 'testlock' where employeeno = 7499";
expect_equal(statusValue.code, 0);

statusValue = T2:"update emp_update set ename = 'testlock' where employeeno >7369";
expect_equal(statusValue.code, 0);

statusValue = T2:"update emp_update set ename = 'testlock' where employeeno !=7369";
expect_equal(statusValue.code, 0);

T1: "commit";
statusValue = T2:"update emp_update set ename = 'testlock' where employeeno = 7369";
expect_equal(statusValue.code, 0);
}

TestCase CASE100
{
    # UPDATE: UPDATE SET duplicate  unique
    Terminal T1 T2;
statusValue = T1:"drop table  emp_update cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: """create table emp_update(
employeeno DECIMAL(4) NOT NULL unique,
ename VARCHAR(10),
job VARCHAR(9),
mgr DECIMAL(4),
hiredate DATE,
sal DECIMAL(7, 2),
comm DECIMAL(7, 2),
deptno DECIMAL(2))""";

T1: "insert into emp_update select * from employee";

T1: "begin work";
T1: """update emp_update set ename = 'testlock' where employeeno = 7369""";

statusValue = T2:"update emp_update set ename = 'testlock' where employeeno = 7369";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"update emp_update set ename = 'testlock' where employeeno = 7499";
expect_equal(statusValue.code, 0);

statusValue = T2:"update emp_update set ename = 'testlock' where employeeno >7369";
expect_equal(statusValue.code, 0);

statusValue = T2:"update emp_update set ename = 'testlock' where employeeno !=7369";
expect_equal(statusValue.code, 0);

T1: "commit";
statusValue = T2:"update emp_update set ename = 'testlock' where employeeno = 7369";
expect_equal(statusValue.code, 0);
}

TestCase CASE101
{
    # UPDATE: UPDATE SET duplicate when table not primary key and unique key
    Terminal T1 T2;
statusValue = T1:"drop table  emp_update cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: """create table emp_update(
employeeno DECIMAL(4),
ename VARCHAR(10),
job VARCHAR(9),
mgr DECIMAL(4),
hiredate DATE,
sal DECIMAL(7, 2),
comm DECIMAL(7, 2),
deptno DECIMAL(2))""";

T1: "insert into emp_update select * from employee";

T1: "begin work";
T1: """update emp_update set ename = 'testlock' where employeeno = 7369""";


statusValue = T2:"update emp_update set ename = 'testlock' where employeeno = 7369";
expect_equal(statusValue.code, 30052);

statusValue = T2:"update emp_update set ename = 'testlock' where employeeno != 7369";
expect_equal(statusValue.code, 0);

T1: "commit";
}

TestCase CASE102
{
    # UPDATE: T1: UPDATE  1,  T2:delete 1
    Terminal T1 T2;
statusValue = T1:"drop table  emp_update cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_update like employee";
T1: "insert into emp_update select * from employee";

T1: "begin work";
T1: """update emp_update set ename = '1234' where employeeno = 7788""";

statusValue = T2:"update emp_update set employeeno = 1234 where ename = 'TAC-MD'";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"delete from emp_update where ename = 'TAC-MD'";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T1: "commit";
statusValue = T2:"update emp_update set employeeno = 1234 where ename = 'TAC-MD'";
expect_equal(statusValue.code, 0);
}

TestCase CASE103
{
    # UPDATE: T1: UPDATE  1,  T2:delete table
    Terminal T1 T2;
statusValue = T1:"drop table  emp_update cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_update like employee";
T1: "insert into emp_update select * from employee";

T1: "begin work";
T1: """update emp_update set employeeno = 1234 where employeeno = 7788""";

statusValue = T2:"update emp_update set employeeno = 1234";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"delete from emp_update";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T1: "commit";
statusValue = T2:"delete from emp_update";
expect_equal(statusValue.code, 0);
}

TestCase CASE104
{
    # UPDATE: UPDATE set 1 in basic table , delete 1 in view
    Terminal T1 T2;
statusValue = T1:"drop table  emp_update cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_update like employee";
T1: "insert into emp_update select * from employee";
T1: """create view emp_view_update as select * from emp_update""";

T1: "begin work";
T1: """update emp_update set sal = 1234 where employeeno = 7788""";

statusValue = T2:"update emp_view_update set sal = 1234 where employeeno = 7788";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"delete from emp_view_update where employeeno = 7788";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T1: "commit";
statusValue = T2:"update emp_view_update set sal = 1234 where employeeno = 7788";
expect_equal(statusValue.code, 0);
}

TestCase CASE105
{
    # UPDATE: UPDATE set 1 in  view, delete 1 in basic table
    Terminal T1 T2;
statusValue = T1:"drop table  emp_update cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_update like employee";
T1: "insert into emp_update select * from employee";
T1: """create view emp_view_update as select * from emp_update""";

T1: "begin work";
T1: """update emp_view_update set sal = 1234 where employeeno = 7788""";

statusValue = T2:"update emp_update set sal = 1234 where employeeno = 7788";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"delete from emp_update where employeeno = 7788";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T1: "commit";
statusValue = T2:"update emp_update set sal = 1234 where employeeno = 7788";
expect_equal(statusValue.code, 0);
}

TestCase CASE106
{
    # UPDATE: update set 1 where b in(select * from b)
    Terminal T1 T2;
statusValue = T1:"drop table  emp_update cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_update like employee";
T1: "insert into emp_update select * from employee";
T1: """create view emp_view_update as select * from emp_update""";

T1: "begin work";
T1: """update emp_view_update set sal = 1234 where employeeno = 7788""";

statusValue = T2:"update emp_update set sal = 1234 where employeeno = 7788";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"delete from emp_update where employeeno = 7788";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T1: "commit";
statusValue = T2:"update emp_update set sal = 1234 where employeeno = 7788";
expect_equal(statusValue.code, 0);

}

TestCase CASE107
{
    # UPDATE: update view shouldn't lock rows in table where not in views
    Terminal T1 T2;
statusValue = T1:"drop table  emp_update cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_update like employee";
T1: "insert into emp_update select * from employee";
T1: """create view emp_view_update as select * from emp_update""";

T1: "begin work";
T1: """update emp_view_update set sal = 1234 where employeeno = 7788""";

statusValue = T2:"update emp_update set sal = 1234 where employeeno !=7788";
expect_equal(statusValue.code, 0);

statusValue = T2:"delete from emp_update where employeeno !=7788";
expect_equal(statusValue.code, 0);

T1: "commit";
statusValue = T2:"update emp_update set sal = 1234 where employeeno !=7788";
expect_equal(statusValue.code, 0);

}

TestCase CASE108
{
    # UPSERT: upsert duplicate primary key
    Terminal T1 T2;
statusValue = T1:"drop table t0 cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table t0(a int not null primary key, b int, c int)";

T1: "begin work";
T1: "upsert into t0 values(1,2,2)";

statusValue = T2:"upsert into t0 values(1,3,3)";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T1: "commit";
statusValue = T2:"upsert into t0 values(1,3,3)";
expect_equal(statusValue.code, 0);

}

TestCase CASE109
{
    # UPSERT: upsert duplicate unique
    Terminal T1 T2;
statusValue = T1:"drop table t0 cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table t0(a int not null unique, b int, c int)";

T1: "begin work";
T1: "upsert into t0 values(1,2,2)";

statusValue = T2:"upsert into t0 values(1,3,3)";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T1: "commit";
statusValue = T2:"upsert into t0 values(1,3,3)";
expect_equal(statusValue.code, 8102);

}

TestCase CASE110
{
    # upsert: upsert duplicate when table not primary key and unique key
    Terminal T1 T2;
statusValue = T1:"drop table t0 cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table t0(a int, b int, c int)";

T1: "begin work";
T1: "upsert into t0 values(1,2,2)";

statusValue = T2:"upsert into t0 values(1,3,3)";
expect_equal(statusValue.code, 0);

T1: "commit";

statusValue = T2:"upsert into t0 values(1,3,3)";
expect_equal(statusValue.code, 0);

}

TestCase CASE111
{
    # upsert: T1: upsert 1,  T2:delete 1
    Terminal T1 T2;
statusValue = T1:"drop table t0 cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table t0(a int primary key, b int, c int)";
T1: "upsert into t0 values(1,2,2)";

T1: "begin work";
T1: "upsert into t0 values(1,3,3)";

statusValue = T2:"delete from t0 where a =1";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T1: "commit";

statusValue = T2:"delete from t0 where a =1";
expect_equal(statusValue.code, 0);

}

TestCase CASE112
{
    # upsert: T1: upsert 1,  T2:delete table
    Terminal T1 T2;
statusValue = T1:"drop table t0 cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table t0(a int primary key, b int, c int)";
T1: "upsert into t0 values(1,2,2)";

T1: "begin work";
T1: "upsert into t0 values(1,3,3)";

statusValue = T2:"delete from t0";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T1: "commit";

statusValue = T2:"delete from t0";
expect_equal(statusValue.code, 0);

}

TestCase CASE113
{
    # Upsert: upsert into a  select * from table b
    Terminal T1 T2;
statusValue = T1:"drop table t0 cascade";
expect_no_substr(statusValue.message, "ERROR 30052");

statusValue = T1:"drop table t1 cascade";
expect_no_substr(statusValue.message, "ERROR 30052");

T1: "create table t0(a int primary key, b int, c int)";
T1: "create table t1(a int primary key, b int, c int)";
T1: "upsert into t0 values(1,2,2)";
T1: "upsert into t1 values(2,2,4)";

T1: "begin work";
T1: "upsert into t0 select * from t1";

T2: "begin work";
statusValue = T2:"select * from t1 for update";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T1: "commit";

statusValue = T2:"delete from t0";
expect_equal(statusValue.code, 0);

}

TestCase CASE114
{
    # upsert: upsert 1 into basic table , delete 1 in view
    Terminal T1 T2;
statusValue = T1:"drop table t0 cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "drop view t0_view";
T1: "create table t0(a int primary key, b int, c int)";
T1: "create view  t0_view as select * from t0 where a <= 3";
T1: "upsert into t0 values(1,2,2)";
T1: "upsert into t0 values(2,2,2)";
T1: "upsert into t0 values(3,2,4)";
T1: "upsert into t0 values(4,2,2)";
T1: "upsert into t0 values(5,2,4)";

T1: "begin work";
T1: "upsert into t0 values(1,3,2)";

statusValue = T2:"delete from t0_view where a =1 ";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"upsert into t0_view values(1,2,2) ";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T1: "commit";
statusValue = T2:"upsert into t0_view values(1,2,2) ";
expect_equal(statusValue.code, 0);
}

TestCase CASE115
{
    # upsert: upsert 1 into basic table , delete 1 in view
    Terminal T1 T2;
statusValue = T1:"drop table t0 cascade";
expect_no_substr(statusValue.message, "ERROR 30052");

T1: "drop view t0_view";
T1: "create table t0(a int primary key, b int, c int)";
T1: "create view  t0_view as select * from t0 where a <= 3";
T1: "upsert into t0 values(1,2,2)";
T1: "upsert into t0 values(2,2,2)";
T1: "upsert into t0 values(3,2,4)";
T1: "upsert into t0 values(4,2,2)";
T1: "upsert into t0 values(5,2,4)";

T1: "begin work";
T1: "upsert into t0 values(1,3,2)";

statusValue = T2:"delete from t0_view where a =1 ";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"upsert into t0_view values(1,2,2) ";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T1: "commit";
statusValue = T2:"upsert into t0_view values(1,2,2) ";
expect_equal(statusValue.code, 0);
}


TestCase CASE116
{
    # upsert: upsert: upsert 1 into basic table , delete 2 in view
    Terminal T1 T2;
statusValue = T1:"drop table t0 cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "drop view t0_view";
T1: "create table t0(a int primary key, b int, c int)";
T1: "create view  t0_view as select * from t0 where a <= 3";
T1: "upsert into t0 values(1,2,2)";
T1: "upsert into t0 values(2,2,2)";
T1: "upsert into t0 values(3,2,4)";
T1: "upsert into t0 values(4,2,2)";
T1: "upsert into t0 values(5,2,4)";

T1: "begin work";
T1: "upsert into t0 values(1,3,2)";

statusValue = T2:"delete from t0_view where a =2";
expect_equal(statusValue.code, 0);

statusValue = T2:"upsert into t0_view values(2,2,2)";
expect_equal(statusValue.code, 0);

T1: "commit";
}


TestCase CASE117
{
    # upsert: upsert: upsert 1 into basic table , delete 2 in view
    Terminal T1 T2;
statusValue = T1:"drop table t0 cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "drop view t0_view";
T1: "create table t0(a int primary key, b int, c int)";
T1: "create view  t0_view as select * from t0 where a <= 3";
T1: "upsert into t0 values(1,2,2)";
T1: "upsert into t0 values(2,2,2)";
T1: "upsert into t0 values(3,2,4)";
T1: "upsert into t0 values(4,2,2)";
T1: "upsert into t0 values(5,2,4)";

T1: "begin work";
T1: "upsert into t0_view values(1,3,2)";

statusValue = T2:"delete from t0 where a =2";
expect_equal(statusValue.code, 0);

statusValue = T2:"upsert into t0 values(2,2,2) ";
expect_equal(statusValue.code, 0);

T1: "commit";
}

TestCase CASE118
{
    # Update using upsert
    Terminal T1 T2;
statusValue = T1:"drop table t0 cascade";
expect_no_substr(statusValue.message, "ERROR 30052");

T1: "create table t0(a int primary key, b int, c int)";
T1: "upsert into t0 values(1,2,2)";
T1: "upsert into t0 values(2,2,2)";
T1: "upsert into t0 values(3,2,4)";
T1: "upsert into t0 values(4,2,2)";
T1: "upsert into t0 values(5,2,4)";

T1: "begin work";
T1: "update using upsert  t0 set b =2 where a=2";

statusValue = T2:"update using upsert  t0 set b =2 where a=2";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"delete from t0 where a=2 ";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T1: "commit";
statusValue = T2:"delete from t0 where a=2 ";
expect_equal(statusValue.code, 0);
}


TestCase CASE119
{
    # call with x-lock
    Terminal T1 T2;
statusValue = T1:"drop library spj_test cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "drop table SPJ_NUMERIC cascade";

T1: "create library spj_test file '/opt/trafodion/QALibs/SPJ/test_spj.jar'";

T1: "drop procedure numeric_insert cascade ";

statusValue = T1:"""create procedure numeric_insert(in value numeric(12,4))
external name 'org.trafodion.test.spj.Numeric.insert(java.math.BigDecimal)'
library spj_test
language  java
PARAMETER STYLE JAVA
modifies sql data""";

T1: "begin work";
T1: "call numeric_insert(1)";

T2: "begin work";
statusValue = T2:"call numeric_insert(1)";
expect_equal(statusValue.code, 11220);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");
statusValue = T2:"showddl procedure numeric_insert";
expect_equal(statusValue.code, 0);

T1: "commit";
statusValue = T2:"drop procedure numeric_insert";
expect_equal(statusValue.code, 0);

}

# Multiple partition cases

TestCase CASE120
{
    Terminal T1 T2;
statusValue = T1:"drop table emp_partition";
expect_no_substr(statusValue.message, "ERROR 30052");

T1: """CREATE TABLE emp_partition
   (
    employeeno DECIMAL(4) NOT NULL primary key
    )
	salt using 2 partitions on(employeeno)
	""";

T1: "INSERT INTO emp_partition VALUES(1)";
T1: "INSERT INTO emp_partition VALUES(0623)";

T2: "begin work";
T2: "delete from emp_partition";

statusValue = T1:"delete from emp_partition where employeeno = 1";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T2: "rollback";

T2: "begin work";
T2: "delete from emp_partition where employeeno = 1";

statusValue = T1:"delete from emp_partition where employeeno = 1";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

T2: "rollback";
}

TestCase CASE121
{
    # sequence.nextval with x-lock
    Terminal T1 T2;
statusValue = T1:"drop sequence seqlock";
expect_no_substr(statusValue.message, "ERROR 30052");

T1: "create sequence seqlock";

T1: "begin work";
statusValue = T1:"select seqlock.nextval from dual";
expect_equal(statusValue.code, 0);

T2: "begin work";
statusValue = T2:"select seqlock.nextval from dual";
expect_equal(statusValue.code, 30052);

T2: "begin work";
statusValue = T2:"select seqlock.currval from dual";
expect_equal(statusValue.code, 30052);

T1: "commit";

T2: "begin work";
statusValue = T2:"select seqlock.currval from dual";
expect_equal(statusValue.code, 0);

T1: "begin work";
statusValue = T1:"select seqlock.currval from dual";
expect_equal(statusValue.code, 0);

statusValue = T1:"select seqlock.nextval from dual";
expect_equal(statusValue.code, 0);

T2: "commit";

}


#dml select  index_scan
TestCase CASE122
{
    # index_scan
    Terminal T1 T2;
statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

T1: "create index idx_scan on emp_temp(employeeno)";

T1: "begin work";
t1rs1 = T1:ResultSet("select employeeno from emp_temp where employeeno =7839");

T2: "begin work";
T2: "set parserflags 1";
statusValue = T2:"select * from table(index_table idx_scan) for update";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

#index and base table not same

T2: "begin work";
statusValue = T2:"select employeeno from emp_temp where employeeno =7839 for update";
expect_equal(statusValue.code, 0);

statusValue = T2:"select * from emp_temp for update";
expect_equal(statusValue.code, 0);

T1: "commit";

statusValue = T2:"select * from table(index_table idx_scan) for update";
expect_equal(statusValue.code, 0);

T2: "commit";

}

#dml select mdam_scan
TestCase CASE123
{
    # mdam_scan
    Terminal T1 T2;
statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: """create table emp_temp
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
""";
T1: "insert into emp_temp select * from employee";

T1: "create index idx_emp on emp_temp(employeeno)";

T1: "begin work";
t1rs1 = T1:ResultSet("select employeeno from emp_temp where deptno =7839");

T2: "begin work";
t2rs1 = T2:ResultSet("select employeeno from emp_temp where deptno =7839");


expect_equal(t1rs1, t2rs1);

T1: "commit";
T2: "commit";

}

#vsbb_scan
TestCase CASE124
{
    # vsbb_scan
    Terminal T1 T2;
statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

T1: "create index idx_scan on emp_temp(employeeno)";

T1: "begin work";
t1rs1 = T1:ResultSet("select employeeno from emp_temp a, emp_temp b where a.employeeno =b.employeeno and a.employeeno = 7788");

T2: "begin work";
t2rs1 = T2:ResultSet("select employeeno from emp_temp a, emp_temp b where a.employeeno =b.employeeno and a.employeeno = 7788");

expect_equal(t1rs1, t2rs1);

T1: "commit";
T2: "commit";

}

#vsbb_scan_diff table
TestCase CASE125
{
    # vsbb_scan
    Terminal T1 T2;
statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

T1: "create index idx_scan on emp_temp(employeeno)";

T1: "begin work";
t1rs1 = T1:ResultSet("select employeeno from emp_temp a, emp_temp b where a.employeeno =b.employeeno and a.employeeno = 7788");

T2: "begin work";
t2rs1 = T2:ResultSet("select employeeno from emp_temp a, emp_temp b where a.employeeno =b.employeeno and a.employeeno = 7788");

expect_equal(t1rs1, t2rs1);

T1: "commit";
T2: "commit";

}

#dml ： select complex query union
TestCase CASE126
{
    # union
    Terminal T1 T2;
statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

T1: "create index idx_scan on emp_temp(employeeno)";

T1: "begin work";
t1rs1 = T1:ResultSet("select * from emp_temp union  select employeeno from emp_temp where employeeno = 7788");

T2: "begin work";
t2rs1 = T2:ResultSet("select * from emp_temp union  select employeeno from emp_temp where employeeno = 7788");

expect_equal(t1rs1, t2rs1);

T1: "commit";
T2: "commit";

}

# select join group by order by
TestCase CASE127
{
    # join
    Terminal T1 T2;
statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";


T1: "begin work";
t1rs1 = T1:ResultSet("""select distinct(EMPLOYEENO)  from
 (select * from (select employeeno,ename from EMPLOYEE a
 right join (select * from dept) b on a.deptno = b.deptno
 where a.deptno =10 order by a.employeeno) union all
  select * from (select employeeno,ename from EMPLOYEE a right join
   (select * from dept) b on a.deptno = b.deptno where a.deptno =10  order by a.employeeno)) c group by c.EMPLOYEENO;""");

T2:"begin work";
t2rs1 = T1:ResultSet("""select distinct(EMPLOYEENO)  from
 (select * from (select employeeno,ename from EMPLOYEE a
 right join (select * from dept) b on a.deptno = b.deptno
 where a.deptno =10 order by a.employeeno) union all
  select * from (select employeeno,ename from EMPLOYEE a right join
   (select * from dept) b on a.deptno = b.deptno where a.deptno =10  order by a.employeeno)) c group by c.EMPLOYEENO;""");

expect_equal(t1rs1, t2rs1);

T1: "commit";
T2: "commit";

}

#update composite primary key
TestCase CASE128
{
    # update composite primary key
    Terminal T1 T2;
statusValue = T1:"drop table  emp_composite_pk cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: """create table emp_composite_pk(
    employeeno DECIMAL(4),
    ename VARCHAR(10),
    job VARCHAR(9),
    mgr DECIMAL(4),
    hiredate DATE,
    sal DECIMAL(7, 2),
    comm DECIMAL(7, 2),
    deptno DECIMAL(2),
    primary key(employeeno,deptno)
    )""";

T1:"insert into emp_composite_pk select * from employee";

T1: "begin work";
T1: "update emp_composite_pk set deptno = 50 where employeeno = 7369";

T2: "begin work";
statusValue = T2:"update emp_composite_pk set deptno = 50 where employeeno = 7788";
expect_equal(statusValue.code, 0);

statusValue = T2:"update emp_composite_pk set deptno = 50 where employeeno = 7369";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"insert into emp_composite_pk values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 60)";
expect_equal(statusValue.code, 0);

T1:"rollback";
statusValue = T2:"update emp_composite_pk set deptno = 50 where employeeno = 7369 and deptno = 20";
expect_equal(statusValue.code, 0);
}

TestCase CASE129
{
    # update composite unique-key
    Terminal T1 T2;
statusValue = T1:"drop table  emp_composite_unique cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: """create table emp_composite_unique(
    employeeno DECIMAL(4),
    ename VARCHAR(10),
    job VARCHAR(9),
    mgr DECIMAL(4),
    hiredate DATE,
    sal DECIMAL(7, 2),
    comm DECIMAL(7, 2),
    deptno DECIMAL(2),
    unique(employeeno,deptno)
    )""";

T1:"insert into emp_composite_unique select * from employee";

T1: "begin work";
T1: "update emp_composite_unique set deptno = 50 where employeeno = 7369";

T2: "begin work";
statusValue = T2:"update emp_composite_unique set deptno = 50 where employeeno = 7788";
expect_equal(statusValue.code, 0);

statusValue = T2:"update emp_composite_unique set deptno = 50 where employeeno = 7369";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"insert into emp_composite_unique values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 60)";
expect_equal(statusValue.code, 0);

T1:"rollback";
statusValue = T2:"update emp_composite_unique set deptno = 50 where employeeno = 7369 and deptno =20";
expect_equal(statusValue.code, 0);
}

#check(constraint)
TestCase CASE130
{
    # update composite unique-key
    Terminal T1 T2;
statusValue = T1:"drop table  emp_check cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: """create table emp_check(
    employeeno DECIMAL(4),
    ename VARCHAR(10),
    job VARCHAR(9),
    mgr DECIMAL(4),
    hiredate DATE,
    sal DECIMAL(7, 2),
    comm DECIMAL(7, 2),
    deptno DECIMAL(2) check(deptno >= 10)
    )""";

T1:"insert into emp_check select * from employee";

T1: "begin work";
T1: "update emp_check set deptno = 50 where employeeno = 7369";

T2: "begin work";
statusValue = T2:"update emp_check set deptno = 50 where employeeno = 7788";
expect_equal(statusValue.code, 0);

statusValue = T2:"update emp_check set deptno = 9 where employeeno = 7369";
expect_equal(statusValue.code, 30052);
expect_substr(statusValue.message, "ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"insert into emp_check values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 60)";
expect_equal(statusValue.code, 0);

T1:"rollback";
statusValue = T2:"update emp_check set deptno = 50 where employeeno = 7369";
expect_equal(statusValue.code, 0);
}

#forign key  -- delete parent table , insert or update or delele subtable
TestCase CASE131
{
    Terminal T1 T2;
statusValue = T1:"drop table  emp_fk cascade";
expect_no_substr(statusValue.message, "ERROR 30052");

statusValue = T1:"drop table  dept_fk cascade";
expect_no_substr(statusValue.message, "ERROR 30052");

T1: """create table dept_fk like dept""";
T1: """insert into dept_fk select * from dept""";

T1: """create table emp_fk(
    employeeno DECIMAL(4),
    ename VARCHAR(10),
    job VARCHAR(9),
    mgr DECIMAL(4),
    hiredate DATE,
    sal DECIMAL(7, 2),
    comm DECIMAL(7, 2),
    deptno DECIMAL(2) references dept_fk(deptno)
    )""";

T1:"insert into emp_fk select * from employee where deptno >10";

T1: "begin work";
T1: "delete from dept_fk where deptno =10";

T2:"begin work";
statusValue = T2:"insert into emp_fk values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)";
expect_equal(statusValue.code, 30052);

statusValue = T2:"update emp_fk set deptno = 10";
expect_equal(statusValue.code, 30052);

statusValue = T2:"delete from emp_fk where deptno = 10";
expect_equal(statusValue.code, 0);

statusValue = T2:"insert into emp_fk values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 20)";
expect_equal(statusValue.code, 0);

T1:"commit";
T2:"commit";

statusValue = T2:"insert into emp_fk values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)";
expect_equal(statusValue.code, 0);

}

#forign key  -- insert parent table , insert or update or delele subtable
TestCase CASE132
{
    Terminal T1 T2;
statusValue = T1:"drop table  emp_fk cascade";
expect_no_substr(statusValue.message, "ERROR 30052");

statusValue = T1:"drop table  dept_fk cascade";
expect_no_substr(statusValue.message, "ERROR 30052");

T1: """create table dept_fk like dept""";
T1: """insert into dept_fk select * from dept""";

T1: """create table emp_fk(
    employeeno DECIMAL(4),
    ename VARCHAR(10),
    job VARCHAR(9),
    mgr DECIMAL(4),
    hiredate DATE,
    sal DECIMAL(7, 2),
    comm DECIMAL(7, 2),
    deptno DECIMAL(2) references dept_fk(deptno)
    )""";

T1:"insert into emp_fk select * from employee";

T1: "begin work";
T1: "INSERT INTO dept_fk VALUES(50, 'ACCOUNTING', 'NEW YORK'); ";

T2:"begin work";
statusValue = T2:"insert into emp_fk values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 50)";
expect_equal(statusValue.code, 8103);

statusValue = T2:"update emp_fk set deptno = 50";
expect_equal(statusValue.code, 8103);

statusValue = T2:"delete from emp_fk where deptno = 50";
expect_equal(statusValue.code, 0);

statusValue = T2:"insert into emp_fk values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 30)";
expect_equal(statusValue.code, 0);

T1:"commit";

statusValue = T2:"insert into emp_fk values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 50)";
expect_equal(statusValue.code, 0);

}

#forign key  -- update parent table ,insert or update or delele subtable
TestCase CASE133
{
    Terminal T1 T2;
statusValue = T1:"drop table  emp_fk cascade";
expect_no_substr(statusValue.message, "ERROR 30052");

statusValue = T1:"drop table  dept_fk cascade";
expect_no_substr(statusValue.message, "ERROR 30052");

T1: """create table dept_fk like dept""";
T1: """insert into dept_fk select * from dept""";

T1: """create table emp_fk(
    employeeno DECIMAL(4),
    ename VARCHAR(10),
    job VARCHAR(9),
    mgr DECIMAL(4),
    hiredate DATE,
    sal DECIMAL(7, 2),
    comm DECIMAL(7, 2),
    deptno DECIMAL(2) references dept_fk(deptno)
    )""";

T1:"insert into emp_fk select * from employee where deptno > 10";

T1: "begin work";
T1: "update dept_fk set deptno = 50 where deptno = 10 ";

T2:"begin work";
statusValue = T2:"insert into emp_fk values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)";
expect_equal(statusValue.code, 30052);

statusValue = T2:"update emp_fk set deptno = 10";
expect_equal(statusValue.code, 30052);

statusValue = T2:"delete from emp_fk where deptno = 10";
expect_equal(statusValue.code, 0);

statusValue = T2:"insert into emp_fk values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 50)";
expect_equal(statusValue.code, 30052);

T1:"rollback";

statusValue = T2:"insert into emp_fk values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)";
expect_equal(statusValue.code, 0);

}

#forign key  -- for update parent table ,insert or update or delele subtable
TestCase CASE134
{
    Terminal T1 T2;
statusValue = T1:"drop table  emp_fk cascade";
expect_no_substr(statusValue.message, "ERROR 30052");

statusValue = T1:"drop table  dept_fk cascade";
expect_no_substr(statusValue.message, "ERROR 30052");

T1: """create table dept_fk like dept""";
T1: """insert into dept_fk select * from dept""";

T1: """create table emp_fk(
    employeeno DECIMAL(4),
    ename VARCHAR(10),
    job VARCHAR(9),
    mgr DECIMAL(4),
    hiredate DATE,
    sal DECIMAL(7, 2),
    comm DECIMAL(7, 2),
    deptno DECIMAL(2) references dept_fk(deptno)
    )""";

T1:"insert into emp_fk select * from employee where deptno > 10";

T1: "begin work";
T1: "select * from dept_fk where  deptno = 10 for update ";

T2:"begin work";
statusValue = T2:"insert into emp_fk values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)";
expect_equal(statusValue.code, 30052);

statusValue = T2:"update emp_fk set deptno = 10";
expect_equal(statusValue.code, 30052);

statusValue = T2:"delete from emp_fk where deptno = 10";
expect_equal(statusValue.code, 0);

statusValue = T2:"insert into emp_fk values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 20)";
expect_equal(statusValue.code, 0);

T1:"rollback";

statusValue = T2:"insert into emp_fk values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)";
expect_equal(statusValue.code, 0);

}

#forign key  -- insert subtable , parent table check lock
TestCase CASE135
{
    Terminal T1 T2;
statusValue = T1:"drop table  emp_fk cascade";
expect_no_substr(statusValue.message, "ERROR 30052");

statusValue = T1:"drop table  dept_fk cascade";
expect_no_substr(statusValue.message, "ERROR 30052");

T1: """create table dept_fk like dept""";
T1: """insert into dept_fk select * from dept""";

T1: """create table emp_fk(
    employeeno DECIMAL(4),
    ename VARCHAR(10),
    job VARCHAR(9),
    mgr DECIMAL(4),
    hiredate DATE,
    sal DECIMAL(7, 2),
    comm DECIMAL(7, 2),
    deptno DECIMAL(2) references dept_fk(deptno)
    )""";

T1:"insert into emp_fk select * from employee";

T1: "begin work";
T1: "insert into emp_fk values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10) ";

T2:"begin work";
statusValue = T2:"select * from dept_fk where  deptno = 10 for update ";
expect_equal(statusValue.code, 30052);

statusValue = T2:"delete from dept_fk where deptno = 10 ";
expect_equal(statusValue.code, 30052);

statusValue = T2:"update dept_fk set dname ='RESEARCH' where deptno = 10 ";
expect_equal(statusValue.code, 30052);


statusValue = T2:"insert into emp_fk values(7890, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)";
expect_equal(statusValue.code, 0);

T1:"rollback";

statusValue = T2:"insert into emp_fk values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)";
expect_equal(statusValue.code, 0);

}


#forign key  -- update subtable , parent table check lock
TestCase CASE136
{
    Terminal T1 T2;
statusValue = T1:"drop table  emp_fk cascade";
expect_no_substr(statusValue.message, "ERROR 30052");

statusValue = T1:"drop table  dept_fk cascade";
expect_no_substr(statusValue.message, "ERROR 30052");

T1: """create table dept_fk like dept""";
T1: """insert into dept_fk select * from dept""";

T1: """create table emp_fk(
    employeeno DECIMAL(4),
    ename VARCHAR(10),
    job VARCHAR(9),
    mgr DECIMAL(4),
    hiredate DATE,
    sal DECIMAL(7, 2),
    comm DECIMAL(7, 2),
    deptno DECIMAL(2) references dept_fk(deptno)
    )""";

T1:"insert into emp_fk select * from employee";

T1: "begin work";
T1: "update emp_fk set deptno = 20 where deptno = 10";

T2:"begin work";
statusValue = T2:"select * from dept_fk where  deptno = 10 for update ";
expect_equal(statusValue.code, 30052);

statusValue = T2:"delete from dept_fk where deptno = 20 ";
expect_equal(statusValue.code, 30052);

statusValue = T2:"update dept_fk set dname = 'RESEARCH' where deptno = 10 ";
expect_equal(statusValue.code, 30052);

statusValue = T2:"insert into emp_fk values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 20)";
expect_equal(statusValue.code, 0);

statusValue = T2:"insert into emp_fk values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)";
expect_equal(statusValue.code, 0);

T1:"rollback";

statusValue = T2:"insert into emp_fk values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)";
expect_equal(statusValue.code, 0);

}

#forign key  -- delete or for update subtable , parent table check lock
TestCase CASE137
{
    Terminal T1 T2;
statusValue = T1:"drop table  emp_fk cascade";
expect_no_substr(statusValue.message, "ERROR 30052");

statusValue = T1:"drop table  dept_fk cascade";
expect_no_substr(statusValue.message, "ERROR 30052");

T1: """create table dept_fk like dept""";
T1: """insert into dept_fk select * from dept""";

T1: """create table emp_fk(
    employeeno DECIMAL(4),
    ename VARCHAR(10),
    job VARCHAR(9),
    mgr DECIMAL(4),
    hiredate DATE,
    sal DECIMAL(7, 2),
    comm DECIMAL(7, 2),
    deptno DECIMAL(2) references dept_fk(deptno)
    )""";

T1:"insert into emp_fk select * from employee";

T1: "begin work";
T1: "delete from emp_fk where deptno = 10";

T2:"begin work";
statusValue = T2:"select * from dept_fk where  deptno = 10 for update ";
expect_equal(statusValue.code, 0);

statusValue = T2:"delete from dept_fk where deptno = 10 ";
expect_equal(statusValue.code, 0);

statusValue = T2:"update dept_fk set dname = 'RESEARCH' where deptno = 10 ";
expect_equal(statusValue.code, 0);

statusValue = T2:"insert into emp_fk values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)";
expect_equal(statusValue.code, 0);

statusValue = T2:"insert into emp_fk values(7890, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)";
expect_equal(statusValue.code, 0);

T2:"rollback";

T1:"rollback";

statusValue = T2:"insert into emp_fk values(7369, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)";
expect_equal(statusValue.code, 0);

T2:"rollback";
T1:"rollback";
T1: "begin work";
T1: "select * from emp_fk where deptno = 10 for update";


T2: "begin work";
T2: "select * from dept_fk where deptno = 10 for update";
T2:"rollback";
T1:"rollback";

}

# Savepoint + is LOCK  rollback
TestCase CASE138
{
    Terminal T1 T2;
T1: "cqd traf_savepoints 'on'";
T2: "cqd traf_savepoints 'on'";

statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

T1: "begin work";
T1: "begin savepoint";
T1: "select * from emp_temp";  # is lock

T2: "begin work";
statusValue = T2:"select * from emp_temp for update";
expect_equal(statusValue.code, 30052);

# savepoint
T1: "rollback savepoint";

T2: "begin work";
statusValue = T2:"select * from emp_temp for update";
expect_equal(statusValue.code, 0);

T1: "commit";
}

# Savepoint + is LOCK  commit
TestCase CASE139
{
    Terminal T1 T2;
T1: "cqd traf_savepoints 'on'";
T2: "cqd traf_savepoints 'on'";

statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

T1: "begin work";
T1: "begin savepoint";
T1: "select * from emp_temp";  # is lock

T2: "begin work";
statusValue = T2:"select * from emp_temp for update";
expect_equal(statusValue.code, 30052);

# savepoint
T1: "commit savepoint";

T2: "begin work";
statusValue = T2:"select * from emp_temp for update";
expect_equal(statusValue.code, 30052);

T1: "commit";

T2: "begin work";
statusValue = T2:"select * from emp_temp for update";
expect_equal(statusValue.code, 0);
}

# Savepoint + ix LOCK  rollback
TestCase CASE140
{
    Terminal T1 T2;
T1: "cqd traf_savepoints 'on'";
T2: "cqd traf_savepoints 'on'";

statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

T1: "begin work";
T1: "begin savepoint";
T1: "delete from emp_temp where employeeno = '7788'";  # ix lock

T2: "begin work";
statusValue = T2:"select * from emp_temp for update";
expect_equal(statusValue.code, 30052);

# savepoint
T1: "rollback savepoint";

T2: "begin work";
statusValue = T2:"select * from emp_temp for update";
expect_equal(statusValue.code, 0);

T1: "commit";
}

# Savepoint + ix LOCK  commit
TestCase CASE141
{
    Terminal T1 T2;
T1: "cqd traf_savepoints 'on'";
T2: "cqd traf_savepoints 'on'";

statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

T1: "begin work";
T1: "begin savepoint";
T1: "delete from emp_temp where employeeno = '7788'";  # ix lock

T2: "begin work";
statusValue = T2:"select * from emp_temp for update";
expect_equal(statusValue.code, 30052);

# savepoint
T1: "commit savepoint";

T2: "begin work";
statusValue = T2:"select * from emp_temp for update";
expect_equal(statusValue.code, 30052);

T1: "commit";

T2: "begin work";
statusValue = T2:"select * from emp_temp for update";
expect_equal(statusValue.code, 0);

}

# Savepoint + u LOCK  rollback
TestCase CASE142
{
    Terminal T1 T2;
T1: "cqd traf_savepoints 'on'";
T2: "cqd traf_savepoints 'on'";

statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

T1: "begin work";
T1: "begin savepoint";
T1: "select * from emp_temp where employeeno = '7788' for update";  # u lock

T2: "begin work";
statusValue = T2:"select * from emp_temp where employeeno = '7788' for update";
expect_equal(statusValue.code, 30052);

# savepoint
T1: "rollback savepoint";

T2: "begin work";
statusValue = T2:"select * from emp_temp where employeeno = '7788' for update";
expect_equal(statusValue.code, 0);

T1: "commit";
}

# Savepoint + u LOCK  commit
TestCase CASE143
{
    Terminal T1 T2;
T1: "cqd traf_savepoints 'on'";
T2: "cqd traf_savepoints 'on'";

statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

T1: "begin work";
T1: "begin savepoint";
T1: "select * from emp_temp where employeeno = '7788' for update";  # u lock

T2: "begin work";
statusValue = T2:"select * from emp_temp where employeeno = '7788' for update";
expect_equal(statusValue.code, 30052);

# savepoint
T1: "commit savepoint";
T2: "begin work";
statusValue = T2:"select * from emp_temp where employeeno = '7788' for update";
expect_equal(statusValue.code, 30052);

T1: "commit";

T2: "begin work";
statusValue = T2:"select * from emp_temp where employeeno = '7788' for update";
expect_equal(statusValue.code, 0);
}

# Savepoint + x row LOCK     rollback
TestCase CASE144
{
    Terminal T1 T2;
T1: "cqd traf_savepoints 'on'";
T2: "cqd traf_savepoints 'on'";

statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

T1: "begin work";
T1: "begin savepoint";
T1: "delete from emp_temp where employeeno = '7788'";  # x lock

T2: "begin work";
statusValue = T2:"delete from emp_temp where employeeno = '7788'";
expect_equal(statusValue.code, 30052);

# savepoint
T1: "rollback savepoint";
statusValue = T2:"delete from emp_temp where employeeno = '7788'";
expect_equal(statusValue.code, 0);

T1: "commit";
}
# Savepoint + x -- row LOCK  commit
TestCase CASE145
{
    Terminal T1 T2;
T1: "cqd traf_savepoints 'on'";
T2: "cqd traf_savepoints 'on'";

statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

T1: "begin work";
T1: "begin savepoint";
T1: "delete from emp_temp where employeeno = '7788'";  # x lock

T2: "begin work";
statusValue = T2:"delete from emp_temp where employeeno = '7788'";
expect_equal(statusValue.code, 30052);

# savepoint
T1: "commit savepoint";
statusValue = T2:"delete from emp_temp where employeeno = '7788'";
expect_equal(statusValue.code, 30052);

T1: "commit";

statusValue = T2:"delete from emp_temp where employeeno = '7788'";
expect_equal(statusValue.code, 0);
}

# Savepoint + x -- table LOCK  rollback
TestCase CASE146
{
    Terminal T1 T2;
T1: "cqd traf_savepoints 'on'";
T2: "cqd traf_savepoints 'on'";

statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

T1: "begin work";
T1: "begin savepoint";
T1: "select * from emp_temp for update";  # x  table lock

T2: "begin work";
statusValue = T2:"delete from emp_temp where employeeno = '7788'";
expect_equal(statusValue.code, 30052);

# savepoint
T1: "rollback savepoint";
statusValue = T2:"delete from emp_temp where employeeno = '7788'";
expect_equal(statusValue.code, 0);

T1: "commit";
}
# Savepoint + x -- table LOCK  commit
TestCase CASE147
{
    Terminal T1 T2;
T1: "cqd traf_savepoints 'on'";
T2: "cqd traf_savepoints 'on'";

statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

T1: "begin work";
T1: "begin savepoint";
T1: "select * from emp_temp for update";  # x table lock

T2: "begin work";
statusValue = T2:"delete from emp_temp where employeeno = '7788'";
expect_equal(statusValue.code, 30052);

# savepoint
T1: "commit savepoint";
statusValue = T2:"delete from emp_temp where employeeno = '7788'";
expect_equal(statusValue.code, 30052);

T1: "commit";

statusValue = T2:"delete from emp_temp where employeeno = '7788'";
expect_equal(statusValue.code, 0);
}


# transaction 1 add is lock，savepoint verify lock
TestCase CASE148
{
    Terminal T1 T2;
T1: "cqd traf_savepoints 'on'";
T2: "cqd traf_savepoints 'on'";

statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

T1: "begin work";
T1: "select * from emp_temp";  # is lock

T2: "begin work";
T1: "begin savepoint";
statusValue = T2:"select * from emp_temp for update";
expect_equal(statusValue.code, 30052);

T1: "commit";

T2: "begin work";
statusValue = T2:"drop table emp_temp";
expect_equal(statusValue.code, 0);
T2: "commit";
}

# transaction 1 add ix lock，savepoint verify lock
TestCase CASE149
{
    Terminal T1 T2;
T1: "cqd traf_savepoints 'on'";
T2: "cqd traf_savepoints 'on'";

statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

T1: "begin work";
T1: "delete from emp_temp where employeeno=7788";  # ix lock

T2: "begin work";
T1: "begin savepoint";
statusValue = T2:"select * from emp_temp for update";
expect_equal(statusValue.code, 30052);

T1: "commit";

T2: "begin work";
statusValue = T2:"drop table emp_temp";
expect_equal(statusValue.code, 0);
T2: "commit";
}

# transaction 1 add x row lock，savepoint verify lock
TestCase CASE150
{
    Terminal T1 T2;
T1: "cqd traf_savepoints 'on'";
T2: "cqd traf_savepoints 'on'";

statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

T1: "begin work";
T1: "delete from emp_temp where employeeno=7788";  # x lock

T2: "begin work";
T1: "begin savepoint";
statusValue = T2:"delete from emp_temp where employeeno=7788";
expect_equal(statusValue.code, 30052);

T1: "commit";

T2: "begin work";
statusValue = T2:"delete from emp_temp where employeeno=7788";
expect_equal(statusValue.code, 0);
T2: "commit";

}
# transaction 1 add x table lock，savepoint verify lock
TestCase CASE151
{
    Terminal T1 T2;
T1: "cqd traf_savepoints 'on'";
T2: "cqd traf_savepoints 'on'";

statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

T1: "begin work";
T1: "select * from emp_temp for update";  # x lock

T2: "begin work";
T1: "begin savepoint";
statusValue = T2:"delete from emp_temp where employeeno=7788";
expect_equal(statusValue.code, 30052);

T1: "commit";

T2: "begin work";
statusValue = T2:"delete from emp_temp where employeeno=7788";
expect_equal(statusValue.code, 0);
T2: "commit";

}

# transaction 1 add U row lock，savepoint verify lock
TestCase CASE152
{
    Terminal T1 T2;
T1: "cqd traf_savepoints 'on'";
T2: "cqd traf_savepoints 'on'";

statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

T1: "begin work";
T1: "select * from emp_temp where employeeno =7788 for update";  # U lock

T2: "begin work";
T1: "begin savepoint";
statusValue = T2:"select * from emp_temp where employeeno =7788 for update";
expect_equal(statusValue.code, 30052);

T1: "commit";

T2: "begin work";
statusValue = T2:"select * from emp_temp where employeeno =7788 for update";
expect_equal(statusValue.code, 0);
T2: "commit";
}

# 2 Savepoint verify lock, is-x-lock conflict
TestCase CASE153
{
    Terminal T1 T2;
T1: "cqd traf_savepoints 'on'";
T2: "cqd traf_savepoints 'on'";

statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

T1: "begin work";
T1: "begin savepoint";
statusValue = T1:"select * from emp_temp";  # is lock
expect_equal(statusValue.code, 0);

T2: "begin work";
T2: "begin savepoint";
statusValue = T2:"select * from emp_temp for update";
expect_equal(statusValue.code, 30052);

T1: "rollback savepoint";

T2: "begin work";
T2: "begin savepoint";
statusValue = T2:"select * from emp_temp where employeeno =7788 for update";
expect_equal(statusValue.code, 0);
T2: "commit";
}

# 2 Savepoint verify lock, ix-x-lock conflict
TestCase CASE154
{
    Terminal T1 T2;
T1: "cqd traf_savepoints 'on'";
T2: "cqd traf_savepoints 'on'";

statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

T1: "begin work";
T1: "begin savepoint";
statusValue = T1:"update emp_temp set sal = 7800 where employeeno = 7788 ";  # ix lock
expect_equal(statusValue.code, 0);

T2: "begin work";
T2: "begin savepoint";
statusValue = T2:"select * from emp_temp for update";
expect_equal(statusValue.code, 30052);

T1: "rollback savepoint";

T2: "begin work";
T2: "begin savepoint";
statusValue = T2:"select * from emp_temp where employeeno =7788 for update";
expect_equal(statusValue.code, 0);
T2: "commit";
}

# 2 Savepoint verify lock, x-x-row lock conflict
TestCase CASE155
{
    Terminal T1 T2;
T1: "cqd traf_savepoints 'on'";
T2: "cqd traf_savepoints 'on'";

statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

T1: "begin work";
T1: "begin savepoint";
statusValue = T1:"update emp_temp set sal = 7800 where employeeno = 7788 ";  # x lock
expect_equal(statusValue.code, 0);

T2: "begin work";
T2: "begin savepoint";
statusValue = T2:"update emp_temp set sal = 7800 where employeeno = 7788";
expect_equal(statusValue.code, 30052);

T1: "rollback savepoint";

T2: "begin work";
T2: "begin savepoint";
statusValue = T2:"update emp_temp set sal = 7800 where employeeno = 7788";
expect_equal(statusValue.code, 0);
T2: "commit";
}


# 2 Savepoint verify lock, x-x-table lock conflict
TestCase CASE156
{
    Terminal T1 T2;
T1: "cqd traf_savepoints 'on'";
T2: "cqd traf_savepoints 'on'";

statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

T1: "begin work";
T1: "begin savepoint";
statusValue = T1:"select * from emp_temp for update ";  # x table lock
expect_equal(statusValue.code, 0);

T2: "begin work";
T2: "begin savepoint";
statusValue = T2:"select * from emp_temp for update";  # x table lock
expect_equal(statusValue.code, 30052);

T1: "rollback savepoint";

T2: "begin work";
T2: "begin savepoint";
statusValue = T2:"select * from emp_temp for update";
expect_equal(statusValue.code, 0);
T2: "commit";
}

# 2 Savepoint verify lock, u-u-row lock conflict
TestCase CASE157
{
    Terminal T1 T2;
T1: "cqd traf_savepoints 'on'";
T2: "cqd traf_savepoints 'on'";

statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

T1: "begin work";
T1: "begin savepoint";
statusValue = T1:"select * from emp_temp where employeeno =7788 for update";  # u row lock
expect_equal(statusValue.code, 0);

T2: "begin work";
T2: "begin savepoint";
statusValue = T2:"select * from emp_temp where employeeno =7788 for update";  # u row lock
expect_equal(statusValue.code, 30052);

T1: "rollback savepoint";

T2: "begin work";
T2: "begin savepoint";
statusValue = T2:"select * from emp_temp where employeeno =7788 for update";
expect_equal(statusValue.code, 0);
# Check to see if the lock is released
T2: "commit";
}

# savepoint deadlock --sigle table diff row
TestCase CASE158
{
    Terminal T1 T2;
T1: "cqd traf_savepoints 'on'";
T2: "cqd traf_savepoints 'on'";

statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

T1: "begin work";
T1: "begin savepoint";
statusValue = T1:"update emp_temp set sal = 7800 where employeeno = 7788";  # x row lock
expect_equal(statusValue.code, 0);

T2: "begin work";
T2: "begin savepoint";
statusValue = T2:"update emp_temp set sal = 7800 where employeeno = 7792";  # x row lock
expect_equal(statusValue.code, 0);

statusValue = T2:"update emp_temp set sal = 7000 where employeeno=7788";  # x row lock
expect_equal(statusValue.code, 30052);

statusValue = T1:"update emp_temp set sal = 7800 where employeeno = 7792";  # x row lock
expect_equal(statusValue.code, 0);

T1: "rollback savepoint";

T2: "begin work";
T2: "begin savepoint";
statusValue = T2:"select * from emp_temp where employeeno =7788 for update";
expect_equal(statusValue.code, 0);
# Check to see if the lock is released
T2: "commit";
}

# savepoint deadlock multilist-table
TestCase CASE159
{
    Terminal T1 T2;
T1: "cqd traf_savepoints 'on'";
T2: "cqd traf_savepoints 'on'";

statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

T1: "drop table emp_temp1 cascade";
T1: "create table emp_temp1 like  employee";
T1: "insert into emp_temp1 select * from employee";

T1: "begin work";
T1: "begin savepoint";
statusValue = T1:"update emp_temp set sal = 7800 where employeeno = 7788";  # x row lock
expect_equal(statusValue.code, 0);

T2: "begin work";
T2: "begin savepoint";
statusValue = T2:"delete from emp_temp1 where employeeno = 7792";  # x row lock
expect_equal(statusValue.code, 0);

statusValue = T2:"update emp_temp set sal = 7000 where employeeno=7788";  # x row lock
expect_equal(statusValue.code, 30052);

statusValue = T1:"delete from emp_temp1 where employeeno = 7792";  # x row lock
expect_equal(statusValue.code, 0);

T1: "rollback savepoint";

T2: "begin work";
T2: "begin savepoint";
statusValue = T2:"select * from emp_temp where employeeno =7788 for update";
expect_equal(statusValue.code, 0);
# Check to see if the lock is released
T2: "commit";
}

# 1 transaction contain 2 savepoint(after rollback ，start begin)(u-u)
TestCase CASE160
{
    Terminal T1 T2;
T1: "cqd traf_savepoints 'on'";
T2: "cqd traf_savepoints 'on'";

statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

T1: "begin work";
T1: "begin savepoint";
statusValue = T1:"select * from emp_temp where employeeno =7788 for update";  # u row lock
expect_equal(statusValue.code, 0);

T2: "begin work";
T2: "begin savepoint";
statusValue = T2:"select * from emp_temp where employeeno =7788 for update";  # u row lock
expect_equal(statusValue.code, 30052);

T1: "rollback savepoint";

T1: "begin savepoint";
statusValue = T1:"select * from emp_temp where employeeno =7788 for update";  # u row lock
expect_equal(statusValue.code, 0);

T2: "begin work";
T2: "begin savepoint";
statusValue = T2:"select * from emp_temp where employeeno =7788 for update";  # u row lock
expect_equal(statusValue.code, 30052);

T1: "rollback savepoint";

T2: "begin work";
T2: "begin savepoint";
statusValue = T2:"select * from emp_temp where employeeno =7788 for update";
expect_equal(statusValue.code, 0);
# Check to see if the lock is released
T2: "commit";
}

# 1 transaction contain 2 savepoint(after rollback ，start begin)（x-x)
TestCase CASE161
{
    Terminal T1 T2;
T1: "cqd traf_savepoints 'on'";
T2: "cqd traf_savepoints 'on'";

statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

T1: "begin work";
T1: "begin savepoint";
statusValue = T1:"update emp_temp set sal = 7000 where employeeno=7788";  # x row lock
expect_equal(statusValue.code, 0);

T2: "begin work";
T2: "begin savepoint";
statusValue = T2:"update emp_temp set sal = 7000 where employeeno=7788";  # x row lock
expect_equal(statusValue.code, 30052);

T1: "rollback savepoint";

T1: "begin savepoint";
statusValue = T1:"update emp_temp set sal = 7800 where employeeno = 7788";  # x row lock
expect_equal(statusValue.code, 0);

T2: "begin work";
T2: "begin savepoint";
statusValue = T2:"update emp_temp set sal = 7800 where employeeno = 7788";  # x row lock
expect_equal(statusValue.code, 30052);

T1: "rollback savepoint";

T2: "begin work";
T2: "begin savepoint";
statusValue = T2:"update emp_temp set sal = 7000 where employeeno=7788";
expect_equal(statusValue.code, 0);
# Check to see if the lock is released
T2: "commit";
}


# 1 transaction contain A variety of lock
TestCase CASE162
{
    Terminal T1 T2;
statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

# u-lock
T1: "begin work";
statusValue = T1:"select * from emp_temp";  # is row lock
expect_equal(statusValue.code, 0);

T2: "begin work";
statusValue = T2:"select * from emp_temp for update";  # x table lock
expect_equal(statusValue.code, 30052);

# ix and x lock
statusValue = T1:"delete from employee where employeeno =7788 ";  # ix row lock
expect_equal(statusValue.code, 0);

T2: "begin work";
statusValue = T2:"select * from emp_temp for update";  # x table lock
expect_equal(statusValue.code, 30052);

# u lock
statusValue = T1:"select * from emp_temp  where employeeno = 7902 for update";  # u row lock
expect_equal(statusValue.code, 0);

T2: "begin work";
statusValue = T2:"select * from emp_temp for update";  # x table lock
expect_equal(statusValue.code, 30052);

# add x_table lock
statusValue = T1:"select * from emp_temp for update";  # u row lock
expect_equal(statusValue.code, 0);

T2: "begin work";
statusValue = T2:"select * from emp_temp for update";  # x table lock
expect_equal(statusValue.code, 30052);

T1: "rollback";

T2: "begin work";
statusValue = T2:"select * from emp_temp for update";
expect_equal(statusValue.code, 0);
# Check to see if the lock is released
T2: "commit";
}

# 1 transaction savepoint contain a variety of lock
TestCase CASE163
{
    Terminal T1 T2;
statusValue = T1:"drop table emp_temp cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_temp like  employee";
T1: "insert into emp_temp select * from employee";

# u-lock
T1: "begin work";
T1: "begin savepoint";
statusValue = T1:"select * from emp_temp";  # is row lock
expect_equal(statusValue.code, 0);

T2: "begin work";
T2: "begin savepoint";
statusValue = T2:"select * from emp_temp for update";  # x table lock
expect_equal(statusValue.code, 30052);

# ix and x lock
statusValue = T1:"delete from employee where employeeno =7788 ";  # ix row lock
expect_equal(statusValue.code, 0);

T2: "begin work";
T2: "begin savepoint";
statusValue = T2:"select * from emp_temp for update";  # x table lock
expect_equal(statusValue.code, 30052);

# u lock

T2: "begin work";
statusValue = T1:"select * from emp_temp  where employeeno = 7902 for update";  # u row lock
expect_equal(statusValue.code, 0);

T2: "begin work";
T2: "begin savepoint";
statusValue = T2:"select * from emp_temp for update";  # x table lock
expect_equal(statusValue.code, 30052);

# add x_table lock

T2: "begin work";
statusValue = T1:"select * from emp_temp for update";  # u row lock
expect_equal(statusValue.code, 0);

T2: "begin work";
T2: "begin savepoint";
statusValue = T2:"select * from emp_temp for update";  # x table lock
expect_equal(statusValue.code, 30052);

T1: "rollback savepoint";

T2: "begin work";
T2: "begin savepoint";
statusValue = T2:"select * from emp_temp for update";
expect_equal(statusValue.code, 0);
# Check to see if the lock is released
T2: "commit";
}

#回滚多个savepoint
TestCase CASE164{
    Terminal T1 T2;
T1:"drop table test_tb cascade";
T1:"create table  test_tb(a int primary key)";

T1:"begin work";
T1:"insert into test_tb values (1);";
T1:"insert into test_tb values (2);";

T1: "begin savepoint";
T1: "insert into test_tb values(3);";
T1: "rollback savepoint;";
T1: "insert into test_tb values(3);";
T1: "rollback savepoint;";
T1: "insert into test_tb values(3);";

statusValue = T2: "insert into test_tb  values(3);";
expect_equal(statusValue.code, 30052);

T1: "rollback savepoint;";
T1: "insert into test_tb values(3);";
T1: "rollback savepoint;";
T1: "insert into test_tb values(3);";
T1: "rollback savepoint;";
T1: "insert into test_tb values(3);";
T1: "rollback savepoint;";

statusValue = T2: "insert into test_tb  values(3);";
expect_equal(statusValue.code, 0);

T1:"commit";
T2:"commit";

}



#region split
#is -lock  region split
TestCase CASE165
{
    Terminal T1 T2;

statusValue = T1:"drop table emp_split cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_split like  employee";
T1: "insert into emp_split select * from employee";

T1: "begin work";
T1: "select * from emp_split";  # is lock

# region split
Shell("python RegionSplit.py");
# hbase shell split'TRAFODION.S_LOCKREGRESSION.EMP_SPLIT','e'

T2: "begin work";
statusValue = T2:"select * from emp_split for update";
expect_equal(statusValue.code, 30052);

T1: "commit";

T2: "begin work";
statusValue = T2:"select * from emp_split for update";
expect_equal(statusValue.code, 0);
T2: "commit";
}

# ix-lock region split
TestCase CASE166
{
    Terminal T1 T2;

statusValue = T1:"drop table emp_split cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_split like  employee";
T1: "insert into emp_split select * from employee";

T1: "begin work";
T1: "delete from emp_split where employeeno = 7788";  # ix lock

# region split
Shell("python RegionSplit.py");
# hbase shell split'TRAFODION.S_LOCKREGRESSION.EMP_SPLIT','e'

T2: "begin work";
statusValue = T2:"select * from emp_split for update";
expect_equal(statusValue.code, 30052);

T1: "commit";

T2: "begin work";
statusValue = T2:"select * from emp_split for update";
expect_equal(statusValue.code, 0);
T2: "commit";
}

# x-row lock region split
TestCase CASE167
{
    Terminal T1 T2;

statusValue = T1:"drop table emp_split cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_split like  employee";
T1: "insert into emp_split select * from employee";

T1: "begin work";
T1: "update emp_split set sal = 7800 where employeeno = 7788";  # x lock

# region split
Shell("python RegionSplit.py");
# hbase shell split'TRAFODION.S_LOCKREGRESSION.EMP_SPLIT','e'

T2: "begin work";
statusValue = T2:"update emp_split set sal = 7800 where employeeno = 7788";
expect_equal(statusValue.code, 30052);

T1: "commit";

T2: "begin work";
statusValue = T2:"select * from emp_split for update";
expect_equal(statusValue.code, 0);
T2: "commit";
}

# x-table lock region split
TestCase CASE168
{
    Terminal T1 T2;

statusValue = T1:"drop table emp_split cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_split like  employee";
T1: "insert into emp_split select * from employee";

T1: "begin work";
T1: "select * from emp_split for update";  # x lock

# region split
Shell("python RegionSplit.py");
# hbase shell split'TRAFODION.S_LOCKREGRESSION.EMP_SPLIT','e'

T2: "begin work";
statusValue = T2:"select * from emp_split for update";
expect_equal(statusValue.code, 30052);

T1: "commit";

T2: "begin work";
statusValue = T2:"select * from emp_split for update";
expect_equal(statusValue.code, 0);
T2: "commit";
}

# u lock region split
TestCase CASE169
{
    Terminal T1 T2;

statusValue = T1:"drop table emp_split cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "create table emp_split like  employee";
T1: "insert into emp_split select * from employee";

T1: "begin work";
T1: "select * from emp_split where employeeno = 7788 for update";  # x lock

# region split
Shell("python RegionSplit.py");
# hbase shell split'TRAFODION.S_LOCKREGRESSION.EMP_SPLIT','e'

T2: "begin work";
statusValue = T2:"select * from emp_split where employeeno = 7788 for update";
expect_equal(statusValue.code, 30052);

T1: "commit";

T2: "begin work";
statusValue = T2:"select * from emp_split for update";
expect_equal(statusValue.code, 0);
T2: "commit";
}



















