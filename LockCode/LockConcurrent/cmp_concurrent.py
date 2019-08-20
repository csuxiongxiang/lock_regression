import ply.lex as lex
import ply.yacc as yacc
import logging
import sys

logging.basicConfig(level=logging.DEBUG, format="%(levelname)s::%(message)s")
logger = logging.getLogger('compiler')

reserved = {
    'CurrentDate': 'CURRENT_DATE',
    'CurrentTimeStamp': 'CURRENT_TIMESTAMP',
    'DynamicParam': 'DYNAMIC_PARAM',
    'Do': 'DO',
    'Each': 'EACH',
    'EmbedPython': 'EMBED_PYTHON',
    'ExpectEqual': 'EXPECT_EQUAL',
    'For': 'FOR',
    'Undo': 'UNDO',
    'FinalCheck': 'FINAL_CHECK',
    'In': 'IN',
    'Init': 'INIT',
    'Into': 'INTO',
    'DBConfig': 'DB_CONFIG',
    'PythonExp': 'PYTHON_EXP',
    'Range': 'RANGE',
    'RuntimeConfig': 'RUNTIME_CONFIG',
    'ResultSet': 'RESULT_SET',
    'RandomInt': 'RAND_INT',
    'RandomDouble': 'RAND_DOUBLE',
    'RandomString': 'RAND_STRING',
    'Sequence': 'SEQUENCE',
    'Set': 'SET',
    'SharedList': 'SHARED_LIST',
    'TestCase': 'TEST_CASE',
    'With': 'WITH'
}

tokens = [
    'STRING',
    'NUMBER',
    'LPAREN',
    'RPAREN',
    'LBRACKET',
    'RBRACKET',
    'LBRACE',
    'RBRACE',
    'COMMA',
    'COLON',
    'SEMICOLON',
    'EQUAL',
    'ID'
] + list(reserved.values())


t_NUMBER = r'\d[\.\d]*'
t_LPAREN = r'\('
t_RPAREN = r'\)'
t_LBRACKET = r'\['
t_RBRACKET = r'\]'
t_LBRACE = r'{'
t_RBRACE = r'}'
t_COMMA = r','
t_COLON = r':'
t_SEMICOLON = r';'
t_EQUAL = r'='

t_ignore = ' \t'
t_ignore_COMMENT = '\#.*'


def t_STRING(t):
    r'("""[^"""]*""")|(".*")'
    t.lexer.lineno += t.value.count('\n')
    return t


def t_ID(t):
    r"""[a-zA-Z_][a-zA-Z_0-9]*"""
    t.type = reserved.get(t.value, 'ID')  # Check for reserved words
    return t


def t_newline(t):
    r"""\n+"""
    t.lexer.lineno += len(t.value)


def t_error(t):
    logger.error("Illegal character '%s', lineno:%s" % (t.value[0], t.lexer.lineno))


lexer = lex.lex()


# parse and translate
class OffsetWriter:

    def __init__(self, file_name):
        self.file = open(file_name, mode='w')
        self.offset = 0

    def offset_back(self):
        self.offset -= 4

    def offset_ahead(self):
        self.offset += 4

    def write(self, s):
        self.file.write("%s%s" % (' ' * self.offset, s))

    def new_line(self):
        self.file.write("\n")

case_dynamic_var_dict = {}

output_file = OffsetWriter("Concurrent_unittest.py")

output_file.write('''# import pdbc.trafodion.connector as connector
import pyodbc as connector
import threading
import queue
import logging
import datetime
import random
import string
import copy

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(threadName)s] %(levelname)s::  %(message)s')
connector.pooling = False

class Logger:

    def __init__(self, name):
        self.logger = logging.getLogger(name)
        self.prefix = ''
        self.level = {'debug': logging.DEBUG,
                      'info': logging.INFO,
                      'warning': logging.WARNING,
                      'error': logging.ERROR}

    def set_prefix(self, pf):
        self.prefix = pf

    def debug(self, message):
        self.logger.debug("%s%s" % (self.prefix, message))

    def info(self, message):
        self.logger.info("%s%s" % (self.prefix, message))

    def warning(self, message):
        self.logger.warning("%s%s" % (self.prefix, message))

    def error(self, message):
        self.logger.error("%s%s" % (self.prefix, message))

    def set_level(self, level):
        if level in self.level:
            self.logger.setLevel(self.level[level])

logger = Logger('main_log')

case_list = []


def equal(a, b):
    special_type_list = [list, tuple]
    if type(a) in special_type_list or type(b) in special_type_list:
        if len(a) == len(b):
            for e_a, e_b in zip(a, b):
                if not equal(e_a, e_b):
                    return False
            return True
        else:
            return False
    if type(a) is str and type(b) is str:
        return a.rstrip() == b.rstrip()
    else:
        return a == b


def to_lines(sets):
    ret = ''
    for l in  sets:
        ret += str(l) + '\\n'
    return ret


def reset(v):
    if hasattr(v, 'reset'):
        v.reset()
    return v


def inner_count(v):
    if (type(v) is float or type(v) is int) and hasattr(v, 'count'):
        return v.count
    return 1


def get_next_value(v):
    if hasattr(v, 'get_next'):
        return v.get_next()
    return v


class RandomInt:

    def __init__(self, min, max, count):
        self.min = min
        self.max = max
        self.count = count

    def get_next(self):
        return random.randint(self.min, self.max)

    def reset(self):
        pass


class RandomDouble:

    def __init__(self, min, max, decimal, count):
        self.min = min
        self.max = max
        self.decimal = decimal
        self.count = count

    def get_next(self):
        return round(random.uniform(self.min, self.max), self.decimal)


    def reset(self):
        pass

class CurrentDate:

    def __init__(self, count):
        self.count = count

    def get_next(self):
        return datetime.datetime.today().strftime('%Y-%m-%d')

    def reset(self):
        pass


class CurrentTimeStamp:

    def __init__(self, count):
        self.count = count

    def get_next(self):
        return datetime.datetime.today().strftime('%Y-%m-%d %H:%M:%S.%f')

    def reset(self):
        pass


class RandomString:

    def __init__(self, len, count):
        self.len = len
        self.count = count

    def get_next(self):
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=self.len))

    def reset(self):
        pass

class Sequence:

    def __init__(self, start, count):
        self.start = start
        self.count = count
        self.current = start

    def get_next(self):
        ret = self.current
        self.current += 1
        return ret

    def reset(self):
        self.current = self.start

class Case:

    def run_init(self, cursor, action=None):
        """optional init"""
        pass

    def run_do_action(self, cursor, action=None):
        """iteration will go from here"""
        pass

    def run_undo_action(self, cursor, action=None):
        """undo action will go from here"""
        pass

    def run_final_check(self, cursor, action=None):
        """final check will be execute after all action and undo action executed"""
        pass

    @staticmethod
    def expect_equal(a, b):
        if equal(a, b):
            logger.debug('\\n%s\\nequal\\n%s' % (a, b))
        else:
            logger.error("\\n%s\\nnot equal\\n%s" % (a, b))
            raise AssertionError("%s not equal %s" % (a, b))

    def clone(self):
        """sub class should implement this function"""
        pass


''')


end_code_fragment = """

class Action:

    EXIT = 0
    EXECUTE_CASE = 1

    def __init__(self, type, round, iteration, run=None, name=None, depend_action=None):
        self.type = type
        self.run = run
        self.name = name
        self.round = round
        self.iteration = iteration
        self.prefix = '[Action:%s][iteration:%s]' % (name, iteration)
        self.depend_action = depend_action
        self.is_done = False


class RetryError(Exception):

    def __init__(self, s):
        super().__init__(self)
        self.str = s

    def __str__(self):
        return self.str


class Executor(threading.Thread):

    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.need_reconnect = True

    def run(self):
        logger.info('Executor start')
        try:
            while True:
                action = self.manager.get_next_action()
                if action.type == Action.EXIT:
                    logger.info('executor exit')
                    break
                elif action.type == Action.EXECUTE_CASE:
                    if action.depend_action is not None and not action.depend_action.is_done:
                        self.manager.put_action(action)
                        self.manager.notify_action_done()
                        continue
                    retry_times = 0
                    while retry_times < runtime_config['retry_times']:
                        try:
                            if self.need_reconnect:
                                self.reconnect()
                                self.need_reconnect = False

                            logger.debug("%s : run" % action.prefix)
                            action.run(self, action)
                            logger.info("%s success" % action.prefix)
                            action.is_done = True
                            self.manager.action_count(action)
                            break
                        except connector.Error as e:
                            logger.debug("%s : type:%s, %s" % (action.prefix, type(e), e))
                            if '08001' in str(e) or '08S01' in str(e) or 'HY000' in str(e) or 'S1T00' in str(e):
                                self.need_reconnect = True
                            elif '8616' not in str(e) and '8606' not in str(e) and '8604' not in str(e) and "30052" not in str(e) and "8839" not in str(e):
                                self.execute('rollback', prefix=action.prefix)

                            retry_times += 1
                            logger.info("%s failed, %s%s retry" % (action.prefix, retry_times, get_seq_suffix(retry_times)))
                            # time.sleep(0.01)
                    else:
                        manager.exception_queue.put(RetryError(self.name))
                else:
                    logging.error('unknown action type')
                    break

                self.manager.notify_action_done()
        except AssertionError as e:
            manager.exception_queue.put(e)
        logger.debug('Executor exit')

    def execute(self, sql, var_dict=None, prefix=''):
        if var_dict is not None:
            sql = sql % var_dict
        logger.debug('%s : execute "%s"\\n' % (prefix, sql))
        self.cursor.execute(sql)
        logger.debug('%s : success\\n' % prefix)

    def fetchall(self, prefix=''):
        logger.debug('%s : fetch result' % prefix)
        rs = self.cursor.fetchall()
        logger.debug('%s : success' % prefix)
        return rs

    def reconnect(self):
        logger.info("try to reconnect")
        self.connection = connector.connect(**db_config)
        self.connection.autocommit = True
        self.cursor = self.connection.cursor()
        logger.info("reconnect success")


class TaskManager:

    def __init__(self, cases):
        logger.debug('init case list')
        self.case_list = cases
        self.is_job_done = False
        self.action_queue = queue.Queue(10)
        self.exception_queue = queue.Queue(10)
        self.executor = []
        self.undo_actions = []
        self.action_counter = {}
        self.action_counter_lock = threading.Lock()

        for i in range(runtime_config['parallel']):
            self.executor.append(Executor(self))

    def run_init(self):
        logger.debug('run init')

        for executor in self.executor:
            executor.start()

        if not runtime_config['skip_init']:
            for case in self.case_list:
                self.action_queue.put(Action(Action.EXECUTE_CASE, 1, 1, case.run_init, "%s.run_init" % case.name))
            self.action_queue.join()

    def get_next_action(self):
        if self.is_job_done:
            return Action(Action.EXIT, 1, 1)
        else:
            return self.action_queue.get()

    def notify_action_done(self):
        self.action_queue.task_done()

    def run_actions(self, round):
        # loop iteration counts
        # random case from template list and execute do actions then put case undo queue
        # or pick case from undo list and execute undo actions
        logger.debug('run actions')
        self.undo_actions = []
        for i in range(runtime_config['iterations']):
            for idx_case, case in enumerate(self.case_list):
                do_action = Action(Action.EXECUTE_CASE, round, i + 1, case.run_do_action, "%s.do_action" % case.name)
                self.action_queue.put(do_action)
                self.undo_actions.append(Action(Action.EXECUTE_CASE, round, i + 1, case.run_undo_action,
                    "%s.undo_action" % case.name, do_action))
                self.case_list[idx_case] = case.clone()

        random.shuffle(self.undo_actions)

        for action in self.undo_actions:
            self.action_queue.put(action)

        self.action_queue.join()

    def run_final_check(self, round):
        for case in self.case_list:
            self.action_queue.put(Action(Action.EXECUTE_CASE, round, 1, case.run_final_check, '%s.final_check' % case.name))
        self.action_queue.join()

    def close(self):
        for i in range(len(self.executor)):
            self.action_queue.put(Action(Action.EXIT, 1, 1))

        for e in self.executor:
            e.join()

    def reset_action_counter(self):
        self.action_counter = {}

    def action_count(self, action):
        self.action_counter_lock.acquire()
        if action.name not in self.action_counter:
            self.action_counter[action.name] = 1
        else:
            self.action_counter[action.name] += 1
        self.action_counter_lock.release()

    def put_action(self, action):
        self.action_queue.put(action)


def get_seq_suffix(s):

    if s == 1:
        return 'st'
    elif s == 2:
        return 'nd'
    elif s == 3:
        return 'rd'
    else:
        return 'th'


if __name__ == "__main__":

    manager = TaskManager(case_list)

    for case in case_list:
        case.update_dynamic_var()

    manager.run_init()

    fatal_error = None
    try:
        fatal_error = manager.exception_queue.get_nowait()
        exit(-1)
    except queue.Empty:
        pass

    for r in range(runtime_config['rounds']):
        for case in case_list:
            case.update_dynamic_var()
        manager.reset_action_counter()
        logger.set_prefix('[%s%s round]: ' % (r+1, get_seq_suffix(r+1)))
        logger.info('\\n\\n======================\\n'
                     '%s%s round\\n'
                     '======================'
                     % (r + 1, get_seq_suffix(r + 1)))
        manager.run_actions(r + 1)
        try:
            fatal_error = manager.exception_queue.get_nowait()
            break
        except queue.Empty:
            pass

        for action, count in manager.action_counter.items():
            logger.info('%s success count: %s' % (action, count))

        manager.run_final_check(r + 1)

    while fatal_error is not None:
        print(fatal_error)
        try:
            fatal_error = manager.exception_queue.get_nowait()
        except queue.Empty:
            break

    manager.close()
"""


def unquote_str(s):
    if s.startswith('"""'):
        return s[3:len(s)-3]
    else:
        return s[1:len(s)-1]


def p_test_spec(p):
    r"""test_spec : config_spec case_spec"""
    output_file.write(end_code_fragment)


def p_config_spec(p):
    r"""config_spec : db_config_spec runtime_config_spec"""
    pass


def p_db_config_spec(p):
    r"""db_config_spec : DB_CONFIG LBRACE STRING RBRACE"""
    output_file.write('db_config = {')
    output_file.write(unquote_str(p[3]))
    output_file.write('}\n\n')


def p_runtime_config_spec(p):
    r"""runtime_config_spec : RUNTIME_CONFIG LBRACE STRING RBRACE"""
    output_file.write('runtime_config = {')
    output_file.write(unquote_str(p[3]))
    output_file.write('}\n\n')
    output_file.write('if "log_level" in runtime_config:\n')
    output_file.offset_ahead()
    output_file.write('logger.set_level(runtime_config["log_level"])\n')
    output_file.offset_back()


def p_case_spec(p):
    r"""case_spec : case_stmt
                  | case_spec case_stmt"""
    logger.debug('case spec done')


def p_case_stmt(p):
    r"""case_stmt : TEST_CASE case_name case_start case_body case_end"""
    output_file.write("case_list.append(%s())\n" % p[2])


def p_case_name(p):
    r"""case_name : ID"""
    output_file.write("\n\nclass %s(Case):\n" % p[1])
    output_file.new_line()
    output_file.offset_ahead()
    output_file.write('def __init__(self):\n')
    output_file.offset_ahead()
    output_file.write('self.name = \"%s\"\n' % p[1])
    output_file.write('self.dict_var = {}\n')
    output_file.write('self.dict_dynamic_generator = {}\n')
    output_file.write('self.init_dynamic_dict()\n')
    output_file.write('self.shared_vars = {}\n')
    output_file.offset_back()
    output_file.new_line()
    p[0] = p[1]


def p_case_start(p):
    r"""case_start : LBRACE"""
    global case_dynamic_var_dict
    case_dynamic_var_dict = {}


def p_case_end(p):
    r"""case_end : RBRACE"""

    output_file.write('def init_dynamic_dict(self):\n')
    output_file.offset_ahead()
    if len(case_dynamic_var_dict) > 0:
        for k, v in case_dynamic_var_dict.items():
            output_file.write('self.dict_dynamic_generator["%s"] = %s\n' % (k, v))
    else:
        output_file.write('pass\n')
    output_file.offset_back()
    output_file.new_line()
    output_file.write("""def update_dynamic_var(self):
        for k, v in self.dict_dynamic_generator.items():
            self.dict_var[k] = v.get_next()

    """)
    output_file.offset_back()
    output_file.write("""def clone(self):
        ret = copy.deepcopy(self)
        ret.shared_var = {}
        ret.dict_var = {}
        ret.update_dynamic_var()
        return ret
    """)

    output_file.new_line()


def p_case_body(p):
    r"""case_body : dynamic_param_stmt init_stmt do_stmt undo_stmt final_check_stmt
                  | init_stmt do_stmt undo_stmt final_check_stmt"""
    logger.debug('case body done')


def p_dynamic_param_stmt(p):
    r"""dynamic_param_stmt : DYNAMIC_PARAM d_start dynamic_var_declarations d_end"""
    pass


def p_d_start(p):
    r"""d_start : LBRACE"""
    pass


def p_d_end(p):
    r"""d_end : RBRACE"""
    pass


def p_var_declarations(p):
    r"""dynamic_var_declarations : dynamic_var_declarations dynamic_var_declaration
                                 | dynamic_var_declaration"""
    pass


def p_var_declaration(p):
    r"""dynamic_var_declaration : ID EQUAL rule"""
    case_dynamic_var_dict[p[1]] = p[3]


def p_rule(p):
    r"""rule : random_int
             | random_double
             | current_date
             | current_timestamp
             | random_string
             | sequence"""
    p[0] = p[1]


def p_random_int(p):
    r"""random_int : RAND_INT LPAREN NUMBER COMMA NUMBER COMMA NUMBER RPAREN"""
    p[0] = "RandomInt(%s, %s, %s)" % (p[3], p[5], p[7])


def p_random_double(p):
    r"""random_double : RAND_DOUBLE LPAREN NUMBER COMMA NUMBER COMMA NUMBER COMMA NUMBER RPAREN"""
    p[0] = "RandomDouble(%s, %s, %s, %s)" % (p[3], p[5], p[7], p[9])


def p_current_date(p):
    r"""current_date : CURRENT_DATE LPAREN NUMBER RPAREN"""
    p[0] = "CurrentDate(p[3])"


def p_current_timestamp(p):
    r"""current_timestamp : CURRENT_TIMESTAMP LPAREN NUMBER RPAREN"""
    p[0] = "CurrentTimeStamp(%s)" % p[3]


def p_random_string(p):
    r"""random_string : RAND_STRING LPAREN NUMBER COMMA NUMBER RPAREN"""
    p[0] = "RandomString(%s, %s)" % (p[3], p[5])


def p_sequence(p):
    r"""sequence : SEQUENCE LPAREN NUMBER COMMA NUMBER RPAREN"""
    p[0] = "Sequence(%s, %s)" % (p[3], p[5])


def p_python_expr(p):
    r"""python_expr : PYTHON_EXP LPAREN STRING RPAREN"""
    p[0] = unquote_str(p[3])


def p_shared_var(p):
    r"""shared_var : SHARED_LIST"""
    p[0] = p[1]


def p_init_stmt(p):
    r"""init_stmt : INIT init_start init_body init_end"""
    logger.debug('init stmt done')


def p_init_start(p):
    r"""init_start : LBRACE"""
    output_file.write("def run_init(self, cursor, action=None):\n")
    output_file.offset_ahead()


def p_init_end(p):
    r"""init_end : RBRACE"""
    output_file.new_line()
    output_file.offset_back()


def p_init_body(p):
    r"""init_body : executable_stmts"""
    pass


def p_do_stmt(p):
    r"""do_stmt : DO do_start do_body do_end"""
    logger.debug('do stmt done')


def p_do_start(p):
    r"""do_start : LBRACE"""
    output_file.write("def run_do_action(self, cursor, action):\n")
    output_file.offset_ahead()


def p_do_end(p):
    r"""do_end : RBRACE"""
    output_file.new_line()
    output_file.offset_back()


def p_do_body(p):
    r"""do_body : executable_stmts"""
    pass


def p_undo_stmt(p):
    r"""undo_stmt : UNDO undo_start undo_body undo_end"""
    logger.debug('undo stmt done')


def p_undo_start(p):
    r"""undo_start : LBRACE"""
    output_file.write("def run_undo_action(self, cursor, action=None):\n")
    output_file.offset_ahead()


def p_undo_end(p):
    r"""undo_end : RBRACE"""
    output_file.new_line()
    output_file.offset_back()


def p_undo_body(p):
    r"""undo_body : executable_stmts"""
    pass


def p_final_check_stmt(p):
    r"""final_check_stmt : FINAL_CHECK final_check_start final_body final_check_end"""
    logger.debug('final check stmt')


def p_final_check_start(p):
    r"""final_check_start : LBRACE"""
    output_file.write("def run_final_check(self, cursor, action=None):\n")
    output_file.offset_ahead()


def p_final_body(p):
    r"""final_body : executable_stmts"""
    pass


def p_final_check_end(p):
    r"""final_check_end : RBRACE"""
    output_file.offset_back()
    output_file.new_line()


def p_executable_stmts(p):
    r"""executable_stmts : executable_stmt
                         | executable_stmts executable_stmt"""
    pass


def p_executable_stmt(p):
    r"""executable_stmt : expression SEMICOLON
                        | assignment SEMICOLON
                        | assertion SEMICOLON
                        | for_stmt
                        | for_each_stmt
                        | embed_python_stmt SEMICOLON"""
    pass


def p_assertion(p):
    r"""assertion : EXPECT_EQUAL LPAREN expression COMMA expression RPAREN"""
    output_file.write("self.expect_equal(%s, %s)\n" % (p[3], p[5]))


def p_assignment(p):
    r"""assignment : ID EQUAL expression
                   | ID EQUAL shared_var"""
    if p[3] == 'SharedList':
        output_file.write("%s = []\n" % p[1])
        output_file.write("self.shared_vars['%s'] = %s\n" % (p[1], p[1]))
    else:
        output_file.write("%s = %s\n" % (p[1], p[3]))


def p_expression(p):
    r"""expression : query_stmt
                   | result_set_query_stmt
                   | query_into_stmt
                   | query_with_stmt
                   | query_with_into_stmt
                   | var_name
                   | set
                   | rule
                   | python_expr
                   | NUMBER"""
    p[0] = p[1]


def p_set(p):
    r"""set : SET LPAREN STRING RPAREN"""
    p[0] = unquote_str(p[3])


def p_query_stmt(p):
    r"""query_stmt : COLON STRING"""
    output_file.write("cursor.execute(%s, self.dict_var, action.prefix)\n" % p[2])


def p_result_set_query_stmt(p):
    r"""result_set_query_stmt : COLON RESULT_SET LPAREN STRING RPAREN"""
    output_file.write("cursor.execute(%s, self.dict_var, action.prefix)\n" % p[4])
    output_file.write("temp_rs = cursor.fetchall(action.prefix)\n")
    p[0] = "temp_rs"


def p_query_into_stmt(p):
    r"""query_into_stmt : COLON STRING INTO var_list"""
    output_file.write("cursor.execute(%s, self.dict_var, action.prefix)\n" % p[2])
    output_file.write("temp_rs = cursor.fetchall(action.prefix)\n")
    for i, var in enumerate(p[4]):
        output_file.write("%s = [row[%s] for row in temp_rs]\n" % (var, i))
        output_file.write("logger.debug(\"%%s : %s = [\\n%%s]\" %% (action.prefix, to_lines(%s)))\n" % (var, var))


def p_var_name(p):
    r"""var_name : ID
                 | ID LBRACKET NUMBER RBRACKET
                 | ID LBRACKET ID RBRACKET"""
    if len(p) > 2:
        p[0] = p[1] + p[2] + p[3] + p[4]
    else:
        p[0] = p[1]

def p_var_list(p):
    r"""var_list : var_name
                 | var_list COMMA var_name"""
    if len(p) > 2:
        p[0] = p[1] + [p[3]]
    else:
        p[0] = [p[1]]


def p_query_with_stmt(p):
    r"""query_with_stmt : COLON STRING WITH var_list"""
    li = ""
    idx = 0
    for id in p[4]:
        output_file.write("reset(%s)\n" % id)
        output_file.write("max_count = inner_count(%s)\n" % id)
        output_file.write("for inner_i_%s in range(max_count):\n" % idx)
        output_file.offset_ahead()
        output_file.write("inner_v_%s = get_next_value(%s)\n" % (idx, id))
        li += "inner_v_%s, " % idx
        idx += 1

    output_file.write("cursor.execute(%s.format(%s), self.dict_var, action.prefix)\n" % (p[2], li))

    for id in p[4]:
        output_file.offset_back()


def p_query_with_into(p):
    r"""query_with_into_stmt : COLON STRING WITH var_list INTO var_list"""
    li = ""
    idx = 0
    for id in p[4]:
        output_file.write("reset(%s)\n" % id)
        output_file.write("max_count = inner_count(%s)\n" % id)
        output_file.write("for inner_i_%s in range(max_count):\n" % idx)
        output_file.offset_ahead()
        output_file.write("inner_v_%s = get_next_value(%s)\n" % (idx, id))
        li += "inner_v_%s, " % idx
        idx += 1

    output_file.write("cursor.execute(%s.format(%s), self.dict_var, action.prefix)\n" % (p[2], li))

    for id in p[4]:
        output_file.offset_back()

    output_file.write("temp_rs = cursor.fetchall()\n")
    for i, var in enumerate(p[6]):
        output_file.write("%s = [row[%s] for row in temp_rs]\n" % (var, i))
        output_file.write("logger.debug(\"%s = [\\n%%s]\" %% to_lines(%s))\n" % (var, var))


def p_for_stmt(p):
    r"""for_stmt : for_start1 executable_stmts for_end
                 | for_start2 executable_stmts for_end"""
    pass


def p_for_start1(p):
    r"""for_start1 : FOR ID IN RANGE LPAREN NUMBER COMMA NUMBER RPAREN  LBRACE"""
    output_file.write("for %s in range(%s, %s):\n" % (p[2], p[6], p[8]))
    output_file.offset_ahead()


def p_for_start2(p):
    r"""for_start2 : FOR ID IN RANGE LPAREN ID RPAREN  LBRACE"""
    output_file.write("for %s in range(get_next_value(%s)):\n" % (p[2], p[6]))
    output_file.offset_ahead()


def p_for_end(p):
    r"""for_end : RBRACE"""
    output_file.offset_back()


def p_for_each_stmt(p):
    r"""for_each_stmt : for_each_start executable_stmts for_each_end"""
    pass


def p_for_each_start(p):
    r"""for_each_start : FOR EACH var_list LBRACE"""
    ilist = ""
    ziplist = ""
    for i in range(len(p[3])):
        if i > 0:
            ilist += ', '
            ziplist += ', '
        ilist += 'e_' + p[3][i]
        ziplist += p[3][i]
    output_file.write("for %s in zip(%s):\n" % (ilist, ziplist))
    output_file.offset_ahead()


def p_for_each_end(p):
    r"""for_each_end : RBRACE"""
    output_file.offset_back()


def p_embed_python_stmt(p):
    r"""embed_python_stmt : EMBED_PYTHON LPAREN STRING RPAREN"""
    output_file.write("%s\n" % unquote_str(p[3]))


parser = yacc.yacc()


if __name__ == "__main__":

    if len(sys.argv) < 2:
        print("usage: %s test_case_file" % sys.argv[0])
        exit(-1)
    with open(sys.argv[1]) as f:
        data = f.read()
        parser.parse(data)

