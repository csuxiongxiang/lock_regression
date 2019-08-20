Config
{
    """
    'host': '10.10.23.23',
    'port': 23400,
    'tenant_name': 'ESGYNDB',
    'schema': 's_lockplsql',
    'user': 'trafodion',
    'password': 'traf123',
    'charset': 'utf-8',
    'use_unicode': True,
    'get_warnings': True,
    'connection_timeout' : 6000
    """
}

TestCase
CASE000
{
    # Create common tables required for the test TestCase CASE00
statusValue =:"drop schema s_lockplsql cascade";
expect_no_substr(statusValue.message, "ERROR 30052");
:"cleanup schema s_lockplsql";
:"create schema  if not exists s_lockplsql";
:"set schema s_lockplsql";

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
:"create index idx_plsql on employee(employeeno);";
:"create view viewplsql as select * from employee where employeeno >= 7788;";
}

TestCase
CASE001
{
    Terminal
T1
T2;
T1: "begin work";

# is lock
T1: """begin
 for c in (select employeeno , ename from employee)
  loop
    dbms_output.put_line(c.employeeno || '   ' || c.ename);
 end loop;
 end;
 /""";

T2: "begin work";
statusValue = T2:"""begin
 for c in (select employeeno , ename from employee for update)
  loop
    dbms_output.put_line(c.employeeno || '   ' || c.ename);
 end loop;
 end;
 /""";

expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");
T2: "commit";

statusValue = T2:"select * from employee for update";

expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

# ls release
T1: "commit";
statusValue = T2:"select * from employee for update";
expect_equal(statusValue.code, 0);
expect_no_substr(statusValue.message, "ERROR 30052");
}

TestCase
CASE002
{
    Terminal
T1
T2;
T1: "begin work";

# is lock
T1: """begin
 for c in (select employeeno , ename from employee)
  loop
    dbms_output.put_line(c.employeeno || '   ' || c.ename);
 end loop;
 end;
 /""";

T2: "begin work";
statusValue = T2:"""begin
 for c in (select employeeno , ename from employee for update)
  loop
    dbms_output.put_line(c.employeeno || '   ' || c.ename);
 end loop;
 end;
 /""";

expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");
T2: "rollback";

statusValue = T2:"select * from employee for update";

expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

# ls release
T1: "rollback";
statusValue = T2:"select * from employee for update";
expect_equal(statusValue.code, 0);
expect_no_substr(statusValue.message, "ERROR 30052");
}

# ix Add IX lock in AnonymoUs
TestCase
CASE003
{
    Terminal
T1
T2;
T1: "begin work";

# ix lock
T1: """BEGIN
   DECLARE IXname char(20) :='ix_lock';
   DBMS_OUTPUT.PUT_LINE('Add IX lock in AnonymoUs');
   exec 'UPDATE employee SET ENAME = '''||IXname||'''  WHERE EMPLOYEENO = 7788 '; /*add X-row lock*/
END;
/""";

T2: "begin work";
statusValue = T2:"""begin
 for c in (select employeeno , ename from employee for update)
  loop
    dbms_output.put_line(c.employeeno || '   ' || c.ename);
 end loop;
 end;
 /""";

expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");
T2: "commit";

statusValue = T2:"select * from employee for update";

expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

# lx release
T1: "commit";
statusValue = T2:"select * from employee for update";
expect_equal(statusValue.code, 0);
expect_no_substr(statusValue.message, "ERROR 30052");
}

TestCase
CASE004
{
    Terminal
T1
T2;
T1: "begin work";

# ix lock
T1: """BEGIN
   DECLARE IXname char(20) :='ix_lock';
   DBMS_OUTPUT.PUT_LINE('Add IX lock in AnonymoUs');
   exec 'UPDATE employee SET ENAME = '''||IXname||'''  WHERE EMPLOYEENO = 7788'; /*add X-row lock*/
END;
/""";

T2: "begin work";
statusValue = T2:"""begin
 for c in (select employeeno , ename from employee for update)
  loop
    dbms_output.put_line(c.employeeno || '   ' || c.ename);
 end loop;
 end;
 /""";

expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");
T2: "rollback";

statusValue = T2:"select * from employee for update";

expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

# lx release
T1: "rollback";
statusValue = T2:"select * from employee for update";
expect_equal(statusValue.code, 0);
expect_no_substr(statusValue.message, "ERROR 30052");
}

# Add x-table lock in AnonymoUs
TestCase
CASE005
{
    Terminal
T1
T2;
T1: "begin work";

# x-table lock
T1: """begin
 for c in (select employeeno , ename from employee for update)
  loop
    dbms_output.put_line(c.employeeno || '   ' || c.ename);
 end loop;
 end;
 /""";

T2: "begin work";
statusValue = T2:"""begin
 for c in (select employeeno , ename from employee for update)
  loop
    dbms_output.put_line(c.employeeno || '   ' || c.ename);
 end loop;
 end;
 /""";

expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");
T2: "commit";

statusValue = T2:"select * from employee for update";

expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

# x table release
T1: "commit";
statusValue = T2:"select * from employee for update";
expect_equal(statusValue.code, 0);
expect_no_substr(statusValue.message, "ERROR 30052");
}

TestCase
CASE006
{
    Terminal
T1
T2;
T1: "begin work";

# x lock
T1: """begin
 for c in (select employeeno , ename from employee for update)
  loop
    dbms_output.put_line(c.employeeno || '   ' || c.ename);
 end loop;
 end;
 /""";

T2: "begin work";
statusValue = T2:"""begin
 for c in (select employeeno , ename from employee for update)
  loop
    dbms_output.put_line(c.employeeno || '   ' || c.ename);
 end loop;
 end;
 /""";

expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");
T2: "rollback";

statusValue = T2:"select * from employee for update";

expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

# x -table release
T1: "rollback";
statusValue = T2:"select * from employee for update";
expect_equal(statusValue.code, 0);
expect_no_substr(statusValue.message, "ERROR 30052");
}


# Add x-row lock in AnonymoUs
TestCase
CASE007
{
    Terminal
T1
T2;
T1: "begin work";

# x-row lock
T1: """BEGIN
   DECLARE IXname char(20) :='Xiang';
   DBMS_OUTPUT.PUT_LINE('X row lock AnonymoUs test');
   exec 'UPDATE employee SET ENAME = '''||IXname||'''  WHERE EMPLOYEENO = 7788 '; /*add X-row lock*/
END;
/""";

T2: "begin work";
statusValue = T2:"""BEGIN
   DECLARE IXname char(20) :='Xiang';
   DBMS_OUTPUT.PUT_LINE('X row lock AnonymoUs test');
   exec 'UPDATE employee SET ENAME = '''||IXname||'''  WHERE EMPLOYEENO = 7788 '; /*add X-row lock*/
END;
/""";

expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");
T2: "commit";

statusValue = T2:"select * from employee for update";

expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

# x row release
T1: "commit";
statusValue = T2:"select * from employee for update";
expect_equal(statusValue.code, 0);
expect_no_substr(statusValue.message, "ERROR 30052");
}

TestCase
CASE008
{
    Terminal
T1
T2;
T1: "begin work";

# x row lock
T1: """BEGIN
   DECLARE IXname char(20) :='Xiang';
   DBMS_OUTPUT.PUT_LINE('X row lock AnonymoUs test');
   exec 'UPDATE employee SET ENAME = '''||IXname||'''  WHERE EMPLOYEENO = 7788 '; /*add X-row lock*/
END;
/""";

T2: "begin work";
statusValue = T2:"""BEGIN
   DECLARE IXname char(20) :='Xiang';
   DBMS_OUTPUT.PUT_LINE('X row lock AnonymoUs test');
   exec 'UPDATE employee SET ENAME = '''||IXname||'''  WHERE EMPLOYEENO = 7788 '; /*add X-row lock*/
END;
/""";

expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");
T2: "rollback";

statusValue = T2:"select * from employee for update";

expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

# x -row release
T1: "rollback";
statusValue = T2:"select * from employee for update";
expect_equal(statusValue.code, 0);
expect_no_substr(statusValue.message, "ERROR 30052");
}


# Add u lock in AnonymoUs
TestCase
CASE009
{
    Terminal
T1
T2;
T1: "begin work";

# u lock
T1: """begin
 for c in (select employeeno , ename from employee where employeeno = 7788  for update)
  loop
    dbms_output.put_line(c.employeeno || '   ' || c.ename);
 end loop;
 end;
 /""";

T2: "begin work";
statusValue = T2:"""begin
 for c in (select employeeno , ename from employee where employeeno = 7788  for update)
  loop
    dbms_output.put_line(c.employeeno || '   ' || c.ename);
 end loop;
 end;
 /""";

expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");
T2: "commit";

statusValue = T2:"select * from employee for update";

expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

# u release
T1: "commit";
statusValue = T2:"select * from employee for update";
expect_equal(statusValue.code, 0);
expect_no_substr(statusValue.message, "ERROR 30052");
}

TestCase
CASE010
{
    Terminal
T1
T2;
T1: "begin work";

# u lock
T1: """begin
 for c in (select employeeno , ename from employee where employeeno = 7788  for update)
  loop
    dbms_output.put_line(c.employeeno || '   ' || c.ename);
 end loop;
 end;
 /""";

T2: "begin work";
statusValue = T2:"""begin
 for c in (select employeeno , ename from employee where employeeno = 7788  for update)
  loop
    dbms_output.put_line(c.employeeno || '   ' || c.ename);
 end loop;
 end;
 /""";

expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");
T2: "rollback";

statusValue = T2:"select * from employee for update";

expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

# x -row release
T1: "rollback";
statusValue = T2:"select * from employee for update";
expect_equal(statusValue.code, 0);
expect_no_substr(statusValue.message, "ERROR 30052");
}

# ########################################################
# #procedure
# ########################################################
# is procedure test
TestCase
CASE011
{

: """create or replace procedure test_is_lock() as
begin
 for c in (select employeeno , ename from employee)
  loop
    dbms_output.put_line(c.employeeno || '   ' || c.ename);
 end loop;
 end;
/""";

:"""CREATE OR REPLACE PROCEDURE test_x_table_lock() AS
begin
 for c in (select employeeno , ename from employee for update)
  loop
    dbms_output.put_line(c.employeeno || '   ' || c.ename);
 end loop;
 end;
/""";

:"""create or replace procedure test_Ix_lock() as
DECLARE
   c1 VARCHAR(10);
BEGIN
   SELECT 'Ix_LOCK' INTO c1 FROM DUAL ;
   exec 'UPDATE employee SET ENAME = '''||c1||'''  WHERE EMPLOYEENO = 7788 '; /*add X-row lock*/
   DBMS_OUTPUT.PUT_LINE('Ix lock procedure test');
END;
/""";

:"""create or replace procedure test_x_row_lock() as
declare
	c1 varchar(10);
begin
	select 'x_r_lock' into c1;
	exec 'UPDATE employee SET ENAME = '''||c1||'''  WHERE EMPLOYEENO = 7788 '; /*add X-row lock*/
	dbms_output.put_line('x row lock procedure test');
end;
/""";

:"""create or replace procedure test_u_lock() as
begin
	for c in (select employeeno , ename from employee  WHERE EMPLOYEENO = '7788' for update)
	loop
		dbms_output.put_line(c.employeeno || '   ' || c.ename);
	end loop;
end;
/""";
}

###################################
# function
###################################
# is function test
TestCase
CASE021
{
    Terminal
T1
T2;
T1: "drop function get_avg_islock cascade";
T1: """CREATE FUNCTION get_avg_islock() RETURNS (avg_lock INT) AS
BEGIN
 DECLARE cnt INT = 0;
 SELECT avg(sal) INTO cnt FROM employee
 WHERE JOB LIKE '%CLERK';

 RETURN cnt;
END;
/""";

T1: "drop function get_avg_x_Tablelock cascade";
T1: """create function get_avg_x_Tablelock() return(avg_lock INT) as
begin
	declare cnt int = 0;
	select avg(sal) into cnt from employee for update;
	return cnt;
END;
/""";

T1: "begin work";
T1: "select get_avg_islock() from dual";

T2: "begin work";
statusValue = T2:"select get_avg_x_Tablelock() from dual;";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"select * from employee for update";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

# is -row release
T1: "commit";
statusValue = T2:"select * from employee for update";
expect_no_substr(statusValue.message, "ERROR 30052");
}

# is rollback
TestCase
CASE022
{
    Terminal
T1
T2;

T1: "begin work";
T1: "select get_avg_islock() from dual";

T2: "begin work";
statusValue = T2:"select get_avg_x_Tablelock() from dual;";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"select * from employee for update";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

# is -lock release
T1: "rollback";
statusValue = T2:"select * from employee for update";
expect_no_substr(statusValue.message, "ERROR 30052");
}

TestCase
CASE023
{
    Terminal
T1
T2;
T1: "drop function get_avg_ixlock cascade";
T1: """create function get_avg_ixlock() RETURNS(avg_lock INT) as
begin
	declare cnt int = 0;
	update employee set ename ='ix_lock' where employeeno = '7788';
	select avg(sal) into cnt from employee where employeeno = '7788';
	return cnt;
end;
/""";

T1: "drop function get_avg_x_Tablelock cascade";
T1: """create function get_avg_x_Tablelock() return(avg_lock INT) as
begin
	declare cnt int = 0;
	select avg(sal) into cnt from employee for update;
	return cnt;
END;
/""";

T1: "begin work";
T1: "select get_avg_ixlock() from dual;";

T2: "begin work";
statusValue = T2:"select get_avg_x_Tablelock() from dual;";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"select * from employee for update";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

# ix release
T1: "commit";
statusValue = T2:"select * from employee for update";
expect_no_substr(statusValue.message, "ERROR 30052");
}

TestCase
CASE024
{
    Terminal
T1
T2;

T1: "begin work";
T1: "select get_avg_ixlock() from dual;";

T2: "begin work";
statusValue = T2:"select get_avg_x_Tablelock() from dual;";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"select * from employee for update";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

# ix release
T1: "rollback";
statusValue = T2:"select * from employee for update";
expect_no_substr(statusValue.message, "ERROR 30052");
}

TestCase
CASE025
{
    Terminal
T1
T2;
T1: "drop function get_avg_x_rowtablelock cascade";
T1: """create function get_avg_x_rowtablelock() return(avg_lock INT) as
begin
	declare cnt int = 0;
	update employee set ename ='ix_lock' where employeeno = '7788';
	select avg(sal) into cnt from employee where employeeno = '7788';
	return cnt;
end;
/""";

T1: "begin work";
T1: "select get_avg_x_rowtablelock() from dual;";

T2: "begin work";
statusValue = T2:"select get_avg_x_rowtablelock() from dual;";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"update employee set ename ='ix_lock' where employeeno = '7788';";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

# u release
T1: "commit";
statusValue = T2:"update employee set ename ='ix_lock' where employeeno = '7788';";
expect_no_substr(statusValue.message, "ERROR 30052");
}

TestCase
CASE026
{
    Terminal
T1
T2;

T1: "begin work";
T1: "select get_avg_x_rowtablelock() from dual;";

T2: "begin work";
statusValue = T2:"select get_avg_x_rowtablelock() from dual;";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"update employee set ename ='ix_lock' where employeeno = '7788';";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

# u release
T1: "rollback";
statusValue = T2:"update employee set ename ='ix_lock' where employeeno = '7788';";
expect_no_substr(statusValue.message, "ERROR 30052");
}

TestCase
CASE027
{
    Terminal
T1
T2;
T1: "drop function get_avg_ulock cascade";
T1: """create function get_avg_ulock() return(avg_lock INT) as
begin
	declare cnt int = 0;
	select avg(sal) into cnt from employee where employeeno = '7788' for update;
	return cnt;
end;
/""";

T1: "begin work";
T1: "select get_avg_ulock() from dual;";

T2: "begin work";
statusValue = T2:"select get_avg_ulock() from dual;";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"select * from employee where employeeno = '7788' for update";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

# u release
T1: "commit";
statusValue = T2:"select * from employee where employeeno = '7788' for update;";
expect_no_substr(statusValue.message, "ERROR 30052");
}

TestCase
CASE028
{
    Terminal
T1
T2;

T1: "begin work";
T1: "select get_avg_ulock() from dual;";

T2: "begin work";
statusValue = T2:"select get_avg_ulock() from dual;";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"select * from employee where employeeno = '7788' for update";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

# u release
T1: "rollback";
statusValue = T2:"select * from employee where employeeno = '7788' for update;";
expect_no_substr(statusValue.message, "ERROR 30052");
}

TestCase
CASE029
{
    Terminal
T1
T2;
T1: "drop function get_avg_x_Tablelock cascade";
T1: """create function get_avg_x_Tablelock() return(avg_lock INT) as
begin
	declare cnt int = 0;
	select avg(sal) into cnt from employee for update;
	return cnt;
end;
/""";

T1: "begin work";
T1: "select get_avg_x_Tablelock() from dual;";

T2: "begin work";
statusValue = T2:"select get_avg_x_Tablelock() from dual;";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"select * from employee for update";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

# x table lock release
T1: "commit";
statusValue = T2:"select * from employee for update;";
expect_no_substr(statusValue.message, "ERROR 30052");
}

TestCase
CASE030
{
    Terminal
T1
T2;

T1: "begin work";
T1: "select get_avg_x_Tablelock() from dual;";

T2: "begin work";
statusValue = T2:"select get_avg_x_Tablelock() from dual;";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"select * from employee for update";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

# x table lock release
T1: "rollback";
statusValue = T2:"select * from employee for update;";
expect_no_substr(statusValue.message, "ERROR 30052");
}


#########################################################################
##package
#########################################################################
#is lock
TestCase
CASE031
{
    Terminal
T1
T2;
:"""CREATE OR REPLACE PACKAGE BODY test_pack_islock AS //
FUNCTION get_avg_islock() RETURNS INT
BEGIN
 DECLARE cnt INT = 0;
 SELECT avg(sal)INTO cnt FROM employee
 WHERE JOB LIKE '%CLERK';

 RETURN cnt;
END;
END//;""";

:"""CREATE OR REPLACE PACKAGE BODY test_pack_xtablelock AS //
function get_avg_x_Tablelock() return int
begin
	declare cnt int = 0;
	select avg(sal)into cnt from employee for update;
	return cnt;
end;
end//;""";

:"""CREATE OR REPLACE PACKAGE BODY test_pack_ixlock AS //
function get_avg_ixlock() RETURNS int
begin
	declare cnt int = 0;
	update employee set ename ='ix_lock' where employeeno = '7788';
	select avg(sal)into cnt from employee where employeeno = '7788';
	return cnt;
end;
end//;""";

:"""CREATE OR REPLACE PACKAGE BODY test_pack_xrowlock AS //
function get_avg_xlock() RETURNS int
begin
	declare cnt int = 0;
	update employee set ename ='ix_lock' where employeeno = '7788';
	select avg(sal)into cnt from employee where employeeno = '7788';
	return cnt;
end;
end//;""";

:"""CREATE OR REPLACE PACKAGE BODY test_pack_ulock AS //
function get_avg_ulock() return  int
begin
	declare cnt int = 0;
	select avg(sal)into cnt from employee where employeeno = '7788' for update;
	return cnt;
end;
end//;""";


T1: "begin work";
T1: """BEGIN
  DBMS_OUTPUT.PUT_LINE('is_lock test:  '||test_pack_islock.get_avg_islock());
END;
/""";

T2: "begin work";
statusValue = T2:"""BEGIN
  DBMS_OUTPUT.PUT_LINE('table check confict  '|| test_pack_xtablelock.get_avg_x_Tablelock());
END;
/""";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"select * from employee for update";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

# x table lock release
T1: "commit";
statusValue = T2:"select * from employee for update ;";
expect_no_substr(statusValue.message, "ERROR 30052");
}

TestCase
CASE032
{
    Terminal
T1
T2;

T1: "begin work";
T1: """BEGIN
  DBMS_OUTPUT.PUT_LINE('is_lock test:  '||test_pack_islock.get_avg_islock());
END;
/""";

T2: "begin work";
statusValue = T2:"""BEGIN
  DBMS_OUTPUT.PUT_LINE('table check confict  '|| test_pack_xtablelock.get_avg_x_Tablelock());
END;
/""";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"select * from employee for update";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

# x table lock release
T1: "rollback";
statusValue = T2:"select * from employee for update ;";
expect_no_substr(statusValue.message, "ERROR 30052");
}

# ix lock
TestCase
CASE033
{
    Terminal
T1
T2;

T1: "begin work";
T1: """BEGIN
  DBMS_OUTPUT.PUT_LINE('ix_lock test '||test_pack_ixlock.get_avg_ixlock());
END;
/""";

T2: "begin work";
statusValue = T2:"""BEGIN
  DBMS_OUTPUT.PUT_LINE('table check confict  '|| test_pack_xtablelock.get_avg_x_Tablelock());
END;
/""";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"select * from employee for update";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

# x table lock release
T1: "commit";
statusValue = T2:"select * from employee for update;";
expect_no_substr(statusValue.message, "ERROR 30052");
}

TestCase
CASE034
{
    Terminal
T1
T2;

T1: "begin work";
T1: """BEGIN
  DBMS_OUTPUT.PUT_LINE('ix_lock test '||test_pack_ixlock.get_avg_ixlock());
END;
/""";

T2: "begin work";
statusValue = T2:"""BEGIN
  DBMS_OUTPUT.PUT_LINE('table check confict  '|| test_pack_xtablelock.get_avg_x_Tablelock());
END;
/""";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"select * from employee for update";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

# x table lock release
T1: "rollback";
statusValue = T2:"select * from employee for update;";
expect_no_substr(statusValue.message, "ERROR 30052");
}

TestCase
CASE035
{
    Terminal
T1
T2;

T1: "begin work";
T1: """BEGIN
  DBMS_OUTPUT.PUT_LINE('ix_lock test '||test_pack_xrowlock.get_avg_xlock());
END;
/""";

T2: "begin work";
statusValue = T2:"""BEGIN
  DBMS_OUTPUT.PUT_LINE('ix_lock test '||test_pack_xrowlock.get_avg_xlock());
END;
/""";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"update employee set ename ='ix_lock' where employeeno = '7788';";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

# x row lock release
T1: "commit";
statusValue = T2:"update employee set ename ='ix_lock' where employeeno = '7788';";
expect_no_substr(statusValue.message, "ERROR 30052");
}

TestCase
CASE036
{
    Terminal
T1
T2;

T1: "begin work";
T1: """BEGIN
  DBMS_OUTPUT.PUT_LINE('ix_lock test '||test_pack_xrowlock.get_avg_xlock());
END;
/""";

T2: "begin work";
statusValue = T2:"""BEGIN
  DBMS_OUTPUT.PUT_LINE('ix_lock test '||test_pack_xrowlock.get_avg_xlock());
END;
/""";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"update employee set ename ='ix_lock' where employeeno = '7788';";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

# x row lock release
T1: "rollback";
statusValue = T2:"update employee set ename ='ix_lock' where employeeno = '7788';";
expect_no_substr(statusValue.message, "ERROR 30052");
}

TestCase
CASE037
{
    Terminal
T1
T2;

T1: "begin work";
T1: """BEGIN
  DBMS_OUTPUT.PUT_LINE('u rowlock test '|| test_pack_ulock.get_avg_ulock());
END;
/""";

T2: "begin work";
statusValue = T2:"""BEGIN
  DBMS_OUTPUT.PUT_LINE('u rowlock test '|| test_pack_ulock.get_avg_ulock());
END;
/""";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"select sal from employee where employeeno = '7788' for update;";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

# u row lock release
T1: "commit";
statusValue = T2:"select sal from employee where employeeno = '7788' for update;";
expect_no_substr(statusValue.message, "ERROR 30052");
}

TestCase
CASE038
{
    Terminal
T1
T2;

T1: "begin work";
T1: """BEGIN
  DBMS_OUTPUT.PUT_LINE('u rowlock test '|| test_pack_ulock.get_avg_ulock());
END;
/""";

T2: "begin work";
statusValue = T2:"""BEGIN
  DBMS_OUTPUT.PUT_LINE('u rowlock test '|| test_pack_ulock.get_avg_ulock());
END;
/""";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"select sal from employee where employeeno = '7788' for update;";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

# u row lock release
T1: "rollback";
statusValue = T2:"select sal from employee where employeeno = '7788' for update;";
expect_no_substr(statusValue.message, "ERROR 30052");
}

TestCase
CASE039
{
    Terminal
T1
T2;

T1: "begin work";
T1: """BEGIN
  DBMS_OUTPUT.PUT_LINE('x_table_lock test '||test_pack_xtablelock.get_avg_x_Tablelock());
END;
/""";

T2: "begin work";
statusValue = T2:"""BEGIN
  DBMS_OUTPUT.PUT_LINE('x_table_lock test '||test_pack_xtablelock.get_avg_x_Tablelock());
END;
/""";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"select sal from employee for update";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

# x table lock release
T1: "commit";
statusValue = T2:"select sal from employee for update";
expect_no_substr(statusValue.message, "ERROR 30052");
}

TestCase
CASE040
{
    Terminal
T1
T2;

T1: "begin work";
T1: """BEGIN
  DBMS_OUTPUT.PUT_LINE('x_table_lock test '||test_pack_xtablelock.get_avg_x_Tablelock());
END;
/""";

T2: "begin work";
statusValue = T2:"""BEGIN
  DBMS_OUTPUT.PUT_LINE('x_table_lock test '||test_pack_xtablelock.get_avg_x_Tablelock());
END;
/""";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

statusValue = T2:"select sal from employee for update";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");

# x table lock release
T1: "rollback";
statusValue = T2:"select sal from employee for update";
expect_no_substr(statusValue.message, "ERROR 30052");
}

