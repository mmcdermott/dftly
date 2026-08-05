"""The compiled Lark grammar, shared by everything that needs to read dftly's string form.

Kept apart from :mod:`dftly.str_form.parser` so that both the transformer and the f-string field
splitter can use one compiled grammar without importing each other -- the transformer depends on the
node classes, and the nodes depend on the splitter.
"""

from importlib.resources import files

from lark import Lark

GRAMMAR_TEXT = files(__package__).joinpath("grammar.lark").read_text()
GRAMMAR = Lark(GRAMMAR_TEXT, parser="lalr")
