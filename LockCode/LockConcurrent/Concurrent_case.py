DBConfig { """
'DSN': '23d35',
'PWD': 'traf123',
'UID': 'trafodion'
"""
}

RuntimeConfig { """
'parallel': 20,
'rounds': 1,
'iterations': 50,
'retry_times': 200000,
'log_level': 'debug',
'skip_init': False
"""
}

TestCase BasicCase1 {
  DynamicParam {
    var2 = RandomInt(10, 20, 1)
  }
  Init {
    :"drop table if exists account";
    :"create table account(id int primary key, name char(20), balance int)";
    :"insert into account values(1, 'A', 100)";
    :"insert into account values(2, 'B', 100)";
  }
  Do {
    :"begin work";
    :"update account set balance = balance + %(var2)s where id = 1";
    :"update account set balance = balance - %(var2)s where id = 2";
    :"commit";
  }
  Undo {
    :"begin work";
    :"update account set balance = balance - %(var2)s where id = 1";
    :"update account set balance = balance + %(var2)s where id = 2";
    :"commit";
  }
  FinalCheck {
    rs = :ResultSet("select * from account");
    ExpectEqual(rs, Set("""[(1, 'A', 100), (2, 'B', 100)]"""));
  }
}


# TestCase BasicCase2 {
#   DynamicParam {
#     var2 = RandomInt(10, 20, 1)
#   }
#   Init {
#     :"drop table if exists account";
#     :"create table account(id int primary key, name char(20), balance int)";
#     :"insert into account values(1, 'A', 100)";
#     :"insert into account values(2, 'B', 100)";
#   }
#   Do {
#     :"begin work";
#     :"select * from account where id=1 for update";
#     :"update account set balance = balance + %(var2)s where id = 1";
#     :"update account set balance = balance - %(var2)s where id = 2";
#     :"commit";
#   }
#   Undo {
#     :"begin work";
#     :"select * from account where id=1 for update";
#     :"update account set balance = balance - %(var2)s where id = 1";
#     :"update account set balance = balance + %(var2)s where id = 2";
#     :"commit";
#   }
#   FinalCheck {
#     rs = :ResultSet("select * from account");
#     ExpectEqual(rs, Set("""[(1, 'A', 100), (2, 'B', 100)]"""));
#   }
# }
#
# TestCase BasicCase3 {
#   DynamicParam {
#     var2 = RandomInt(10, 20, 1)
#   }
#   Init {
#     :"drop table if exists account";
#     :"create table account(id int primary key, name char(20), balance int)";
#     :"insert into account values(1, 'A', 100)";
#     :"insert into account values(2, 'B', 100)";
#   }
#   Do {
#     :"begin work";
#     :"select * from account for update";
#     :"update account set balance = balance + %(var2)s where id = 1";
#     :"update account set balance = balance - %(var2)s where id = 2";
#     :"commit";
#   }
#   Undo {
#     :"begin work";
#     :"select * from account for update";
#     :"update account set balance = balance - %(var2)s where id = 1";
#     :"update account set balance = balance + %(var2)s where id = 2";
#     :"commit";
#   }
#   FinalCheck {
#     rs = :ResultSet("select * from account");
#     ExpectEqual(rs, Set("""[(1, 'A', 100), (2, 'B', 100)]"""));
#   }
# }