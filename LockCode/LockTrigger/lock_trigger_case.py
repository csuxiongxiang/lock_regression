Config
{
    """
    'host': '10.10.23.23',
    'port': 23400,
    'tenant_name': 'ESGYNDB',
    'schema': 'LOCK_TRIGGER',
    'user': 'trafodion',
    'password': 'traf123',
    'charset': 'utf-8',
    'use_unicode': True,
    'get_warnings': True,
    'connection_timeout' : 6000
    """
}


TestCase CASE000{
: "drop schema lock_trigger cascade;";
:"create schema lock_trigger;";
:"set schema lock_trigger;";

:"drop table TE_RULE_HISTORY cascade";
:"""create table TE_RULE_HISTORY 
( 
  OPERTLR      varchar(10) CHARACTER SET UTF8, 
  OPERTIME     varchar(20) CHARACTER SET UTF8, 
  OPERDESC     varchar(128) CHARACTER SET UTF8, 
  UPTABLE      varchar(30) CHARACTER SET UTF8, 
  UPDATA       varchar(1024) CHARACTER SET UTF8 
);""";

:"""drop table TE_AU_MODE cascade""";
:""" create table TE_AU_MODE
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
primary key (MODEID);""";

:""" INSERT INTO TE_AU_MODE (MODEID,AUTHTYPE,AUTHLEVEL,AUTHLEVELD,AUTHBRNOTYPE,AUTHBRNO,AUTHPOST,URGENTFLAG,AUTHDESC,HXAUTHFLAG,HXAUTHTYPE,REMARK,REMARK1,JZAUTHBNK,JZAUTHLVL) VALUES (
 'AU00001', '4', NULL, NULL, NULL, NULL, NULL, NULL, '累计取现金额达到100万', NULL, NULL, NULL, NULL, NULL, NULL);""";
:""" INSERT INTO TE_AU_MODE (MODEID,AUTHTYPE,AUTHLEVEL,AUTHLEVELD,AUTHBRNOTYPE,AUTHBRNO,AUTHPOST,URGENTFLAG,AUTHDESC,HXAUTHFLAG,HXAUTHTYPE,REMARK,REMARK1,JZAUTHBNK,JZAUTHLVL) VALUES (
'AU00002', '4', NULL, NULL, NULL, NULL, NULL, NULL, '累计转账金额达到100万', NULL, NULL, NULL, NULL, NULL, NULL);""";
:""" INSERT INTO TE_AU_MODE(MODEID,AUTHTYPE,AUTHLEVEL,AUTHLEVELD,AUTHBRNOTYPE,AUTHBRNO,AUTHPOST,URGENTFLAG,AUTHDESC,HXAUTHFLAG,HXAUTHTYPE,REMARK,REMARK1,JZAUTHBNK,JZAUTHLVL) VALUES (
  'AU00003', '1', '1', NULL, NULL, NULL, 'GW006', NULL, '此交易必须授权', NULL, NULL, NULL, NULL, NULL, NULL);""";
:""" INSERT INTO TE_AU_MODE(MODEID,AUTHTYPE,AUTHLEVEL,AUTHLEVELD,AUTHBRNOTYPE,AUTHBRNO,AUTHPOST,URGENTFLAG,AUTHDESC,HXAUTHFLAG,HXAUTHTYPE,REMARK,REMARK1,JZAUTHBNK,JZAUTHLVL) VALUES (
  'AU00004', '2', '1', NULL, NULL, NULL, 'GW006', NULL, '此交易必须授权', NULL, NULL, NULL, NULL, NULL, NULL);""";
:""" INSERT INTO TE_AU_MODE(MODEID,AUTHTYPE,AUTHLEVEL,AUTHLEVELD,AUTHBRNOTYPE,AUTHBRNO,AUTHPOST,URGENTFLAG,AUTHDESC,HXAUTHFLAG,HXAUTHTYPE,REMARK,REMARK1,JZAUTHBNK,JZAUTHLVL) VALUES (
  'AU00005', '3', '1', NULL, NULL, NULL, 'GW006', NULL, '此交易必须授权', NULL, NULL, NULL, NULL, NULL, NULL);""";
:""" INSERT INTO TE_AU_MODE(MODEID,AUTHTYPE,AUTHLEVEL,AUTHLEVELD,AUTHBRNOTYPE,AUTHBRNO,AUTHPOST,URGENTFLAG,AUTHDESC,HXAUTHFLAG,HXAUTHTYPE,REMARK,REMARK1,JZAUTHBNK,JZAUTHLVL) VALUES (
  'AU00006', '4', NULL, NULL, NULL, NULL, NULL, NULL, '此交易必须授权', NULL, NULL, NULL, NULL, NULL, NULL);""";
:""" INSERT INTO TE_AU_MODE(MODEID,AUTHTYPE,AUTHLEVEL,AUTHLEVELD,AUTHBRNOTYPE,AUTHBRNO,AUTHPOST,URGENTFLAG,AUTHDESC,HXAUTHFLAG,HXAUTHTYPE,REMARK,REMARK1,JZAUTHBNK,JZAUTHLVL) VALUES (
  'AU00007', '5', NULL, NULL, NULL, NULL, NULL, NULL, '此交易必须授权', NULL, NULL, NULL, NULL, NULL, NULL);""";
:""" INSERT INTO TE_AU_MODE(MODEID,AUTHTYPE,AUTHLEVEL,AUTHLEVELD,AUTHBRNOTYPE,AUTHBRNO,AUTHPOST,URGENTFLAG,AUTHDESC,HXAUTHFLAG,HXAUTHTYPE,REMARK,REMARK1,JZAUTHBNK,JZAUTHLVL) VALUES (
  'AU00012', '1', '1', NULL, NULL, NULL, 'GW006', NULL, '个人存款账户开户金额大于等于RMB50000元', NULL, NULL, '该账户有未追回的利息', NULL, NULL, NULL);""";

}



TestCase CASE001
{
    Terminal T1 T2;
:"""CREATE OR REPLACE TRIGGER TE_AU_MODE_TRIG after INSERT
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
/""";
T1:"delete from TE_RULE_HISTORY";
T1: "begin work";

# x
T1: "update TE_AU_MODE set AUTHTYPE = '1' where MODEID = 'AU00001';";

T2: "begin work";
statusValue = T2:"""select * from TE_RULE_HISTORY for update""";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");
expect_no_substr(statusValue.message,"LockTimeOutException");
T2: "commit";

# lock release
T1: "commit";
statusValue = T2:"select * from TE_RULE_HISTORY for update";
expect_no_substr(statusValue.message, "ERROR 30052");
}


TestCase CASE002
{
    Terminal T1 T2;
T1:"delete from TE_RULE_HISTORY";
T1: "begin work";
# x -lock
T1: "select * from TE_RULE_HISTORY for update";

T2: "begin work";
statusValue = T2:"""update TE_AU_MODE set AUTHTYPE = '1' where MODEID = 'AU00001'""";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");
expect_no_substr(statusValue.message,"LockTimeOutException");

T2: "commit";

# lock release
T1: "commit";
statusValue = T2:"update TE_AU_MODE set AUTHTYPE = '1' where MODEID = 'AU00001'";
expect_no_substr(statusValue.message, "ERROR 30052");
}


TestCase CASE003
{
    Terminal T1 T2;
T1:"delete from TE_RULE_HISTORY";
T1: "begin work";

T1: "delete from TE_AU_MODE where MODEID = 'AU00001';";

T2: "begin work";
statusValue = T2:"""select * from TE_RULE_HISTORY for update""";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");
expect_no_substr(statusValue.message,"LockTimeOutException");
T2: "commit";

# lock release
T1: "rollback";
statusValue = T2:"select * from TE_RULE_HISTORY for update";
expect_no_substr(statusValue.message, "ERROR 30052");
}


TestCase CASE004
{
    Terminal T1 T2;
T1:"delete from TE_RULE_HISTORY";

T1: "begin work";
# x -lock
T1: "select * from TE_RULE_HISTORY for update";

T2: "begin work";
statusValue = T2:"""delete from TE_AU_MODE where MODEID = 'AU00001'""";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");
expect_no_substr(statusValue.message,"LockTimeOutException");

T2: "commit";

# lock release
T1: "commit";
T2:"begin work";
statusValue = T2:"delete from TE_AU_MODE where MODEID = 'AU00001'";
expect_no_substr(statusValue.message, "ERROR 30052");
T2:"rollback";
}


TestCase CASE005
{
    Terminal T1 T2;
T1:"delete from TE_AU_MODE where MODEID = 'AU00161'";

T1:"delete from TE_RULE_HISTORY";
T1: "begin work";
T1: """INSERT INTO TE_AU_MODE (MODEID,AUTHTYPE,AUTHLEVEL,AUTHLEVELD,AUTHBRNOTYPE,AUTHBRNO,AUTHPOST,URGENTFLAG,AUTHDESC,HXAUTHFLAG,HXAUTHTYPE,REMARK,REMARK1,JZAUTHBNK,JZAUTHLVL) VALUES (
'AU00161','1','1',NULL,NULL,NULL,'GW006',NULL,'本转他：付款账户类型为个人且交易金额大于等于5万',NULL,NULL,NULL,NULL,NULL,NULL);""";

T2: "begin work";
statusValue = T2:"""select * from TE_RULE_HISTORY for update""";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");
expect_no_substr(statusValue.message,"LockTimeOutException");
T2: "commit";

# lock release
T1: "rollback";
statusValue = T2:"select * from TE_RULE_HISTORY for update";
expect_no_substr(statusValue.message, "ERROR 30052");
}


TestCase CASE006
{
    Terminal T1 T2;
T1:"delete from TE_AU_MODE where MODEID = 'AU00161'";
T1:"delete from TE_RULE_HISTORY";
T1: "begin work";

# x -lock
T1: "select * from TE_RULE_HISTORY for update";

T2: "begin work";
statusValue = T2:"""INSERT INTO TE_AU_MODE (MODEID,AUTHTYPE,AUTHLEVEL,AUTHLEVELD,AUTHBRNOTYPE,AUTHBRNO,AUTHPOST,URGENTFLAG,AUTHDESC,HXAUTHFLAG,HXAUTHTYPE,REMARK,REMARK1,JZAUTHBNK,JZAUTHLVL) VALUES (
'AU00161','1','1',NULL,NULL,NULL,'GW006',NULL,'本转他：付款账户类型为个人且交易金额大于等于5万',NULL,NULL,NULL,NULL,NULL,NULL);""";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");
expect_no_substr(statusValue.message,"LockTimeOutException");

T2: "commit";

# lock release
T1: "commit";

T1:"delete from TE_RULE_HISTORY";
T1: "begin work";
statusValue = T2:"""INSERT INTO TE_AU_MODE (MODEID,AUTHTYPE,AUTHLEVEL,AUTHLEVELD,AUTHBRNOTYPE,AUTHBRNO,AUTHPOST,URGENTFLAG,AUTHDESC,HXAUTHFLAG,HXAUTHTYPE,REMARK,REMARK1,JZAUTHBNK,JZAUTHLVL) VALUES (
'AU00161','1','1',NULL,NULL,NULL,'GW006',NULL,'本转他：付款账户类型为个人且交易金额大于等于5万',NULL,NULL,NULL,NULL,NULL,NULL);""";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "rollback";
}


TestCase CASE007
{
    Terminal T1 T2;
statusValue =:"""CREATE OR REPLACE TRIGGER TE_AU_MODE_TRIG before INSERT
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
/""";
expect_substr(statusValue.code, 0);

T1:"delete from TE_RULE_HISTORY";
T1: "begin work";

# add lock
T1: "update TE_AU_MODE set AUTHTYPE = '1' where MODEID = 'AU00001';";

T2: "begin work";
statusValue = T2:"""select * from TE_RULE_HISTORY for update""";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");
expect_no_substr(statusValue.message,"LockTimeOutException");
T2: "commit";

# lock release
T1: "commit";
statusValue = T2:"select * from TE_RULE_HISTORY for update";
expect_no_substr(statusValue.message, "ERROR 30052");
}


TestCase CASE008
{
    Terminal T1 T2;
T1:"delete from TE_RULE_HISTORY";
T1: "begin work";

# x -lock
T1: "select * from TE_RULE_HISTORY for update";

T2: "begin work";
statusValue = T2:"""update TE_AU_MODE set AUTHTYPE = '1' where MODEID = 'AU00001'""";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");
expect_no_substr(statusValue.message,"LockTimeOutException");


T2: "commit";

# lock release
T1: "commit";
statusValue = T2:"update TE_AU_MODE set AUTHTYPE = '1' where MODEID = 'AU00001'";
expect_no_substr(statusValue.message, "ERROR 30052");
}


TestCase CASE009
{
    Terminal T1 T2;
T1:"delete from TE_RULE_HISTORY";
T1: "begin work";

T1: "delete from TE_AU_MODE where MODEID = 'AU00001';";

T2: "begin work";
statusValue = T2:"""select * from TE_RULE_HISTORY for update""";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");
expect_no_substr(statusValue.message,"LockTimeOutException");
T2: "commit";

# lock release
T1: "rollback";
statusValue = T2:"select * from TE_RULE_HISTORY for update";
expect_no_substr(statusValue.message, "ERROR 30052");
}


TestCase CASE010
{
    Terminal T1 T2;
T1:"delete from TE_RULE_HISTORY";
T1: "begin work";

# x -lock
T1: "select * from TE_RULE_HISTORY for update";

T2: "begin work";
statusValue = T2:"""delete from TE_AU_MODE where MODEID = 'AU00001'""";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");
expect_no_substr(statusValue.message,"LockTimeOutException");

T2: "commit";

# lock release
T1: "commit";
T2:"begin work";
statusValue = T2:"delete from TE_AU_MODE where MODEID = 'AU00001'";
expect_no_substr(statusValue.message, "ERROR 30052");
T2:"rollback";
}


TestCase CASE011
{
    Terminal T1 T2;
T1:"delete from TE_AU_MODE where MODEID = 'AU00161'";
T1:"delete from TE_RULE_HISTORY";
T1: "begin work";

T1: """INSERT INTO TE_AU_MODE (MODEID,AUTHTYPE,AUTHLEVEL,AUTHLEVELD,AUTHBRNOTYPE,AUTHBRNO,AUTHPOST,URGENTFLAG,AUTHDESC,HXAUTHFLAG,HXAUTHTYPE,REMARK,REMARK1,JZAUTHBNK,JZAUTHLVL) VALUES (
'AU00161','1','1',NULL,NULL,NULL,'GW006',NULL,'本转他：付款账户类型为个人且交易金额大于等于5万',NULL,NULL,NULL,NULL,NULL,NULL);""";

T2: "begin work";
statusValue = T2:"""select * from TE_RULE_HISTORY for update""";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");
expect_no_substr(statusValue.message,"LockTimeOutException");
T2: "commit";

# lock release
T1: "rollback";
statusValue = T2:"select * from TE_RULE_HISTORY for update";
expect_no_substr(statusValue.message, "ERROR 30052");
}


TestCase CASE012
{
    Terminal T1 T2;
T1:"delete from TE_AU_MODE where MODEID = 'AU00161'";
T1:"delete from TE_RULE_HISTORY";

T1: "begin work";
# x -lock
T1: "select * from TE_RULE_HISTORY for update";

T2: "begin work";
statusValue = T2:"""INSERT INTO TE_AU_MODE (MODEID,AUTHTYPE,AUTHLEVEL,AUTHLEVELD,AUTHBRNOTYPE,AUTHBRNO,AUTHPOST,URGENTFLAG,AUTHDESC,HXAUTHFLAG,HXAUTHTYPE,REMARK,REMARK1,JZAUTHBNK,JZAUTHLVL) VALUES (
'AU00161','1','1',NULL,NULL,NULL,'GW006',NULL,'本转他：付款账户类型为个人且交易金额大于等于5万',NULL,NULL,NULL,NULL,NULL,NULL);""";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");
expect_no_substr(statusValue.message,"LockTimeOutException");

T2: "commit";

# lock release
T1: "commit";
statusValue = T2:"""INSERT INTO TE_AU_MODE (MODEID,AUTHTYPE,AUTHLEVEL,AUTHLEVELD,AUTHBRNOTYPE,AUTHBRNO,AUTHPOST,URGENTFLAG,AUTHDESC,HXAUTHFLAG,HXAUTHTYPE,REMARK,REMARK1,JZAUTHBNK,JZAUTHLVL) VALUES (
'AU00161','1','1',NULL,NULL,NULL,'GW006',NULL,'本转他：付款账户类型为个人且交易金额大于等于5万',NULL,NULL,NULL,NULL,NULL,NULL);""";
expect_no_substr(statusValue.message, "ERROR 30052");

}


TestCase CASE013
{
    Terminal T1 T2;
    :"""CREATE OR REPLACE TRIGGER TE_AU_MODE_TRIG after INSERT
  OR UPDATE OR DELETE ON TRAFODION.LOCK_TRIGGER.TE_AU_MODE FOR EACH STATEMENT AS
    begin
    INSERT INTO TE_RULE_HISTORY VALUES  ('lock', to_char(SYSDATE,'YYYYMMDDHH24MISS') ,'语句级trigger','TE_AU MODE','AU00161,1,1,,,,GW006,,,,,,,,');
end;
/""";


T1:"delete from TE_RULE_HISTORY";
T1: "begin work";

# x
T1: "update TE_AU_MODE set AUTHTYPE = '1' where MODEID = 'AU00001';";

T2: "begin work";
statusValue = T2:"""select * from TE_RULE_HISTORY for update""";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");
expect_no_substr(statusValue.message,"LockTimeOutException");
T2: "commit";

# lock release
T1: "commit";
statusValue = T2:"select * from TE_RULE_HISTORY for update";
expect_no_substr(statusValue.message, "ERROR 30052");
}


TestCase CASE014
{
    Terminal T1 T2;
T1:"delete from TE_RULE_HISTORY";
T1: "begin work";
# x -lock
T1: "select * from TE_RULE_HISTORY for update";

T2: "begin work";
statusValue = T2:"""update TE_AU_MODE set AUTHTYPE = '1' where MODEID = 'AU00001'""";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");
expect_no_substr(statusValue.message,"LockTimeOutException");

T2: "commit";

# lock release
T1: "commit";
statusValue = T2:"update TE_AU_MODE set AUTHTYPE = '1' where MODEID = 'AU00001'";
expect_no_substr(statusValue.message, "ERROR 30052");
}


TestCase CASE015
{
    Terminal T1 T2;
T1:"delete from TE_RULE_HISTORY";
T1: "begin work";

T1: "delete from TE_AU_MODE where MODEID = 'AU00001';";

T2: "begin work";
statusValue = T2:"""select * from TE_RULE_HISTORY for update""";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");
expect_no_substr(statusValue.message,"LockTimeOutException");
T2: "commit";

# lock release
T1: "rollback";
statusValue = T2:"select * from TE_RULE_HISTORY for update";
expect_no_substr(statusValue.message, "ERROR 30052");
}


TestCase CASE016
{
    Terminal T1 T2;
T1:"delete from TE_RULE_HISTORY";
T1: "begin work";

# x -lock
T1: "select * from TE_RULE_HISTORY for update";

T2: "begin work";
statusValue = T2:"""delete from TE_AU_MODE where MODEID = 'AU00001'""";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");
expect_no_substr(statusValue.message,"LockTimeOutException");

T2: "commit";

# lock release
T1: "commit";

T2:"begin work";
statusValue = T2:"delete from TE_AU_MODE where MODEID = 'AU00001'";
expect_no_substr(statusValue.message, "ERROR 30052");
T2:"rollback";

}


TestCase CASE017
{
    Terminal T1 T2;
T1:"delete from TE_AU_MODE where MODEID = 'AU00161'";

T1:"delete from TE_RULE_HISTORY";
T1: "begin work";
T1: """INSERT INTO TE_AU_MODE (MODEID,AUTHTYPE,AUTHLEVEL,AUTHLEVELD,AUTHBRNOTYPE,AUTHBRNO,AUTHPOST,URGENTFLAG,AUTHDESC,HXAUTHFLAG,HXAUTHTYPE,REMARK,REMARK1,JZAUTHBNK,JZAUTHLVL) VALUES (
'AU00161','1','1',NULL,NULL,NULL,'GW006',NULL,'本转他：付款账户类型为个人且交易金额大于等于5万',NULL,NULL,NULL,NULL,NULL,NULL);""";

T2: "begin work";
statusValue = T2:"""select * from TE_RULE_HISTORY for update""";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");
expect_no_substr(statusValue.message,"LockTimeOutException");
T2: "commit";

# lock release
T1: "rollback";
statusValue = T2:"select * from TE_RULE_HISTORY for update";
expect_no_substr(statusValue.message, "ERROR 30052");
}


TestCase CASE018
{
    Terminal T1 T2;
T1:"delete from TE_AU_MODE where MODEID = 'AU00161'";
T1:"delete from TE_RULE_HISTORY";
T1: "begin work";

# x -lock
T1: "select * from TE_RULE_HISTORY for update";

T2: "begin work";
statusValue = T2:"""INSERT INTO TE_AU_MODE (MODEID,AUTHTYPE,AUTHLEVEL,AUTHLEVELD,AUTHBRNOTYPE,AUTHBRNO,AUTHPOST,URGENTFLAG,AUTHDESC,HXAUTHFLAG,HXAUTHTYPE,REMARK,REMARK1,JZAUTHBNK,JZAUTHLVL) VALUES (
'AU00161','1','1',NULL,NULL,NULL,'GW006',NULL,'本转他：付款账户类型为个人且交易金额大于等于5万',NULL,NULL,NULL,NULL,NULL,NULL);""";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");
expect_no_substr(statusValue.message,"LockTimeOutException");

T2: "commit";

# lock release
T1: "commit";

T1:"delete from TE_RULE_HISTORY";
T1: "begin work";
statusValue = T2:"""INSERT INTO TE_AU_MODE (MODEID,AUTHTYPE,AUTHLEVEL,AUTHLEVELD,AUTHBRNOTYPE,AUTHBRNO,AUTHPOST,URGENTFLAG,AUTHDESC,HXAUTHFLAG,HXAUTHTYPE,REMARK,REMARK1,JZAUTHBNK,JZAUTHLVL) VALUES (
'AU00161','1','1',NULL,NULL,NULL,'GW006',NULL,'本转他：付款账户类型为个人且交易金额大于等于5万',NULL,NULL,NULL,NULL,NULL,NULL);""";
expect_no_substr(statusValue.message, "ERROR 30052");
T1: "rollback";
}


TestCase CASE019
{
    Terminal T1 T2;
statusValue =:"""CREATE OR REPLACE TRIGGER TE_AU_MODE_TRIG before INSERT
  OR UPDATE OR DELETE ON TRAFODION.LOCK_TRIGGER.TE_AU_MODE FOR EACH STATEMENT AS
    begin
    INSERT INTO TE_RULE_HISTORY VALUES  ('lock', to_char(SYSDATE,'YYYYMMDDHH24MISS') ,'语句级trigger','TE_AU MODE','AU00161,1,1,,,,GW006,,,,,,,,');
end;
/""";
expect_substr(statusValue.code, 0);

T1:"delete from TE_RULE_HISTORY";
T1: "begin work";

# add lock
T1: "update TE_AU_MODE set AUTHTYPE = '1' where MODEID = 'AU00001';";

T2: "begin work";
statusValue = T2:"""select * from TE_RULE_HISTORY for update""";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");
expect_no_substr(statusValue.message,"LockTimeOutException");
T2: "commit";

# lock release
T1: "commit";
statusValue = T2:"select * from TE_RULE_HISTORY for update";
expect_no_substr(statusValue.message, "ERROR 30052");
}


TestCase CASE020
{
    Terminal T1 T2;
T1:"delete from TE_RULE_HISTORY";
T1: "begin work";

# x -lock
T1: "select * from TE_RULE_HISTORY for update";

T2: "begin work";
statusValue = T2:"""update TE_AU_MODE set AUTHTYPE = '1' where MODEID = 'AU00001'""";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");
expect_no_substr(statusValue.message,"LockTimeOutException");

T2: "commit";

# lock release
T1: "commit";
statusValue = T2:"update TE_AU_MODE set AUTHTYPE = '1' where MODEID = 'AU00001'";
expect_no_substr(statusValue.message, "ERROR 30052");
}


TestCase CASE021
{
    Terminal T1 T2;
T1:"delete from TE_RULE_HISTORY";
T1: "begin work";

T1: "delete from TE_AU_MODE where MODEID = 'AU00001';";

T2: "begin work";
statusValue = T2:"""select * from TE_RULE_HISTORY for update""";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");
expect_no_substr(statusValue.message,"LockTimeOutException");
T2: "commit";

# lock release
T1: "rollback";
statusValue = T2:"select * from TE_RULE_HISTORY for update";
expect_no_substr(statusValue.message, "ERROR 30052");
}


TestCase CASE022
{
    Terminal T1 T2;
T1:"delete from TE_RULE_HISTORY";
T1: "begin work";

# x -lock
T1: "select * from TE_RULE_HISTORY for update";

T2: "begin work";
statusValue = T2:"""delete from TE_AU_MODE where MODEID = 'AU00001'""";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");
expect_no_substr(statusValue.message,"LockTimeOutException");

T2: "commit";

# lock release
T1: "commit";
T2:"begin work";
statusValue = T2:"delete from TE_AU_MODE where MODEID = 'AU00001'";
expect_no_substr(statusValue.message, "ERROR 30052");
T2:"rollback";
}


TestCase CASE023
{
    Terminal T1 T2;
T1:"delete from TE_AU_MODE where MODEID = 'AU00161'";
T1:"delete from TE_RULE_HISTORY";
T1: "begin work";

T1: """INSERT INTO TE_AU_MODE (MODEID,AUTHTYPE,AUTHLEVEL,AUTHLEVELD,AUTHBRNOTYPE,AUTHBRNO,AUTHPOST,URGENTFLAG,AUTHDESC,HXAUTHFLAG,HXAUTHTYPE,REMARK,REMARK1,JZAUTHBNK,JZAUTHLVL) VALUES (
'AU00161','1','1',NULL,NULL,NULL,'GW006',NULL,'本转他：付款账户类型为个人且交易金额大于等于5万',NULL,NULL,NULL,NULL,NULL,NULL);""";

T2: "begin work";
statusValue = T2:"""select * from TE_RULE_HISTORY for update""";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");
expect_no_substr(statusValue.message,"LockTimeOutException");
T2: "commit";

# lock release
T1: "rollback";
statusValue = T2:"select * from TE_RULE_HISTORY for update";
expect_no_substr(statusValue.message, "ERROR 30052");
}


TestCase CASE024
{
    Terminal T1 T2;
T1:"delete from TE_AU_MODE where MODEID = 'AU00161'";
T1:"delete from TE_RULE_HISTORY";
T1: "begin work";

# x -lock
T1: "select * from TE_RULE_HISTORY for update";

T2: "begin work";
statusValue = T2:"""INSERT INTO TE_AU_MODE (MODEID,AUTHTYPE,AUTHLEVEL,AUTHLEVELD,AUTHBRNOTYPE,AUTHBRNO,AUTHPOST,URGENTFLAG,AUTHDESC,HXAUTHFLAG,HXAUTHTYPE,REMARK,REMARK1,JZAUTHBNK,JZAUTHLVL) VALUES (
'AU00161','1','1',NULL,NULL,NULL,'GW006',NULL,'本转他：付款账户类型为个人且交易金额大于等于5万',NULL,NULL,NULL,NULL,NULL,NULL);""";
expect_substr(statusValue.message, "ERROR[30052] ROW LEVEL LOCK TIMEOUT ERROR");
expect_no_substr(statusValue.message,"LockTimeOutException");

T2: "commit";

# lock release
T1: "commit";
statusValue = T2:"""INSERT INTO TE_AU_MODE (MODEID,AUTHTYPE,AUTHLEVEL,AUTHLEVELD,AUTHBRNOTYPE,AUTHBRNO,AUTHPOST,URGENTFLAG,AUTHDESC,HXAUTHFLAG,HXAUTHTYPE,REMARK,REMARK1,JZAUTHBNK,JZAUTHLVL) VALUES (
'AU00161','1','1',NULL,NULL,NULL,'GW006',NULL,'本转他：付款账户类型为个人且交易金额大于等于5万',NULL,NULL,NULL,NULL,NULL,NULL);""";
expect_no_substr(statusValue.message, "ERROR 30052");

}