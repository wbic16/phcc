#!/usr/bin/env python3
"""trace_model.py — an independent model of the preprocessor
conditional-stack machine, written from the machine scroll's rules
(which were derived from tccpp.c). Used by run_trace_tests.py to
predict, for a test input: which marker lines the preprocessor must
emit, or which machine error it must raise, and the frame-state
path taken. The driver then checks the path is a legal path in the
machine scroll and that the real tcc's observable output matches.

Model fidelity notes (mirroring tccpp.c, not the C standard):
  - when the top frame suppresses, the region is consumed by
    preprocess_skip: nested directives are COUNTED, not executed;
    only a boundary #elif/#else/#endif at nesting 0 is dispatched
    to preprocess() for the top frame;
  - #elif after a taken branch does not evaluate its expression;
  - frames below the top are always emitting (a frame is pushed
    only while every frame below emits).

Expression support: the C constant-expression subset used by the
authored tests - integer literals, identifiers, defined(X),
defined X, object-like macro expansion, ! ~ - + * / % << >> < <=
> >= == != & ^ | && || and parentheses. Anything else makes the
model raise Unsupported, loudly.
"""
import re


class ModelError(Exception):
    """The machine mandates an error with this message."""


class Unsupported(Exception):
    pass


# ----------------------------------------------------------------
# expression evaluation

TOKEN_RE = re.compile(r"""
    \s*(?:(?P<num>0[xX][0-9a-fA-F]+[uUlL]*|\d+[uUlL]*)
    |(?P<name>[A-Za-z_][A-Za-z0-9_]*)
    |(?P<op><<|>>|<=|>=|==|!=|&&|\|\||[-+*/%<>&^|!~()?:]))""", re.X)


def tokenize(expr):
    toks, i = [], 0
    while i < len(expr):
        m = TOKEN_RE.match(expr, i)
        if not m:
            if expr[i].isspace():
                i += 1
                continue
            raise Unsupported(f"bad character in expression: {expr[i]!r}")
        i = m.end()
        if m.group("num") is not None:
            toks.append(("num", m.group("num")))
        elif m.group("name") is not None:
            toks.append(("name", m.group("name")))
        else:
            toks.append(("op", m.group("op")))
    toks.append(("end", ""))
    return toks


class ExprParser:
    def __init__(self, toks, macros):
        self.toks = toks
        self.i = 0
        self.macros = macros  # name -> ("int", value-expr-tokens) | ("funclike",)

    def peek(self):
        return self.toks[self.i]

    def next(self):
        t = self.toks[self.i]
        self.i += 1
        return t

    def expect_op(self, op):
        k, v = self.next()
        if (k, v) != ("op", op):
            raise Unsupported(f"expected {op}, got {v}")

    def parse(self):
        v = self.parse_or()
        if self.peek()[0] != "end":
            raise Unsupported("trailing tokens in expression")
        return v

    def parse_or(self):
        v = self.parse_and()
        while self.peek() == ("op", "||"):
            self.next()
            r = self.parse_and()
            v = 1 if (v or r) else 0
        return v

    def parse_and(self):
        v = self.parse_bitor()
        while self.peek() == ("op", "&&"):
            self.next()
            r = self.parse_bitor()
            v = 1 if (v and r) else 0
        return v

    def parse_bitor(self):
        v = self.parse_bitxor()
        while self.peek() == ("op", "|"):
            self.next()
            v = v | self.parse_bitxor()
        return v

    def parse_bitxor(self):
        v = self.parse_bitand()
        while self.peek() == ("op", "^"):
            self.next()
            v = v ^ self.parse_bitand()
        return v

    def parse_bitand(self):
        v = self.parse_equality()
        while self.peek() == ("op", "&"):
            self.next()
            v = v & self.parse_equality()
        return v

    def parse_equality(self):
        v = self.parse_rel()
        while self.peek() in (("op", "=="), ("op", "!=")):
            op = self.next()[1]
            r = self.parse_rel()
            v = 1 if ((v == r) if op == "==" else (v != r)) else 0
        return v

    def parse_rel(self):
        v = self.parse_shift()
        while self.peek() in (("op", "<"), ("op", "<="),
                              ("op", ">"), ("op", ">=")):
            op = self.next()[1]
            r = self.parse_shift()
            v = 1 if {"<": v < r, "<=": v <= r,
                      ">": v > r, ">=": v >= r}[op] else 0
        return v

    def parse_shift(self):
        v = self.parse_add()
        while self.peek() in (("op", "<<"), ("op", ">>")):
            op = self.next()[1]
            r = self.parse_add()
            v = v << r if op == "<<" else v >> r
        return v

    def parse_add(self):
        v = self.parse_mul()
        while self.peek() in (("op", "+"), ("op", "-")):
            op = self.next()[1]
            r = self.parse_mul()
            v = v + r if op == "+" else v - r
        return v

    def parse_mul(self):
        v = self.parse_unary()
        while self.peek() in (("op", "*"), ("op", "/"), ("op", "%")):
            op = self.next()[1]
            r = self.parse_unary()
            if op == "*":
                v = v * r
            else:
                if r == 0:
                    raise Unsupported("division by zero in model "
                                      "expression")
                q = abs(v) // abs(r)
                if (v < 0) != (r < 0):
                    q = -q
                v = q if op == "/" else v - q * r
        return v

    def parse_unary(self):
        k, val = self.peek()
        if (k, val) == ("op", "!"):
            self.next()
            return 0 if self.parse_unary() else 1
        if (k, val) == ("op", "~"):
            self.next()
            return ~self.parse_unary()
        if (k, val) == ("op", "-"):
            self.next()
            return -self.parse_unary()
        if (k, val) == ("op", "+"):
            self.next()
            return self.parse_unary()
        return self.parse_primary()

    def parse_primary(self):
        k, val = self.next()
        if k == "num":
            s = val.rstrip("uUlL")
            return int(s, 16) if s.lower().startswith("0x") else int(s, 10)
        if (k, val) == ("op", "("):
            v = self.parse_or()
            self.expect_op(")")
            return v
        if k == "name":
            if val == "defined":
                k2, v2 = self.next()
                if (k2, v2) == ("op", "("):
                    k3, name = self.next()
                    if k3 != "name":
                        raise Unsupported("defined() needs a name")
                    self.expect_op(")")
                elif k2 == "name":
                    name = v2
                else:
                    raise Unsupported("defined needs a name")
                return 1 if name in self.macros else 0
            if val in self.macros:
                kind = self.macros[val]
                if kind[0] == "funclike":
                    raise Unsupported(f"function-like macro {val} in "
                                      f"#if expression")
                return eval_expr(kind[1], self.macros, depth=1)
            return 0  # undefined identifier in a pp expression
        raise Unsupported(f"unexpected token {val!r}")


def eval_expr(expr, macros, depth=0):
    if depth > 32:
        raise Unsupported("macro expansion too deep")
    return ExprParser(tokenize(expr), macros).parse()


# ----------------------------------------------------------------
# the machine model

DIRECTIVE = re.compile(r"^\s*#\s*([A-Za-z_]+)\s*(.*?)\s*$")
MARKER = re.compile(r"^MK_[A-Z0-9_]+$")


class Frame:
    def __init__(self, slot, state):
        self.slot = slot
        self.state = state


class Model:
    def __init__(self):
        self.frames = []
        self.macros = {}       # name -> ("int", expr-string) | ("funclike",)
        self.skipping = False  # inside preprocess_skip for the top frame
        self.skip_depth = 0    # preprocess_skip's local counter 'a'
        self.emitted = []      # marker names, in order
        self.path = []         # (from_state, event, to_state)

    def top_state(self):
        return self.frames[-1].state if self.frames else "EMPTY"

    def step(self, frm, event, to):
        self.path.append((frm, event, to))

    # -- condition evaluation
    def cond_value(self, directive, rest):
        if directive == "ifdef":
            name = rest.split()[0] if rest.split() else ""
            return 1 if name in self.macros else 0
        if directive == "ifndef":
            name = rest.split()[0] if rest.split() else ""
            return 0 if name in self.macros else 1
        return 1 if eval_expr(rest, self.macros) != 0 else 0

    # -- events on the top frame (dispatched by preprocess())
    def ev_if(self, directive, rest):
        frm = self.top_state()
        if len(self.frames) >= 64:
            self.step(frm, "ev_if", 'ERROR "memory full (ifdef)"')
            raise ModelError("memory full (ifdef)")
        v = self.cond_value(directive, rest)
        state = "ACTIVE" if v == 1 else "SKIP_NOT_TAKEN"
        self.frames.append(Frame(v, state))
        self.step(frm, "ev_if", state)
        if v == 0:
            self.skipping = True
            self.skip_depth = 0

    def ev_elif(self, rest):
        if not self.frames:
            self.step("EMPTY", "ev_elif",
                      'ERROR "#elif without matching #if"')
            raise ModelError("#elif without matching #if")
        f = self.frames[-1]
        frm = f.state
        if f.slot > 1:
            self.step(frm, "ev_elif", 'ERROR "#elif after #else"')
            raise ModelError("#elif after #else")
        if f.slot == 1:
            f.state = "TAKEN_QUIET"
            self.step(frm, "ev_elif", "TAKEN_QUIET")
            self.skipping = True
            self.skip_depth = 0
            return
        v = self.cond_value("if", rest)
        f.slot = v
        f.state = "ACTIVE" if v == 1 else "SKIP_NOT_TAKEN"
        self.step(frm, "ev_elif", f.state)
        if v == 0:
            self.skipping = True
            self.skip_depth = 0
        else:
            self.skipping = False

    def ev_else(self):
        if not self.frames:
            self.step("EMPTY", "ev_else",
                      'ERROR "#else without matching #if"')
            raise ModelError("#else without matching #if")
        f = self.frames[-1]
        frm = f.state
        if f.slot & 2:
            self.step(frm, "ev_else", 'ERROR "#else after #else"')
            raise ModelError("#else after #else")
        f.slot ^= 3
        if frm in ("ACTIVE", "TAKEN_QUIET"):
            f.state = "SKIP_TAKEN"
            self.step(frm, "ev_else", "SKIP_TAKEN")
            self.skipping = True
            self.skip_depth = 0
        else:  # SKIP_NOT_TAKEN
            f.state = "ACTIVE_ELSE"
            self.step(frm, "ev_else", "ACTIVE_ELSE")
            self.skipping = False

    def ev_endif(self):
        if not self.frames:
            self.step("EMPTY", "ev_endif",
                      'ERROR "#endif without matching #if"')
            raise ModelError("#endif without matching #if")
        frm = self.frames[-1].state
        self.frames.pop()
        self.step(frm, "ev_endif", "pop")
        self.skipping = False

    # -- main scan
    def run(self, source):
        for raw in source.splitlines():
            line = raw.strip()
            m = DIRECTIVE.match(raw)
            directive = m.group(1) if m else None
            rest = m.group(2) if m else ""
            if self.skipping:
                if directive in ("if", "ifdef", "ifndef"):
                    self.skip_depth += 1
                elif directive == "endif":
                    if self.skip_depth == 0:
                        self.ev_endif()
                    else:
                        self.skip_depth -= 1
                elif directive in ("elif", "else"):
                    if self.skip_depth == 0:
                        if directive == "elif":
                            self.ev_elif(rest)
                        else:
                            self.ev_else()
                    # else: counted region, directive not executed
                # everything else inside a skipped region: ignored
                continue
            if directive in ("if", "ifdef", "ifndef"):
                self.ev_if(directive, rest)
            elif directive == "elif":
                self.ev_elif(rest)
            elif directive == "else":
                self.ev_else()
            elif directive == "endif":
                self.ev_endif()
            elif directive == "define":
                dm = re.match(r"([A-Za-z_][A-Za-z0-9_]*)(\()(.*)", rest)
                if dm:
                    self.macros[dm.group(1)] = ("funclike",)
                else:
                    parts = rest.split(None, 1)
                    if parts:
                        self.macros[parts[0]] = (
                            "int", parts[1] if len(parts) > 1 else "1")
            elif directive == "undef":
                self.macros.pop(rest.split()[0] if rest.split() else "",
                                None)
            elif directive == "error":
                raise ModelError("#error (in active region)")
            elif directive is None:
                if MARKER.match(line):
                    self.emitted.append(line)
            # other directives (#include, #pragma, ...): no markers
            # in the authored tests depend on them.
        if self.frames:
            self.step(self.top_state(), "ev_eof",
                      'ERROR "missing #endif"')
            raise ModelError("missing #endif")
        return self.emitted, self.path
