-------------------------------------------------------------
--is test:
--begin t1
begin work;
call test_is_lock();

begin work;
call test_x_table_lock();

--commit t1
commit;

begin work;
call test_x_table_lock();
commit;

-------------------------------------------------------------
--Ix lock
--begin t1
begin work;
call test_Ix_lock();

begin work;
call test_x_table_lock();

--t1 commit
commit;

begin work;
call test_x_table_lock();
commit;

--------------------------------------------------------------
--x table lock
--begin t1
begin work;
call test_x_table_lock();

begin work;
call test_x_table_lock();

--commit t1
commit

begin work;
call test_x_table_lock();
commit

---------------------------------------------------------------
--x row lock
--begin t1
begin work;
call test_x_row_lock();

begin work;
call test_x_row_lock();

--commit t1
commit

begin work;
call test_x_row_lock();
commit;

---------------------------------------------------------------
--u lock
--begin t1
begin work;
call test_u_lock();

begin work;
call test_u_lock();

--commit t1
commit;

begin work;
call test_u_lock();
commit;



























