Config
{
    """
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
    """
}

# TestCase
# CASE000
# {
# # Create common tables required for the test TestCase CASE00
# statusValue=:"drop schema lockinfo cascade";
# expect_no_substr(statusValue.message, "ERROR 30052");
# :"cleanup schema lockinfo";
# :"create schema  if not exists lockinfo";
# :"set schema lockinfo";
#
# :"drop table dept cascade";
# :"CREATE TABLE dept(deptno DECIMAL(2) not null primary key, dname VARCHAR(14),loc VARCHAR(13))";
# :"showddl dept";
# :"INSERT INTO dept VALUES(10, 'ACCOUNTING', 'NEW YORK')";
# :"INSERT INTO dept VALUES(20, 'RESEARCH', 'DALLAS')";
# :"INSERT INTO dept VALUES(30, 'SALES', 'CHICAGO')";
# :"INSERT INTO dept VALUES(40, 'OPERATIONS', 'BOSTON')";
#
# t2rs1 =:ResultSet("select * from dept where deptno = 10 for update");
# expect_equal(t2rs1, Tuple("((10,'ACCOUNTING','NEW YORK'),)"));
#
# :"drop table employee cascade";
# :"""CREATE TABLE employee
#    (
#     employeeno DECIMAL(4) NOT NULL primary key,
#     ename VARCHAR(10),
#     job VARCHAR(9),
#     mgr DECIMAL(4),
#     hiredate DATE,
#     sal DECIMAL(7, 2),
#     comm DECIMAL(7, 2),
#     deptno DECIMAL(2),
#     foreign key(deptno) references dept(deptno)
#     )
#      hbase_options
# 	(
#     data_block_encoding = 'fast_diff',
#     compression = 'snappy',
#     memstore_flush_size = '1073741824'
# 	)
# """;
#
# :"INSERT INTO employee VALUES(7369, 'SMITH', 'CLERK', 7902, DATE '1980-12-17', 800, NULL, 20)";
# :"INSERT INTO employee VALUES(7499, 'ALLEN', 'SALESMAN', 7698, DATE '1981-02-20', 1600, 300, 30)";
# :"INSERT INTO employee VALUES(7521, 'WARD', 'SALESMAN', 7698, DATE '1981-02-22', 1250, 500, 30)";
# :"INSERT INTO employee VALUES(7566, 'JONES', 'MANAGER', 7839, DATE '1981-04-02', 2975, NULL, 20)";
# :"INSERT INTO employee VALUES(7654, 'MARTIN', 'SALESMAN', 7698, DATE '1981-09-28', 1250, 1400, 30)";
# :"INSERT INTO employee VALUES(7698, 'BLAKE', 'MANAGER', 7839, DATE '1981-05-01', 2850, NULL, 30)";
# :"INSERT INTO employee VALUES(7782, 'CLARK', 'MANAGER', 7839, DATE '1981-07-09', 2450, NULL, 10)";
# :"INSERT INTO employee VALUES(7788, 'TAC-MD', 'ANALYST', 7566, DATE '1982-12-09', 3000, NULL, 20)";
# :"INSERT INTO employee VALUES(7839, 'KING', 'PRESIDENT', 7788, DATE '1981-11-17', 5000, NULL, 10)";
# :"INSERT INTO employee VALUES(7844, 'TURNER', 'SALESMAN', 7698, DATE '1981-09-08', 1500, 0, 30)";
# :"INSERT INTO employee VALUES(7876, 'ADAMS', 'CLERK', 7788, DATE '1983-01-12', 1100, NULL, 20)";
# :"INSERT INTO employee VALUES(7900, 'JAMES', 'CLERK', 7698, DATE '1981-12-03', 950, NULL, 30)";
# :"INSERT INTO employee VALUES(7902, 'FORD', 'ANALYST', 7566, DATE '1981-12-03', 3000, NULL, 20)";
# :"INSERT INTO employee VALUES(7934, 'MILLER', 'CLERK', 7782, DATE '1982-01-23', 1300, NULL, 10)";
# :"create index employee_index on employee(employeeno)";
# :"select * from employee";
#
# :"drop table salgrade cascade";
# :"""CREATE TABLE salgrade
#    (grade DECIMAL primary key,
#     losal DECIMAL,
#     hisal DECIMAL)""";
#
# :"showddl salgrade";
#
# :"INSERT INTO salgrade VALUES(1, 700, 1200)";
# :"INSERT INTO salgrade VALUES(2, 1201, 1400)";
# :"INSERT INTO salgrade VALUES(3, 1401, 2000)";
# :"INSERT INTO salgrade VALUES(4, 2001, 3000)";
# :"INSERT INTO salgrade VALUES(5, 3001, 9999)";
#
# :"SELECT * FROM salgrade";
#
# # large table
# :"create table largetable(id int not null primary key, name varchar(20))";
# :"upsert using load into largetable select element, cast('lock' || element as varchar(20)) from udf(series(1,150))";
#
# }


TestCase
CASE001
{
    :"begin work";
    :"select employeeno, ename, job  from employee where employeeno=7788";
    Shell("lockmanage.py");
    :"commit";

    :"begin work";
    :"select * from employee where employeeno >=7839 and employeeno<=7902";
   Shell("lockmanage.py");
    :"commit";

}

TestCase
CASE002
{
    :"begin work";
    :"update employee set ename = 'lockinfo' where employeeno = 7788";
    Shell("lockmanage.py");
    :"commit";

    :"begin work";
    :"update employee set ename = 'lockinfo'  where employeeno >=7839 and employeeno<=7902";
   Shell("lockmanage.py");
    :"commit";

}

TestCase
CASE003
{
    :"begin work";
    :"select * from employee where employeeno = 7788 for update";
    Shell("lockmanage.py");
    :"commit";

    :"begin work";
    :"select * from employee  where employeeno >=7839 and employeeno<=7902 for update";
   Shell("lockmanage.py");
    :"commit";

}

TestCase
CASE004
{
    :"begin work";
    :"insert into employee values(1234, 'LML', 'CLERK', 7782, DATE '1993-01-23', 2000, NULL, 10)";
    Shell("lockmanage.py");
    :"rollback";

}

TestCase
CASE005
{
    :"begin work";
    :" delete from employee where employeeno = 7369";
    Shell("lockmanage.py");
    :"rollback";
    
    :"begin work";
    :" delete from employee where employeeno > 7369";
    Shell("lockmanage.py");
    :"rollback";
}

