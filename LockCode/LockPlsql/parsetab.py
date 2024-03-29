
# parsetab.py
# This file is automatically generated. Do not edit.
# pylint: disable=W,C,R
_tabversion = '3.10'

_lr_method = 'LALR'

_lr_signature = 'Async Colon Comma Config ELSE EqualSign ExpectEqual ExpectIn ExpectNoSubStr ExpectNotEqual ExpectNotIn ExpectStrEqual ExpectStrNotEqual ExpectSubStr ID IF LBrace LParenthesis NormalString Number Point RBrace RParenthesis RawString ResultSet Semicolon Shell THEN Terminal TestCase Tuple WHILESpec : Configuration CasesConfiguration : Config LBrace String RBraceCases : Cases CaseCases : CaseCase : TestCase CaseName CaseStart Statements CaseEndCaseName : IDCaseStart : LBraceStatements : Statements StatementStatements : StatementStatement : StatementBody SemicolonStatementBody : ScopedStatementScopedStatement : Colon ScopedStatementBodyScopedStatementBody : QueryQuery : StringString : NormalStringString : RawStringScopedStatementBody : ResultSetQueryResultSetQuery : ResultSet LParenthesis Query RParenthesisScopedStatement : Async Colon ScopedStatementBodyScopedStatement : Term Colon ScopedStatementBodyTerm : IDScopedStatement : Async Term Colon ScopedStatementBodyStatementBody : DeclarationDeclaration : Terminal TermListTermList : TermList TermTermList : TermStatementBody : AssignmentAssignment : Variable EqualSign ExpressionVariable : IDVariable : Variable Point IDExpression : StringExpression : NumberExpression : ScopedStatementExpression : VariableExpression : TupleExpressionTupleExpression : Tuple LParenthesis String RParenthesisStatementBody : AssertionAssertion : ExpectEqual LParenthesis Expression Comma Expression RParenthesisAssertion : ExpectNotEqual LParenthesis Expression Comma Expression RParenthesisAssertion : ExpectStrEqual LParenthesis Expression Comma Expression RParenthesisAssertion : ExpectStrNotEqual LParenthesis Expression Comma Expression RParenthesisAssertion : ExpectSubStr LParenthesis Expression Comma Expression RParenthesisAssertion : ExpectNoSubStr LParenthesis Expression Comma Expression RParenthesisAssertion : ExpectIn LParenthesis Expression Comma Expression RParenthesisAssertion : ExpectNotIn LParenthesis Expression Comma Expression RParenthesisStatementBody : Shell LParenthesis String RParenthesisCaseEnd : RBrace'
    
_lr_action_items = {'Config':([0,],[3,]),'$end':([1,4,5,8,39,41,],[0,-1,-4,-3,-5,-47,]),'TestCase':([2,4,5,8,16,39,41,],[6,6,-4,-3,-2,-5,-47,]),'LBrace':([3,9,10,],[7,15,-6,]),'ID':([6,14,15,17,18,26,28,40,42,51,53,54,55,56,57,58,59,60,61,62,63,64,70,92,93,94,95,96,97,98,99,],[10,38,-7,38,-9,51,51,-8,-10,-21,51,-26,77,79,77,77,77,77,77,77,77,77,-25,77,77,77,77,77,77,77,77,]),'NormalString':([7,25,43,49,52,55,57,58,59,60,61,62,63,64,66,68,91,92,93,94,95,96,97,98,99,],[12,12,12,12,12,12,12,12,12,12,12,12,12,12,12,12,12,12,12,12,12,12,12,12,12,]),'RawString':([7,25,43,49,52,55,57,58,59,60,61,62,63,64,66,68,91,92,93,94,95,96,97,98,99,],[13,13,13,13,13,13,13,13,13,13,13,13,13,13,13,13,13,13,13,13,13,13,13,13,13,]),'RBrace':([11,12,13,17,18,40,42,],[16,-15,-16,41,-9,-8,-10,]),'Semicolon':([12,13,19,20,21,22,23,44,45,46,47,51,53,54,67,69,70,71,72,73,74,75,76,77,79,88,90,100,110,111,112,113,114,115,116,117,118,],[-15,-16,42,-11,-23,-27,-37,-12,-13,-17,-14,-21,-24,-26,-19,-20,-25,-34,-28,-31,-32,-33,-35,-29,-30,-46,-22,-18,-36,-38,-39,-40,-41,-42,-43,-44,-45,]),'Comma':([12,13,44,45,46,47,67,69,71,73,74,75,76,77,79,80,81,82,83,84,85,86,87,90,100,110,],[-15,-16,-12,-13,-17,-14,-19,-20,-34,-31,-32,-33,-35,-29,-30,92,93,94,95,96,97,98,99,-22,-18,-36,]),'RParenthesis':([12,13,44,45,46,47,65,67,69,71,73,74,75,76,77,79,89,90,100,101,102,103,104,105,106,107,108,109,110,],[-15,-16,-12,-13,-17,-14,88,-19,-20,-34,-31,-32,-33,-35,-29,-30,100,-22,-18,110,111,112,113,114,115,116,117,118,-36,]),'Shell':([14,15,17,18,40,42,],[24,-7,24,-9,-8,-10,]),'Colon':([14,15,17,18,26,27,38,40,42,50,51,55,57,58,59,60,61,62,63,64,77,92,93,94,95,96,97,98,99,],[25,-7,25,-9,49,52,-21,-8,-10,68,-21,25,25,25,25,25,25,25,25,25,-21,25,25,25,25,25,25,25,25,]),'Async':([14,15,17,18,40,42,55,57,58,59,60,61,62,63,64,92,93,94,95,96,97,98,99,],[26,-7,26,-9,-8,-10,26,26,26,26,26,26,26,26,26,26,26,26,26,26,26,26,26,]),'Terminal':([14,15,17,18,40,42,],[28,-7,28,-9,-8,-10,]),'ExpectEqual':([14,15,17,18,40,42,],[30,-7,30,-9,-8,-10,]),'ExpectNotEqual':([14,15,17,18,40,42,],[31,-7,31,-9,-8,-10,]),'ExpectStrEqual':([14,15,17,18,40,42,],[32,-7,32,-9,-8,-10,]),'ExpectStrNotEqual':([14,15,17,18,40,42,],[33,-7,33,-9,-8,-10,]),'ExpectSubStr':([14,15,17,18,40,42,],[34,-7,34,-9,-8,-10,]),'ExpectNoSubStr':([14,15,17,18,40,42,],[35,-7,35,-9,-8,-10,]),'ExpectIn':([14,15,17,18,40,42,],[36,-7,36,-9,-8,-10,]),'ExpectNotIn':([14,15,17,18,40,42,],[37,-7,37,-9,-8,-10,]),'LParenthesis':([24,30,31,32,33,34,35,36,37,48,78,],[43,57,58,59,60,61,62,63,64,66,91,]),'ResultSet':([25,49,52,68,],[48,48,48,48,]),'EqualSign':([29,38,79,],[55,-29,-30,]),'Point':([29,38,71,77,79,],[56,-29,56,-29,-30,]),'Number':([55,57,58,59,60,61,62,63,64,92,93,94,95,96,97,98,99,],[74,74,74,74,74,74,74,74,74,74,74,74,74,74,74,74,74,]),'Tuple':([55,57,58,59,60,61,62,63,64,92,93,94,95,96,97,98,99,],[78,78,78,78,78,78,78,78,78,78,78,78,78,78,78,78,78,]),}

_lr_action = {}
for _k, _v in _lr_action_items.items():
   for _x,_y in zip(_v[0],_v[1]):
      if not _x in _lr_action:  _lr_action[_x] = {}
      _lr_action[_x][_k] = _y
del _lr_action_items

_lr_goto_items = {'Spec':([0,],[1,]),'Configuration':([0,],[2,]),'Cases':([2,],[4,]),'Case':([2,4,],[5,8,]),'CaseName':([6,],[9,]),'String':([7,25,43,49,52,55,57,58,59,60,61,62,63,64,66,68,91,92,93,94,95,96,97,98,99,],[11,47,65,47,47,73,73,73,73,73,73,73,73,73,47,47,101,73,73,73,73,73,73,73,73,]),'CaseStart':([9,],[14,]),'Statements':([14,],[17,]),'Statement':([14,17,],[18,40,]),'StatementBody':([14,17,],[19,19,]),'ScopedStatement':([14,17,55,57,58,59,60,61,62,63,64,92,93,94,95,96,97,98,99,],[20,20,75,75,75,75,75,75,75,75,75,75,75,75,75,75,75,75,75,]),'Declaration':([14,17,],[21,21,]),'Assignment':([14,17,],[22,22,]),'Assertion':([14,17,],[23,23,]),'Term':([14,17,26,28,53,55,57,58,59,60,61,62,63,64,92,93,94,95,96,97,98,99,],[27,27,50,54,70,27,27,27,27,27,27,27,27,27,27,27,27,27,27,27,27,27,]),'Variable':([14,17,55,57,58,59,60,61,62,63,64,92,93,94,95,96,97,98,99,],[29,29,71,71,71,71,71,71,71,71,71,71,71,71,71,71,71,71,71,]),'CaseEnd':([17,],[39,]),'ScopedStatementBody':([25,49,52,68,],[44,67,69,90,]),'Query':([25,49,52,66,68,],[45,45,45,89,45,]),'ResultSetQuery':([25,49,52,68,],[46,46,46,46,]),'TermList':([28,],[53,]),'Expression':([55,57,58,59,60,61,62,63,64,92,93,94,95,96,97,98,99,],[72,80,81,82,83,84,85,86,87,102,103,104,105,106,107,108,109,]),'TupleExpression':([55,57,58,59,60,61,62,63,64,92,93,94,95,96,97,98,99,],[76,76,76,76,76,76,76,76,76,76,76,76,76,76,76,76,76,]),}

_lr_goto = {}
for _k, _v in _lr_goto_items.items():
   for _x, _y in zip(_v[0], _v[1]):
       if not _x in _lr_goto: _lr_goto[_x] = {}
       _lr_goto[_x][_k] = _y
del _lr_goto_items
_lr_productions = [
  ("S' -> Spec","S'",1,None,None,None),
  ('Spec -> Configuration Cases','Spec',2,'p_spec','cmp_plsql.py',131),
  ('Configuration -> Config LBrace String RBrace','Configuration',4,'p_configuration','cmp_plsql.py',144),
  ('Cases -> Cases Case','Cases',2,'p_cases_cases','cmp_plsql.py',331),
  ('Cases -> Case','Cases',1,'p_cases_case','cmp_plsql.py',336),
  ('Case -> TestCase CaseName CaseStart Statements CaseEnd','Case',5,'p_case','cmp_plsql.py',341),
  ('CaseName -> ID','CaseName',1,'p_case_name','cmp_plsql.py',346),
  ('CaseStart -> LBrace','CaseStart',1,'p_case_start','cmp_plsql.py',354),
  ('Statements -> Statements Statement','Statements',2,'p_statements_statements','cmp_plsql.py',369),
  ('Statements -> Statement','Statements',1,'p_statements_statement','cmp_plsql.py',374),
  ('Statement -> StatementBody Semicolon','Statement',2,'p_statement','cmp_plsql.py',379),
  ('StatementBody -> ScopedStatement','StatementBody',1,'p_statement_body_query','cmp_plsql.py',384),
  ('ScopedStatement -> Colon ScopedStatementBody','ScopedStatement',2,'p_scoped_statement_no_term','cmp_plsql.py',389),
  ('ScopedStatementBody -> Query','ScopedStatementBody',1,'p_scoped_statement_body_query','cmp_plsql.py',399),
  ('Query -> String','Query',1,'p_query','cmp_plsql.py',405),
  ('String -> NormalString','String',1,'p_string_normal','cmp_plsql.py',410),
  ('String -> RawString','String',1,'p_string_raw','cmp_plsql.py',415),
  ('ScopedStatementBody -> ResultSetQuery','ScopedStatementBody',1,'p_scoped_statement_result_set_query','cmp_plsql.py',420),
  ('ResultSetQuery -> ResultSet LParenthesis Query RParenthesis','ResultSetQuery',4,'p_result_set_query','cmp_plsql.py',425),
  ('ScopedStatement -> Async Colon ScopedStatementBody','ScopedStatement',3,'p_scoped_statement_no_term_async','cmp_plsql.py',431),
  ('ScopedStatement -> Term Colon ScopedStatementBody','ScopedStatement',3,'p_scoped_statement_with_term','cmp_plsql.py',440),
  ('Term -> ID','Term',1,'p_term','cmp_plsql.py',452),
  ('ScopedStatement -> Async Term Colon ScopedStatementBody','ScopedStatement',4,'p_scoped_statement_with_term_async','cmp_plsql.py',457),
  ('StatementBody -> Declaration','StatementBody',1,'p_statement_body_declaration','cmp_plsql.py',466),
  ('Declaration -> Terminal TermList','Declaration',2,'p_declaration','cmp_plsql.py',471),
  ('TermList -> TermList Term','TermList',2,'p_term_list_list','cmp_plsql.py',479),
  ('TermList -> Term','TermList',1,'p_term_list_term','cmp_plsql.py',484),
  ('StatementBody -> Assignment','StatementBody',1,'p_statement_body_assignment','cmp_plsql.py',489),
  ('Assignment -> Variable EqualSign Expression','Assignment',3,'p_assignment_expression','cmp_plsql.py',494),
  ('Variable -> ID','Variable',1,'p_variable_id','cmp_plsql.py',500),
  ('Variable -> Variable Point ID','Variable',3,'p_variable_member','cmp_plsql.py',505),
  ('Expression -> String','Expression',1,'p_expression_string','cmp_plsql.py',510),
  ('Expression -> Number','Expression',1,'p_expression_number','cmp_plsql.py',515),
  ('Expression -> ScopedStatement','Expression',1,'p_expression_scoped_statement','cmp_plsql.py',520),
  ('Expression -> Variable','Expression',1,'p_expression_variable','cmp_plsql.py',533),
  ('Expression -> TupleExpression','Expression',1,'p_expression_tuple','cmp_plsql.py',538),
  ('TupleExpression -> Tuple LParenthesis String RParenthesis','TupleExpression',4,'p_expression_tuple_constructor','cmp_plsql.py',543),
  ('StatementBody -> Assertion','StatementBody',1,'p_statement_body_assertion','cmp_plsql.py',551),
  ('Assertion -> ExpectEqual LParenthesis Expression Comma Expression RParenthesis','Assertion',6,'p_assertion_expect_equal','cmp_plsql.py',556),
  ('Assertion -> ExpectNotEqual LParenthesis Expression Comma Expression RParenthesis','Assertion',6,'p_assertion_expect_not_equal','cmp_plsql.py',563),
  ('Assertion -> ExpectStrEqual LParenthesis Expression Comma Expression RParenthesis','Assertion',6,'p_assertion_expect_str_equal','cmp_plsql.py',570),
  ('Assertion -> ExpectStrNotEqual LParenthesis Expression Comma Expression RParenthesis','Assertion',6,'p_assertion_expect_str_not_equal','cmp_plsql.py',577),
  ('Assertion -> ExpectSubStr LParenthesis Expression Comma Expression RParenthesis','Assertion',6,'p_assertion_expect_sub_str','cmp_plsql.py',584),
  ('Assertion -> ExpectNoSubStr LParenthesis Expression Comma Expression RParenthesis','Assertion',6,'p_assertion_expect_no_sub_str','cmp_plsql.py',591),
  ('Assertion -> ExpectIn LParenthesis Expression Comma Expression RParenthesis','Assertion',6,'p_assertion_expect_in','cmp_plsql.py',598),
  ('Assertion -> ExpectNotIn LParenthesis Expression Comma Expression RParenthesis','Assertion',6,'p_assertion_expect_not_in','cmp_plsql.py',605),
  ('StatementBody -> Shell LParenthesis String RParenthesis','StatementBody',4,'p_statement_body_shell','cmp_plsql.py',612),
  ('CaseEnd -> RBrace','CaseEnd',1,'p_case_end','cmp_plsql.py',617),
]
