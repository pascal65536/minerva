import string
import pprint
import ast
import subprocess
import json
import re
import sys

password = 'qwertyuiopasdfghjklzxcvbnm'

class Checker:
    def __init__(self, filepath):
        self.filepath = filepath
        self.cmd = []
        self.errors = []

    def run(self):
        if not self.cmd:
            return {}
        result = subprocess.run(self.cmd, capture_output=True, text=True)
        return self.parse(result.stdout)

    def _parse_(self, result):
        return json.loads(result)

    def __line__(self, lines_dct):
        return lines_dct
    
word_set_1 = set(input())
word_set_2 = set(input())
word_set_3 = set(input())
print(*sorted(word_set_1 & word_set_2 & word_set_3))


def col(a, b):
    """Тест"""
    def Tripple(c):
        return c * 3

    l = a + b
    return Tripple(l)


q = "1"
w = "2"
E = col(q, w)

eval('6 * 8')
