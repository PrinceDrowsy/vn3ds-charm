"""fnmatch for MicroPython: shell-style matching (*, ?, [seq], [!seq]),
case-sensitive as on POSIX, without compiling a regular expression."""


def fnmatch(name, pat):
    return fnmatchcase(name, pat)


def filter(names, pat):
    return [n for n in names if fnmatchcase(n, pat)]


def fnmatchcase(name, pat):
    return _match(name, 0, pat, 0)


def _match(name, i, pat, j):
    while j < len(pat):
        c = pat[j]
        if c == "*":
            while j < len(pat) and pat[j] == "*":
                j += 1
            if j == len(pat):
                return True
            for k in range(i, len(name) + 1):
                if _match(name, k, pat, j):
                    return True
            return False
        if i >= len(name):
            return False
        if c == "?":
            i += 1
            j += 1
        elif c == "[":
            # As CPython's translate: a ] right after [ or [! is a member,
            # and an unclosed [ is a literal.
            k = j + 1
            if k < len(pat) and pat[k] == "!":
                k += 1
            if k < len(pat) and pat[k] == "]":
                k += 1
            while k < len(pat) and pat[k] != "]":
                k += 1
            if k >= len(pat):
                if name[i] != "[":
                    return False
                i += 1
                j += 1
                continue
            body = pat[j + 1:k]
            negate = body[:1] == "!"
            if negate:
                body = body[1:]
            hit = False
            m = 0
            while m < len(body):
                if m + 2 < len(body) and body[m + 1] == "-":
                    hit = hit or body[m] <= name[i] <= body[m + 2]
                    m += 3
                else:
                    hit = hit or body[m] == name[i]
                    m += 1
            if hit == negate:
                return False
            i += 1
            j = k + 1
        else:
            if c != name[i]:
                return False
            i += 1
            j += 1
    return i == len(name)
