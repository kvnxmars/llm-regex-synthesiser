"""
regex_engine.py
================
A small, fully auditable regex -> NFA -> DFA -> minimal DFA engine.

Why a custom engine instead of `re` / `automata-lib` / `greenery`?
- Python's `re` module has no Deterministic Finite Automaton (DFA) / equivalence-checking primitives.
- Third-party FSM libraries impose their own regex dialects, which would
  complicate mapping directly onto Ade-Ibijola's five complexity levels.
- For an Honours thesis, a from-scratch Thompson construction +
  subset construction + minimization is standard, easily defensible in a
  methodology chapter, and gives full control over the restricted
  alphabet/operator set the study requires.

Supported syntax (matches the five complexity levels in the brief):
  literals        : a b c ...
  concatenation    : ab
  alternation      : a|b
  grouping         : (a|b)c
  quantifiers      : a* a+ a? a{2,4} a{2,} a{2}
  character classes: [abc] [a-z] [A-Z0-9] [^a-z] (negation)

The alphabet is explicit and finite (passed in or inferred from the pattern),
which is required for complementation / equivalence checking over DFAs.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import FrozenSet, Optional
import itertools

EPSILON = None  # sentinel for epsilon transitions in the NFA


# --------------------------------------------------------------------------
# 1. Parser -> AST
# --------------------------------------------------------------------------

class Node:
    pass


@dataclass
class Lit(Node):
    ch: str


@dataclass
class CharClass(Node):
    chars: FrozenSet[str]
    negated: bool = False


@dataclass
class Concat(Node):
    left: Node
    right: Node


@dataclass
class Union(Node):
    left: Node
    right: Node


@dataclass
class Star(Node):
    child: Node


@dataclass
class Plus(Node):
    child: Node


@dataclass
class Optional_(Node):
    child: Node


@dataclass
class Repeat(Node):
    child: Node
    lo: int
    hi: Optional[int]  # None means unbounded


class RegexSyntaxError(ValueError):
    pass


class Parser:
    """Recursive-descent parser.

    Grammar:
        expr    := term ('|' term)*
        term    := factor+ | epsilon
        factor  := atom quant?
        quant   := '*' | '+' | '?' | '{' INT (',' INT?)? '}'
        atom    := LIT | charclass | '(' expr ')'
        charclass := '[' '^'? item+ ']'
        item    := CHAR '-' CHAR | CHAR
    """

    METACHARS = set("|*+?(){}[]^-")

    def __init__(self, pattern: str, alphabet: Optional[set] = None):
        self.s = pattern
        self.i = 0
        self.n = len(pattern)
        self.alphabet = alphabet  # used to expand negated classes at parse time if given

    def peek(self) -> Optional[str]:
        return self.s[self.i] if self.i < self.n else None

    def advance(self) -> str:
        c = self.s[self.i]
        self.i += 1
        return c

    def parse(self) -> Node:
        node = self.parse_expr()
        if self.i != self.n:
            raise RegexSyntaxError(f"Unexpected character at position {self.i}: {self.s[self.i:]}")
        return node

    def parse_expr(self) -> Node:
        node = self.parse_term()
        while self.peek() == '|':
            self.advance()
            rhs = self.parse_term()
            node = Union(node, rhs)
        return node

    def parse_term(self) -> Node:
        factors = []
        while self.peek() is not None and self.peek() not in ('|', ')'):
            factors.append(self.parse_factor())
        if not factors:
            raise RegexSyntaxError("Empty term is not supported (no epsilon literal in this study)")
        node = factors[0]
        for f in factors[1:]:
            node = Concat(node, f)
        return node

    def parse_factor(self) -> Node:
        atom = self.parse_atom()
        q = self.peek()
        if q == '*':
            self.advance()
            return Star(atom)
        if q == '+':
            self.advance()
            return Plus(atom)
        if q == '?':
            self.advance()
            return Optional_(atom)
        if q == '{':
            self.advance()
            lo_str = ""
            while self.peek() is not None and self.peek().isdigit():
                lo_str += self.advance()
            if lo_str == "":
                raise RegexSyntaxError("Expected integer after '{'")
            lo = int(lo_str)
            hi = lo
            if self.peek() == ',':
                self.advance()
                hi_str = ""
                while self.peek() is not None and self.peek().isdigit():
                    hi_str += self.advance()
                hi = int(hi_str) if hi_str else None
            if self.peek() != '}':
                raise RegexSyntaxError("Expected closing '}' in quantifier")
            self.advance()
            return Repeat(atom, lo, hi)
        return atom

    def parse_atom(self) -> Node:
        c = self.peek()
        if c is None:
            raise RegexSyntaxError("Unexpected end of pattern")
        if c == '(':
            self.advance()
            node = self.parse_expr()
            if self.peek() != ')':
                raise RegexSyntaxError("Expected closing ')'")
            self.advance()
            return node
        if c == '[':
            return self.parse_charclass()
        if c in self.METACHARS:
            raise RegexSyntaxError(f"Unexpected metacharacter '{c}' at position {self.i}")
        self.advance()
        return Lit(c)

    def parse_charclass(self) -> CharClass:
        assert self.advance() == '['
        negated = False
        if self.peek() == '^':
            negated = True
            self.advance()
        chars = set()
        while self.peek() is not None and self.peek() != ']':
            c1 = self.advance()
            if self.peek() == '-' and self.i + 1 < self.n and self.s[self.i + 1] != ']':
                self.advance()  # consume '-'
                c2 = self.advance()
                if ord(c1) > ord(c2):
                    raise RegexSyntaxError(f"Invalid range {c1}-{c2}")
                for code in range(ord(c1), ord(c2) + 1):
                    chars.add(chr(code))
            else:
                chars.add(c1)
        if self.peek() != ']':
            raise RegexSyntaxError("Expected closing ']' in character class")
        self.advance()
        return CharClass(frozenset(chars), negated=negated)


def parse_regex(pattern: str) -> Node:
    return Parser(pattern).parse()


def infer_alphabet(pattern: str) -> FrozenSet[str]:
    """Collect all literal symbols mentioned in the pattern (ignores negation
    scope; use an explicit alphabet if negated classes are involved, since the
    complement is only well defined relative to a fixed finite alphabet)."""
    node = parse_regex(pattern)
    syms = set()

    def walk(n: Node):
        if isinstance(n, Lit):
            syms.add(n.ch)
        elif isinstance(n, CharClass):
            syms.update(n.chars)
        elif isinstance(n, (Concat, Union)):
            walk(n.left)
            walk(n.right)
        elif isinstance(n, (Star, Plus, Optional_, Repeat)):
            walk(n.child)

    walk(node)
    return frozenset(syms)


# --------------------------------------------------------------------------
# 2. Thompson construction: AST -> epsilon-NFA
# --------------------------------------------------------------------------

@dataclass
class NFA:
    start: int
    accept: int
    # transitions[state][symbol] -> set of destination states; symbol=None is epsilon
    transitions: dict = field(default_factory=dict)
    num_states: int = 0

    def add_state(self) -> int:
        s = self.num_states
        self.transitions[s] = {}
        self.num_states += 1
        return s

    def add_edge(self, src: int, symbol: Optional[str], dst: int):
        self.transitions[src].setdefault(symbol, set()).add(dst)


class ThompsonBuilder:
    def __init__(self, alphabet: FrozenSet[str]):
        self.alphabet = alphabet

    def build(self, node: Node) -> NFA:
        nfa = NFA(start=0, accept=0)
        s, a = self._build(node, nfa)
        nfa.start, nfa.accept = s, a
        return nfa

    def _build(self, node: Node, nfa: NFA):
        if isinstance(node, Lit):
            s, a = nfa.add_state(), nfa.add_state()
            nfa.add_edge(s, node.ch, a)
            return s, a
        if isinstance(node, CharClass):
            symbols = (self.alphabet - node.chars) if node.negated else node.chars
            s, a = nfa.add_state(), nfa.add_state()
            for ch in symbols:
                nfa.add_edge(s, ch, a)
            return s, a
        if isinstance(node, Concat):
            s1, a1 = self._build(node.left, nfa)
            s2, a2 = self._build(node.right, nfa)
            nfa.add_edge(a1, EPSILON, s2)
            return s1, a2
        if isinstance(node, Union):
            s1, a1 = self._build(node.left, nfa)
            s2, a2 = self._build(node.right, nfa)
            s, a = nfa.add_state(), nfa.add_state()
            nfa.add_edge(s, EPSILON, s1)
            nfa.add_edge(s, EPSILON, s2)
            nfa.add_edge(a1, EPSILON, a)
            nfa.add_edge(a2, EPSILON, a)
            return s, a
        if isinstance(node, Star):
            s1, a1 = self._build(node.child, nfa)
            s, a = nfa.add_state(), nfa.add_state()
            nfa.add_edge(s, EPSILON, s1)
            nfa.add_edge(s, EPSILON, a)
            nfa.add_edge(a1, EPSILON, s1)
            nfa.add_edge(a1, EPSILON, a)
            return s, a
        if isinstance(node, Plus):
            # a+ == a . a*
            return self._build(Concat(node.child, Star(node.child)), nfa)
        if isinstance(node, Optional_):
            # a? == (a|epsilon) -- implement directly to avoid empty-term issue
            s1, a1 = self._build(node.child, nfa)
            s, a = nfa.add_state(), nfa.add_state()
            nfa.add_edge(s, EPSILON, s1)
            nfa.add_edge(s, EPSILON, a)
            nfa.add_edge(a1, EPSILON, a)
            return s, a
        if isinstance(node, Repeat):
            lo, hi = node.lo, node.hi
            parts = []
            for _ in range(lo):
                parts.append(node.child)
            if hi is None:
                # a{lo,} == a^lo . a*
                parts.append(Star(node.child))
            else:
                for _ in range(hi - lo):
                    parts.append(Optional_(node.child))
            if not parts:
                raise RegexSyntaxError("{0,0} repetition unsupported (no epsilon literal)")
            n = parts[0]
            for p in parts[1:]:
                n = Concat(n, p)
            return self._build(n, nfa)
        raise TypeError(f"Unknown AST node: {node!r}")


def epsilon_closure(nfa: NFA, states) -> FrozenSet[int]:
    stack = list(states)
    seen = set(states)
    while stack:
        s = stack.pop()
        for dst in nfa.transitions[s].get(EPSILON, ()):
            if dst not in seen:
                seen.add(dst)
                stack.append(dst)
    return frozenset(seen)


# --------------------------------------------------------------------------
# 3. Subset construction: NFA -> complete DFA (with explicit trap state)
# --------------------------------------------------------------------------

@dataclass
class DFA:
    start: int
    accepts: FrozenSet[int]
    transitions: dict  # state -> {symbol: state}, complete over alphabet
    alphabet: FrozenSet[str]
    num_states: int
    trap: int  # dead/non-accepting sink state id


def nfa_to_dfa(nfa: NFA, alphabet: FrozenSet[str]) -> DFA:
    """Standard subset construction, producing a *complete* DFA (every state
    has an outgoing transition for every symbol, via an explicit trap state).
    Completeness is required so that equivalence checking (product automaton)
    and complementation are well defined."""
    TRAP = frozenset()  # sentinel for the dead state
    start_set = epsilon_closure(nfa, {nfa.start})

    discovered = {start_set: 0, TRAP: 1}
    order = [start_set, TRAP]
    frontier = [start_set]

    while frontier:
        cur = frontier.pop()
        if cur == TRAP:
            continue
        for sym in alphabet:
            dst_states = set()
            for s in cur:
                dst_states.update(nfa.transitions[s].get(sym, ()))
            closure = epsilon_closure(nfa, dst_states) if dst_states else TRAP
            if closure not in discovered:
                discovered[closure] = len(discovered)
                order.append(closure)
                frontier.append(closure)

    transitions = {}
    accepts = set()
    for state_set, i in discovered.items():
        transitions[i] = {}
        if state_set != TRAP and nfa.accept in state_set:
            accepts.add(i)
        for sym in alphabet:
            if state_set == TRAP:
                transitions[i][sym] = discovered[TRAP]
                continue
            dst_states = set()
            for s in state_set:
                dst_states.update(nfa.transitions[s].get(sym, ()))
            closure = epsilon_closure(nfa, dst_states) if dst_states else TRAP
            transitions[i][sym] = discovered[closure]

    return DFA(
        start=discovered[start_set],
        accepts=frozenset(accepts),
        transitions=transitions,
        alphabet=alphabet,
        num_states=len(discovered),
        trap=discovered[TRAP],
    )


def regex_to_dfa(pattern: str, alphabet: Optional[FrozenSet[str]] = None) -> DFA:
    ast = parse_regex(pattern)
    if alphabet is None:
        alphabet = infer_alphabet(pattern)
    nfa = ThompsonBuilder(alphabet).build(ast)
    return nfa_to_dfa(nfa, alphabet)


# --------------------------------------------------------------------------
# 4. Minimization (Moore's partition-refinement algorithm; alphabets here
#    are small so Hopcroft's asymptotic edge over Moore's doesn't matter)
# --------------------------------------------------------------------------

def minimize(dfa: DFA) -> DFA:
    states = list(range(dfa.num_states))
    # Initial partition: accepting vs non-accepting
    partition = {s: (1 if s in dfa.accepts else 0) for s in states}

    changed = True
    while changed:
        changed = False
        new_labels = {}
        signature_to_id = {}
        for s in states:
            sig = (partition[s], tuple(partition[dfa.transitions[s][sym]] for sym in sorted(dfa.alphabet)))
            if sig not in signature_to_id:
                signature_to_id[sig] = len(signature_to_id)
            new_labels[s] = signature_to_id[sig]
        if new_labels != partition:
            changed = True
        partition = new_labels

    # Build minimized DFA from partition classes
    class_ids = sorted(set(partition.values()))
    remap = {c: i for i, c in enumerate(class_ids)}
    new_num_states = len(class_ids)
    new_transitions = {i: {} for i in range(new_num_states)}
    new_accepts = set()
    representative = {}
    for s in states:
        cls = remap[partition[s]]
        representative.setdefault(cls, s)
        if s in dfa.accepts:
            new_accepts.add(cls)
    for cls, rep in representative.items():
        for sym in dfa.alphabet:
            dst = dfa.transitions[rep][sym]
            new_transitions[cls][sym] = remap[partition[dst]]
    new_start = remap[partition[dfa.start]]
    new_trap = remap[partition[dfa.trap]]

    return DFA(
        start=new_start,
        accepts=frozenset(new_accepts),
        transitions=new_transitions,
        alphabet=dfa.alphabet,
        num_states=new_num_states,
        trap=new_trap,
    )


def dfa_accepts(dfa: DFA, s: str) -> bool:
    state = dfa.start
    for ch in s:
        if ch not in dfa.transitions[state]:
            return False  # symbol outside alphabet -> reject
        state = dfa.transitions[state][ch]
    return state in dfa.accepts


def enumerate_strings(dfa: DFA, max_len: int, limit: int = 50, accepting_only: bool = True):
    """BFS enumeration of strings up to max_len; used to sample valid/invalid
    strings for MCQ construction (see mcq_search.py Algorithm-5 analogue)."""
    from collections import deque
    results = []
    queue = deque([(dfa.start, "")])
    while queue and len(results) < limit:
        state, prefix = queue.popleft()
        if len(prefix) > max_len:
            continue
        is_acc = state in dfa.accepts
        if is_acc == accepting_only and prefix != "":
            results.append(prefix)
        elif is_acc == accepting_only and prefix == "" and accepting_only:
            results.append(prefix)
        if len(prefix) < max_len:
            for sym in sorted(dfa.alphabet):
                queue.append((dfa.transitions[state][sym], prefix + sym))
    return results