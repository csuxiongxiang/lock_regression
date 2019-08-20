# import pdbc.trafodion.connector as connector
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
        ret += str(l) + '\n'
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
            logger.debug('\n%s\nequal\n%s' % (a, b))
        else:
            logger.error("\n%s\nnot equal\n%s" % (a, b))
            raise AssertionError("%s not equal %s" % (a, b))

    def clone(self):
        """sub class should implement this function"""
        pass


