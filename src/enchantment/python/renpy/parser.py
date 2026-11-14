"""renpy.parser. Script is parsed on the PC by the game's own Ren'Py, never
on the device; what's left is the trie user statements register their
parsers in (renpy.statements, run from the game's source), kept as Ren'Py
builds it so the registry matches."""
from renpy import missing_attribute


class ParseTrie(object):
    def __init__(self):
        self.default = None
        self.words = {}

    def add(self, name, function):
        if not name:
            self.default = function
            return
        first = name[0]
        if first not in self.words:
            self.words[first] = ParseTrie()
        self.words[first].add(name[1:], function)


# The root of the statement trie.
statements = ParseTrie()


def __getattr__(name):
    return missing_attribute("renpy.parser", name)
