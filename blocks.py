import operator
import re
from functools import reduce

MAX_BYTE = 0b11111111


def int_to_bin(num, width):
    return [(num >> i) & 1 for i in range(width)]


def int_to_bool_list(hardware, num, width):
    return [(FalseBool, TrueBool)[bit](hardware) for bit in int_to_bin(num, width)]


def try_hash(val):
    try:
        return hash(val)
    except TypeError:
        return id(val)


def cache(func):
    results = {}

    def inner(*args, **kwargs):
        arg_key = tuple()
        for arg in args:
            arg_key = (*arg_key, try_hash(arg))
        kwarg_key = tuple()
        for name, value in kwargs.items():
            kwarg_key = (*kwarg_key, (name, try_hash(value)))
        key = (arg_key, kwarg_key)
        if key is results:
            return results[key]
        else:
            result = func(*args, **kwargs)
            results[key] = result
            return result

    return inner


class Hardware:
    def __init__(self):
        self.bit_count = 0
        self.html = ""
        self.css = ""
        self.finishers = []
        self.labels = []

    def label(self, bits, name):
        bit_ids = [bit.id_ for bit in bits]
        self.labels.append(((min(bit_ids), max(bit_ids)), name))

    def generate_debug(self):
        html = """
<table id="debug">
    <thead>
        <tr>
            <th>Label</th>
            <th>Dec</th>
            <th>Hex</th>
            <th>Bin</th>
            <th>Range</th>
        </tr>
    </thead>
    <tbody>
        """
        for (start, end), label in self.labels:
            html += f'<tr data-start="{start}" data-end="{end}" class="label">\n'
            html += f"<td>{label}</td>\n"
            html += '<td class="dec"></td>\n'
            html += f'<td class="hex"></td><td class="bin"></td>\n'
            html += f"<td>{start}-{end}</td>\n"
            html += "</tr>\n"
        html += "</tbody></table>\n"
        return html

    def bit(self, value=False):
        id_ = self.bit_count
        self.bit_count += 1
        self.html += f'<input type="checkbox" id="i{id_}"{" checked" if value else ""}>\n'
        return Bit(self, id_)

    def add_css(self, css):
        self.css += css + "\n"

    def alloc(self, bits):
        return Memory([self.bit() for _ in range(bits)])

    def const(self, values):
        return Memory([self.bit(value) for value in values])

    def register_finisher(self, func):
        self.finishers.append(func)

    def finish(self):
        for finisher in self.finishers:
            finisher()

    def output(self, html_loc, css_loc):
        debug_html = self.generate_debug()
        with open(html_loc) as file:
            html_template = file.read()
        with open(html_loc, "w") as file:
            insert_location = "(<!--HARDWARE START-->).*?(<!--HARDWARE END-->)"
            result = re.sub(insert_location, fr"\1\n{self.html}\2", html_template, 1, re.DOTALL)
            debug_location = "(<!--DEBUG START-->).*?(<!--DEBUG END-->)"
            result = re.sub(debug_location, fr"\1\n{debug_html}\2", result, 1, re.DOTALL)
            file.write(result)
        with open(css_loc) as file:
            css_template = file.read()
        with open(css_loc, "w") as file:
            insert_location = r"(/\*HARDWARE START\*/).*?(/\*HARDWARE END\*/)"
            file.write(re.sub(insert_location, fr"\1\n{self.css}\2", css_template, 1, re.DOTALL))


class Bool:
    def __init__(self, hardware):
        self.hardware = hardware

    @staticmethod
    def real_partition(values):
        return (
            [val for val in values if isinstance(val, CSSBool)],
            [val for val in values if not isinstance(val, CSSBool)]
        )

    @staticmethod
    def and_(*values):
        real, nonreal = Bool.real_partition(values)
        real_section = TrueBool(values[0].hardware)
        nonreal_section = TrueBool(values[0].hardware)
        if real:
            real_section = CSSBool(real[0].hardware, ''.join([f":is({b.css})" for b in real]))
        if nonreal:
            nonreal_section = reduce(operator.and_, nonreal)
        return real_section & nonreal_section

    @staticmethod
    def or_(*values):
        real, nonreal = Bool.real_partition(values)
        real_section = FalseBool(values[0].hardware)
        nonreal_section = FalseBool(values[0].hardware)
        if real:
            real_section = CSSBool(values[0].hardware, ",".join([value.css for value in values]))
        if nonreal:
            nonreal_section = reduce(operator.or_, nonreal)
        return real_section | nonreal_section

    @staticmethod
    def xor(*values):
        return reduce(operator.xor, values)

    @staticmethod
    def not_xor(*values):
        return ~reduce(operator.xor, values)


class TrueBool(Bool):
    def __init__(self, hardware):
        super().__init__(hardware)

    def __and__(self, other):
        return other

    def __or__(self, other):
        return TrueBool(self.hardware)

    def __invert__(self):
        return FalseBool(self.hardware)

    def __xor__(self, other):
        return ~other

    @staticmethod
    def xnor(other):
        return other


class FalseBool(Bool):
    def __init__(self, hardware):
        super().__init__(hardware)

    def __and__(self, other):
        return FalseBool(self.hardware)

    def __or__(self, other):
        return other

    def __invert__(self):
        return TrueBool(self.hardware)

    def __xor__(self, other):
        return other

    @staticmethod
    def xnor(other):
        return ~other


class CSSBool(Bool):
    def __init__(self, hardware, css):
        super().__init__(hardware)
        self.css = css

    def __and__(self, other):
        if not isinstance(other, CSSBool):
            return other & self
        return CSSBool(self.hardware, f":is({self.css}):is({other.css})")

    def __or__(self, other):
        if not isinstance(other, CSSBool):
            return other | self
        return CSSBool(self.hardware, f"{self.css},{other.css}")

    def __invert__(self):
        return CSSBool(self.hardware, f"$:not({self.css})")

    def __xor__(self, other):
        if not isinstance(other, CSSBool):
            return other ^ self
        return (self | other) & ~(self & other)

    def xnor(self, other):
        if not isinstance(other, CSSBool):
            return other.xnor(self)
        return (self & other) | ~(self | other)

    def sub_in(self, id_):
        def inner(match):
            oid = int(match.group(1))
            if id_ > oid:
                return f"#i{oid}:checked~#i{id_}"
            else:
                return f"#i{id_}:has(~#i{oid}:checked)"

        rels_subbed = re.sub("%(\\d+)%", inner, self.css)
        ids_subbed = rels_subbed.replace("$", f"#i{id_}")
        return f":is({ids_subbed})"

    def stage(self):
        bit = self.hardware.bit()
        bit.iff(self)
        return bit


class Bit(CSSBool):
    SWITCH = "{display:block;}"

    def __init__(self, hardware, id_):
        super().__init__(hardware, f"%{id_}%")
        self.id_ = id_

    def if_(self, cond):
        if isinstance(cond, CSSBool):
            selector = cond.sub_in(self.id_) + ":not(:checked)"
            self.hardware.add_css(selector + self.SWITCH)
        elif isinstance(cond, FalseBool):
            pass
        elif isinstance(cond, TrueBool):
            self.set(True)
        else:
            raise TypeError()

    def not_if(self, cond):
        if isinstance(cond, CSSBool):
            selector = cond.sub_in(self.id_) + ":checked"
            self.hardware.add_css(selector + self.SWITCH)
        elif isinstance(cond, FalseBool):
            pass
        elif isinstance(cond, TrueBool):
            self.set(False)
        else:
            raise TypeError()

    def iff(self, cond):
        self.if_(cond)
        self.not_if(~cond)

    def iff_when(self, cond, when):
        if when is None:
            self.iff(cond)
        else:
            self.if_(cond & when)
            self.not_if(~cond & when)

    def iff_not(self, cond):
        self.if_(~cond)
        self.not_if(cond)

    def iff_not_when(self, cond, when):
        self.if_(~cond & when)
        self.not_if(cond & when)

    def set(self, value):
        selector = f"#i{self.id_}" + (":not(:checked)" if value else ":checked")
        self.hardware.add_css(selector + self.SWITCH)

    def __repr__(self):
        return f"Bit({self.id_})"

    def label(self, label):
        self.hardware.label([self], label)


class Edged:
    def __init__(self, hardware, when):
        self.last = hardware.bit()
        self.now = hardware.bit()
        self.last.iff(self.now)
        self.now.iff(when)

    def rising(self):
        return self.now & ~self.last

    def falling(self):
        return self.last & ~self.now


class Bools:
    def __init__(self, bools):
        self.bools = bools

    def __eq__(self, other):
        if isinstance(other, Memory):
            return Bool.and_(*[
                ab.xnor(bb)
                for ab, bb in zip(self, other)
            ])
        raise TypeError()

    def __ne__(self, other):
        if isinstance(other, Memory):
            return Bool.or_(*[
                ab ^ bb
                for ab, bb in zip(self, other)
            ])
        raise TypeError()

    def __iter__(self):
        return (bit for bit in self.bools)

    def __getitem__(self, item):
        return self.bools[item]

    def __getslice__(self, slice_):
        return self.bools[slice_]

    def __len__(self):
        return len(self.bools)

    def __rshift__(self, rot):
        if not isinstance(rot, int):
            raise TypeError()
        return Memory([
            self[(i + rot) % len(self)]
            for i in range(len(self))
        ])

    def __lshift__(self, rot):
        return self >> -rot

    def __and__(self, other):
        return Bools(map(operator.and_, zip(self, other)))

    def __or__(self, other):
        return Bools(map(operator.or_, zip(self, other)))

    def __xor__(self, other):
        return Bools(map(operator.xor, zip(self, other)))

    def __invert__(self):
        return Bools(map(operator.invert, self))

    def reversed(self):
        return Bools(list(reversed(self)))

    def __repr__(self):
        return f"{type(self).__name__}({', '.join(map(repr, self))})"

    @staticmethod
    def stage(bools):
        if not bools:
            raise IndexError()
        memory = bools[0].hardware.alloc(len(bools))
        memory.assign(bools)
        return memory


class Memory(Bools):
    def __init__(self, bits):
        super().__init__(bits)

    def assign(self, value, when=None):
        for mem_bit, val_bool in zip(self, value):
            mem_bit.iff_when(val_bool, when)

    def reversed(self):
        return Memory(list(reversed(self)))

    def label(self, label):
        if self.bools:
            hardware = self.bools[0].hardware
            hardware.label(self.bools, label)

    @staticmethod
    def merge(pieces):
        return Memory([bit for piece in pieces for bit in piece])


class BitChain:
    def __init__(self, hardware, n):
        self.hardware = hardware
        self.bits = hardware.alloc(n)
        self.bits[0].iff(~self.bits[n - 1])
        for i, bit in enumerate(self.bits[1:]):
            bit.iff(self.bits[i])

    def at_least(self, n):
        return self.bits[n] & self.bits[0]

    def exactly(self, n):
        if n == len(self.bits) - 1:
            return self.bits[n] & self.bits[0]
        return self.bits[n] & ~self.bits[n + 1]

    def label(self, label):
        self.bits.label(label)


class OneHot(Memory):
    def __init__(self, hardware, options):
        super().__init__(hardware.alloc(options))
        self.options = options

    def set_source(self, source, when=None):
        for i in range(self.options):
            self.bools[i].iff_when(source == i, when)


class Array:
    def __init__(self, hardware, size, elem_bits, index_bits, initial=None):
        if initial is None:
            initial = []
        self.hardware = hardware
        self.index_bits = index_bits
        self.size = size
        self.elem_bits = elem_bits
        self.out = MemNumber(hardware, elem_bits)
        self.mem_sections = [
            (hardware.alloc(elem_bits) if i >= len(initial)
             else hardware.const(int_to_bin(initial[i], elem_bits)))
            for i in range(size)
        ]
        self.mem = Memory.merge(self.mem_sections)
        self.write_mode = hardware.bit()
        self.write_when = []
        self.in_ = MemNumber(hardware, elem_bits)
        self.index_marker = OneHot(hardware, size)
        self.index = MemNumber(hardware, index_bits)
        self.index_marker.set_source(self.index)

        for i in range(size):
            self.mem_sections[i].assign(self.in_, self.index_marker[i] & self.write_mode)
            self.out.assign(self.mem_sections[i], self.index_marker[i])

        hardware.register_finisher(self.finish)

    def finish(self):
        if self.write_when:
            self.write_mode.iff(Bool.or_(*self.write_when))

    def set(self, new_index, value, when):
        self.index.assign(new_index, when)
        self.in_.assign(value, when)
        self.write_when.append(when)

    def get(self, new_index, when):
        self.index.assign(new_index, when)
        return self.out

    def __getitem__(self, item):
        return self.mem_sections[item]


class Number(Bools):
    def __init__(self, hardware, width, bools):
        self.hardware = hardware
        self.width = width
        super().__init__(bools)

    def __eq__(self, other):
        if isinstance(other, int):
            return Bool.and_(*[
                bit if target else ~bit
                for target, bit in zip(int_to_bin(other, self.width), self)
            ])
        elif isinstance(other, Memory):
            return super().__eq__(other)
        raise TypeError()

    def __ne__(self, other):
        if isinstance(other, int):
            return Bool.or_(*[
                ~bit if target else bit
                for target, bit in zip(int_to_bin(other, self.width), self)
            ])
        elif isinstance(other, Memory):
            return super().__ne__(other)
        raise TypeError()

    @cache
    def greater_or_equal(self, other, when, carries=None):
        if carries is None:
            carries = [self.hardware.bit() for _ in range(self.width - 1)]

        greater_yet = FalseBool(self.hardware)
        is_lesses = []
        greater_yets = []
        first = True
        for ab, bb in reversed(list(zip(self, other))):
            if not first:
                carry = carries.pop()
                carry.iff_when(greater_yet, when)
                greater_yets.append(carry)
                greater_yet = carry
            is_lesses.append(bb & ~ab)
            greater_yet = greater_yet | (ab & ~bb)
            first = False
        greater_yets.append(greater_yet)

        return Bool.and_(*(
            ~is_less | greater_yet
            for is_less, greater_yet in zip(is_lesses, greater_yets)
        ))

    def upper(self, n):
        return Number(self.hardware, n, self.bools[-n:])

    def lower(self, n):
        return Number(self.hardware, n, self.bools[:n])

    def pad_top(self, size, typ):
        padding = [typ(self.hardware) for _ in range(size - len(self.bools))]
        return Number(self.hardware, size, self.bools + padding)

    def pad_bottom(self, size, typ):
        padding = [typ(self.hardware) for _ in range(size - len(self.bools))]
        return Number(self.hardware, size, padding + self.bools)

    def left_shift_nowrap(self, amount):
        return self.lower(self.width - amount).pad_bottom(self.width, FalseBool)

    def right_shift_nowrap(self, amount):
        return self.upper(self.width - amount).pad_top(self.width, FalseBool)

    def skip(self, n):
        return self.upper(self.width - n)

    def is_truthy(self):
        return Bool.or_(*self.bools)

    @classmethod
    def from_(cls, hardware, value):
        return cls(hardware, len(value), list(value))

    @cache
    def add(self, other, when, carries=None):
        if carries is None:
            carries = [self.hardware.bit() for _ in range(self.width - 2)]
        result = []

        if isinstance(other, Number):
            carry = None
            store_next_carry = False
            for ab, bb in zip(self, other):
                if store_next_carry:
                    carry_expr = carry
                    carry = carries.pop()
                    carry.iff_when(carry_expr, when)
                if carry is None:
                    new = ab ^ bb
                    carry = ab & bb
                else:
                    new = Bool.xor(ab, bb, carry)
                    carry = (ab & bb) | (carry & (ab | bb))
                    store_next_carry = True
                result.append(new)
            return Number(self.hardware, self.width, result)

        elif isinstance(other, int):
            carry = None
            store_next_carry = False
            for ab, bb in zip(self, int_to_bin(other, self.width)):
                if store_next_carry:
                    carry_expr = carry
                    carry = carries.pop()
                    carry.iff_when(carry_expr, when)
                if carry is None:
                    new = ~ab if bb else ab
                    carry = ab if bb else None
                else:
                    new = ab.xnor(carry) if bb else ab ^ carry
                    carry = ab | carry if bb else ab & carry
                    store_next_carry = True
                result.append(new)

        else:
            raise TypeError()

        return Number(self.hardware, self.width, result)

    def mult_no_special(self, other, when, carries=None):
        if carries is None:
            carries = [self.hardware.bit() for _ in range(2*self.width*self.width-3*self.width+2)]
        result = None
        for i in range(self.width):
            addend = self.left_shift_nowrap(i) & other[i]
            if result is None:
                result = addend
            else:
                stage = MemNumber(self.hardware, self.width, [carries.pop() for _ in range(self.width)])
                stage.assign(result.add(addend, when, carries), when)
                result = stage
        return result

    @cache
    def mult(self, other, when, carries=None):
        not_special = self.skip(1).is_truthy() | other.skip(1).is_truthy()
        return Number.or_(
            other & (self == 1),
            self & (other == 1),
            self.mult_no_special(other, when & not_special, carries) & not_special,
        )

    def __and__(self, other):
        if isinstance(other, int):
            other = int_to_bool_list(self.hardware, other, self.width)
        if isinstance(other, Bool):
            other = [other] * self.width
        return Number(self.hardware, self.width, [ab & bb for ab, bb in zip(self, other)])

    def __or__(self, other):
        if isinstance(other, int):
            other = int_to_bool_list(self.hardware, other, self.width)
        if isinstance(other, Bool):
            other = [other] * self.width
        return Number(self.hardware, self.width, [ab | bb for ab, bb in zip(self, other)])

    def __xor__(self, other):
        if isinstance(other, int):
            other = int_to_bool_list(self.hardware, other, self.width)
        if isinstance(other, Bool):
            other = [other] * self.width
        return Number(self.hardware, self.width, [ab ^ bb for ab, bb in zip(self, other)])

    def __invert__(self):
        return Number(self.hardware, self.width, map(operator.invert, self))

    def __rshift__(self, rot):
        return Number(self.hardware, self.width, super().__rshift__(rot))

    def __lshift__(self, rot):
        return Number(self.hardware, self.width, super().__lshift__(rot))

    @staticmethod
    def and_(*values):
        return reduce(operator.and_, values)

    @staticmethod
    def or_(*values):
        return reduce(operator.or_, values)

    @staticmethod
    def xor(*values):
        return reduce(operator.xor, values)

    @classmethod
    def zero(cls, hardware, size):
        return cls(hardware, size, [FalseBool(hardware) for _ in range(size)])

    def reversed(self):
        return Number(self.hardware, self.width, list(reversed(self)))

    @staticmethod
    def stage(number):
        memory = MemNumber(number.hardware, number.width)
        memory.assign(number)
        return memory


class MemNumber(Number, Memory):
    def __init__(self, hardware: Hardware, width: int, value: int | list[Bool] = 0):
        if isinstance(value, int):
            super().__init__(hardware, width, hardware.const(int_to_bin(value, width)))
        elif isinstance(value, list):
            super().__init__(hardware, width, value)
        else:
            raise TypeError()


class Counter(MemNumber):
    def __init__(self, hardware, width, value=0):
        super().__init__(hardware, width, value)
        self.next_val_rev = hardware.alloc(width).reversed()
        self.count_whens = []
        self.hardware.register_finisher(self.finish)

    def finish(self):
        if not self.count_whens:
            return
        when = Bool.or_(*self.count_whens)
        self.assign(self.next_val_rev, when)
        self.next_val_rev[0].iff_when(~self[0], ~when)
        self.next_val_rev[1].iff_when(self.next_val_rev[0].xnor(self[1]), ~when)
        for i in range(2, self.width):
            is_true = (self[i - 1] & ~self.next_val_rev[i - 1]) ^ self[i]
            self.next_val_rev[i].iff_when(is_true, ~when)

    @cache
    def count(self, when):
        self.count_whens.append(when)
