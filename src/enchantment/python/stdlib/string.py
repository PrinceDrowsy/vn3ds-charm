"""string for MicroPython: the constants, capwords, and Formatter, which
Ren'Py's text substitution subclasses. Formatter follows CPython's
(Lib/string.py), with the field-name splitting CPython does in C written
out here."""

whitespace = ' \t\n\r\v\f'
ascii_lowercase = 'abcdefghijklmnopqrstuvwxyz'
ascii_uppercase = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
ascii_letters = ascii_lowercase + ascii_uppercase
digits = '0123456789'
hexdigits = digits + 'abcdef' + 'ABCDEF'
octdigits = '01234567'
punctuation = r"""!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~"""
printable = digits + ascii_letters + punctuation + whitespace
# Python 2's names for the same.
lowercase = ascii_lowercase
uppercase = ascii_uppercase
letters = ascii_letters


def capwords(s, sep=None):
    return (sep or ' ').join(x.capitalize() for x in s.split(sep))


def _field_name_split(field_name):
    """("a.b[0]") -> ("a", [(True, "b"), (False, 0)]), as CPython's
    _string.formatter_field_name_split."""
    i = 0
    while i < len(field_name) and field_name[i] not in ".[":
        i += 1
    first = field_name[:i]
    if first.isdigit():
        first = int(first)
    rest = []
    while i < len(field_name):
        if field_name[i] == ".":
            j = i + 1
            while j < len(field_name) and field_name[j] not in ".[":
                j += 1
            name = field_name[i + 1:j]
            if not name:
                raise ValueError("Empty attribute in format string")
            rest.append((True, name))
            i = j
        else:
            j = field_name.find("]", i)
            if j < 0:
                raise ValueError("Missing ']' in format string")
            key = field_name[i + 1:j]
            if not key:
                raise ValueError("Empty attribute in format string")
            rest.append((False, int(key) if key.isdigit() else key))
            i = j + 1
            if i < len(field_name) and field_name[i] not in ".[":
                raise ValueError("Only '.' or '[' may follow ']' in format field specifier")
    return first, rest


def _parse(format_string):
    """CPython's _string.formatter_parser: (literal, field name, format
    spec, conversion) for each {field}, with {{ and }} as literal braces."""
    literal = ""
    i = 0
    n = len(format_string)
    while i < n:
        c = format_string[i]
        if c == "{":
            if i + 1 < n and format_string[i + 1] == "{":
                # CPython yields the text so far, with one brace, at each
                # escaped brace.
                yield literal + "{", None, None, None
                literal = ""
                i += 2
                continue
            depth = 1
            j = i + 1
            while j < n and depth:
                if format_string[j] == "{":
                    depth += 1
                elif format_string[j] == "}":
                    depth -= 1
                j += 1
            if depth:
                raise ValueError("expected '}' before end of string")
            field = format_string[i + 1:j - 1]
            conversion = None
            spec = ""
            k = 0
            bracket = False
            while k < len(field):
                if field[k] == "[":
                    bracket = True
                elif field[k] == "]":
                    bracket = False
                elif not bracket and field[k] in "!:":
                    break
                k += 1
            name = field[:k]
            if k < len(field) and field[k] == "!":
                if k + 1 >= len(field):
                    raise ValueError("end of string while looking for conversion specifier")
                conversion = field[k + 1]
                k += 2
                if k < len(field) and field[k] != ":":
                    raise ValueError("expected ':' after conversion specifier")
            if k < len(field) and field[k] == ":":
                spec = field[k + 1:]
            yield literal, name, spec, conversion
            literal = ""
            i = j
        elif c == "}":
            if i + 1 < n and format_string[i + 1] == "}":
                yield literal + "}", None, None, None
                literal = ""
                i += 2
                continue
            raise ValueError("Single '}' encountered in format string")
        else:
            literal += c
            i += 1
    if literal:
        yield literal, None, None, None


class Formatter(object):
    def format(self, format_string, *args, **kwargs):
        return self.vformat(format_string, args, kwargs)

    def vformat(self, format_string, args, kwargs):
        used_args = set()
        result, _ = self._vformat(format_string, args, kwargs, used_args, 2)
        self.check_unused_args(used_args, args, kwargs)
        return result

    def _vformat(self, format_string, args, kwargs, used_args, recursion_depth, auto_arg_index=0):
        if recursion_depth < 0:
            raise ValueError('Max string recursion exceeded')
        result = []
        for literal_text, field_name, format_spec, conversion in self.parse(format_string):
            if literal_text:
                result.append(literal_text)
            if field_name is not None:
                if field_name == '':
                    if auto_arg_index is False:
                        raise ValueError('cannot switch from manual field specification to automatic field numbering')
                    field_name = str(auto_arg_index)
                    auto_arg_index += 1
                elif field_name.isdigit():
                    if auto_arg_index:
                        raise ValueError('cannot switch from manual field specification to automatic field numbering')
                    auto_arg_index = False
                obj, arg_used = self.get_field(field_name, args, kwargs)
                used_args.add(arg_used)
                obj = self.convert_field(obj, conversion)
                format_spec, auto_arg_index = self._vformat(format_spec, args, kwargs, used_args,
                                                            recursion_depth - 1, auto_arg_index=auto_arg_index)
                result.append(self.format_field(obj, format_spec))
        return ''.join(result), auto_arg_index

    def get_value(self, key, args, kwargs):
        if isinstance(key, int):
            return args[key]
        return kwargs[key]

    def check_unused_args(self, used_args, args, kwargs):
        pass

    def format_field(self, value, format_spec):
        return format(value, format_spec)

    def convert_field(self, value, conversion):
        if conversion is None:
            return value
        if conversion == 's':
            return str(value)
        if conversion == 'r':
            return repr(value)
        if conversion == 'a':
            return repr(value)
        raise ValueError("Unknown conversion specifier {0!s}".format(conversion))

    def parse(self, format_string):
        return _parse(format_string)

    def get_field(self, field_name, args, kwargs):
        first, rest = _field_name_split(field_name)
        obj = self.get_value(first, args, kwargs)
        for is_attr, i in rest:
            if is_attr:
                obj = getattr(obj, i)
            else:
                obj = obj[i]
        return obj, first
