"""random for MicroPython, installed as `random` (charm_stdlib): CPython's
Random class, which Ren'Py's renpy.random subclasses and games call
(randint, choice, random, shuffle), on the same Mersenne Twister with the
same seeding, so a seeded sequence matches CPython's. Python 2 drew
integers and choices from random() and Python 3 from getrandbits; PY2,
set by the driver for Python 2 games, picks the game's version."""
import random as _native

PY2 = False

_N = 624
_M = 397
_MASK = 0xffffffff


def _bit_length(n):
    length = 0
    while n:
        n >>= 1
        length += 1
    return length


class Random(object):
    VERSION = 3

    def __init__(self, x=None):
        self.gauss_next = None
        self.seed(x)

    def seed(self, a=None, version=2):
        if a is None:
            key = [_native.getrandbits(32) for _ in range(4)]
        else:
            if isinstance(a, (str, bytes, bytearray)):
                a = hash(a)  # CPython hashes strings with SHA-512 (3) or its own hash (2); neither is here
            a = abs(int(a))
            key = []
            while a:
                key.append(a & _MASK)
                a >>= 32
            if not key:
                key = [0]
        self._init_by_array(key)
        self.gauss_next = None

    def _init_genrand(self, s):
        mt = self._mt = [0] * _N
        mt[0] = s & _MASK
        for i in range(1, _N):
            mt[i] = (1812433253 * (mt[i - 1] ^ (mt[i - 1] >> 30)) + i) & _MASK
        self._index = _N

    def _init_by_array(self, key):
        self._init_genrand(19650218)
        mt = self._mt
        i, j = 1, 0
        for _ in range(max(_N, len(key))):
            mt[i] = ((mt[i] ^ ((mt[i - 1] ^ (mt[i - 1] >> 30)) * 1664525)) + key[j] + j) & _MASK
            i += 1
            j += 1
            if i >= _N:
                mt[0] = mt[_N - 1]
                i = 1
            if j >= len(key):
                j = 0
        for _ in range(_N - 1):
            mt[i] = ((mt[i] ^ ((mt[i - 1] ^ (mt[i - 1] >> 30)) * 1566083941)) - i) & _MASK
            i += 1
            if i >= _N:
                mt[0] = mt[_N - 1]
                i = 1
        mt[0] = 0x80000000

    def _genrand32(self):
        mt = self._mt
        if self._index >= _N:
            for k in range(_N):
                y = (mt[k] & 0x80000000) | (mt[(k + 1) % _N] & 0x7fffffff)
                v = mt[(k + _M) % _N] ^ (y >> 1)
                if y & 1:
                    v ^= 0x9908b0df
                mt[k] = v
            self._index = 0
        y = mt[self._index]
        self._index += 1
        y ^= y >> 11
        y ^= (y << 7) & 0x9d2c5680
        y ^= (y << 15) & 0xefc60000
        y ^= y >> 18
        return y

    def random(self):
        a = self._genrand32() >> 5
        b = self._genrand32() >> 6
        return (a * 67108864.0 + b) * (1.0 / 9007199254740992.0)

    def getrandbits(self, k):
        if k <= 0:
            raise ValueError("number of bits must be greater than zero")
        if k <= 32:
            return self._genrand32() >> (32 - k)
        result = 0
        shift = 0
        while k > 0:
            r = self._genrand32()
            if k < 32:
                r >>= 32 - k
            result |= r << shift
            shift += 32
            k -= 32
        return result

    def getstate(self):
        return self.VERSION, tuple(self._mt) + (self._index,), self.gauss_next

    def setstate(self, state):
        version, internal, self.gauss_next = state
        self._mt = list(internal[:_N])
        self._index = internal[_N]

    def _randbelow(self, n):
        k = _bit_length(n)
        r = self.getrandbits(k)
        while r >= n:
            r = self.getrandbits(k)
        return r

    def randrange(self, start, stop=None, step=1):
        istart = int(start)
        if stop is None:
            if istart <= 0:
                raise ValueError("empty range for randrange()")
            return int(self.random() * istart) if PY2 else self._randbelow(istart)
        istop = int(stop)
        width = istop - istart
        if step == 1:
            if width <= 0:
                raise ValueError("empty range for randrange() (%d, %d, %d)" % (istart, istop, width))
            return int(istart + int(self.random() * width)) if PY2 else istart + self._randbelow(width)
        istep = int(step)
        if istep > 0:
            n = (width + istep - 1) // istep
        elif istep < 0:
            n = (width + istep + 1) // istep
        else:
            raise ValueError("zero step for randrange()")
        if n <= 0:
            raise ValueError("empty range for randrange()")
        return istart + istep * (int(self.random() * n) if PY2 else self._randbelow(n))

    def randint(self, a, b):
        return self.randrange(a, b + 1)

    def choice(self, seq):
        if PY2:
            return seq[int(self.random() * len(seq))]
        if not len(seq):
            raise IndexError('Cannot choose from an empty sequence')
        return seq[self._randbelow(len(seq))]

    def shuffle(self, x):
        for i in reversed(range(1, len(x))):
            j = int(self.random() * (i + 1)) if PY2 else self._randbelow(i + 1)
            x[i], x[j] = x[j], x[i]

    def sample(self, population, k):
        n = len(population)
        if not 0 <= k <= n:
            raise ValueError("sample larger than population or is negative")
        pool = list(population)
        result = [None] * k
        for i in range(k):
            j = int(self.random() * (n - i)) if PY2 else self._randbelow(n - i)
            result[i] = pool[j]
            pool[j] = pool[n - i - 1]
        return result

    def uniform(self, a, b):
        return a + (b - a) * self.random()


_inst = Random()
seed = _inst.seed
random = _inst.random
uniform = _inst.uniform
randint = _inst.randint
choice = _inst.choice
randrange = _inst.randrange
sample = _inst.sample
shuffle = _inst.shuffle
getstate = _inst.getstate
setstate = _inst.setstate
getrandbits = _inst.getrandbits
