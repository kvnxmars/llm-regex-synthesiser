"""
Part 1 => The Symbolic Baseline (Ade-Ibijola-style CFG regex generator)

A python Context-Free Grammar whose productions are grouped by complexity levels so you one can 
sample tasks level-by-level (10 per level x 5 levels = 50 regex tasks). Each generated task carries 
the regex string, its complexity level, and its AST (Abstract Syntax Tree), so downstream modules 
(mcq_search.py) can enumerate valid/invalid strings without re-parsing.

Time complexity note: Generation itself here is linear in the size of the produced expression; 
the O(n^3) bottleneck cited in Ade-Ibijola (2018) is in the *search* step (Algorithm 5) that finds 
valid/invalid example strings for the Multiple Choice Question, not in the grammar sampling step. 
That search is implemented in mcq_search.py and timed separately in efficiency.py so the two costs aren't conflated in these metrics.

"""

from __future__ import annotations
from dataclasses import dataclass
import random
import string

DEFAULT_ALPHABET = tuple("01abc") # small fixed alphabet to keep DFA tractable

@dataclass #dataclass decorator to automatically generate special methods for the regex task
class RegexTask:
    pattern: str
    level: int
    level_name: str
    alphabet: tuple

LEVEL_NAMES = {
    1: "Literal Matching",
    2: "Character Classes",
    3: "Quantifiers",
    4: "Alternation",
    5: "Nested Expressions",
}

class CFGRegexGenerator:
    """Each `gen_level_k` method is a production rule for complexity level k. Levels build on each other (as in the paper): 
    level 5 mixes constructs from 2-4 with explicit nesting/grouping."""

    def __init__(self, alphabet=DEFAULT_ALPHABET, rng: random.Random = None):
        self.alphabet = tuple(alphabet)
        self.rng = rng or random.Random()

    # Level 1: Literal Matching
    def gen_level_1(self) -> str:
        length = self.rng.randint(2, 5)
        return "".join(self.rng.choice(self.alphabet) for _ in range(length))

    # Level 2: Character Classes
    def gen_level_2(self) -> str:
        choice = self.rng.random()
        if choice < 0.5 and len(self.alphabet) >= 3:
            # looking range over the alphabet's own ordering
            a = self.rng.randint(2, min(3, len(self.alphabet)))
            chars = self.rng.sample(self.alphabet, a)
            return f"[{''.join(sorted(chars))}]"

        # Level 3: Quantifiers
        def gen_level_3(self) -> str:
            base = self.rng.choice(self.alphabet)
            quant = self.rng.choice(["*", "+", "?", "{2,3}", "{2,}"])
            return f"{base}{quant}"

        # Level 4: Alternation
        def gen_level_4(self) -> str:
            a = self.rng.randint(2, 3)
            options = self.rng.sample(self.alphabet, min(a, len(self.alphabet)))
            return "|".join(options)

        # Level 5: Nested Expressions
        def gen_level_5(self, depth: int = 2) -> str:
            def build(d):
                if d == 0:
                    return self.rng.choice(self.alphabet)
                choice = self.rng.random()
                if choice < 0.34:
                    a, b = build(d - 1), build(d - 1)
                    return f"({a}|{b})"
                elif choice < 0.67:
                    inner = build(d - 1)
                    q = self.rng.choice(["*", "+"])
                    return f"({inner}){q}"
                else:
                    a, b = build(d - 1), build(d - 1)
                    return f"({a}{b})"
                return build(depth)

        #generate regex task based on the specified level
        def generate(self, level: int) -> RegexTask:
            gens = {1: self.gen_level_1, 
                    2: self.gen_level_2, 
                    3: self.gen_level_3,
                    4: self.gen_level_4,
                    5: self.gen_level_5
                    }
            if level not in gens:
                raise ValueError(f"Level must be in {list(gens.keys())}, got {level}")
            pattern = gens[level]()
            return RegexTask(pattern=pattern, level=level, Level_name=LEVEL_NAMES[level], alphabet=self.alphabet)

        #generate a batch of regex tasks for eacch level

        """
        This generates the full 50-task dataset , dedouplicated within each level so there aree no repeat tasks. The `per_level` 
        parameter controls how many tasks to generate per level (default 10). The `seed` parameter allows for reproducible random generation.
        """
        def generate_batch(self, per_level: int= 10, seed: int = None) -> list:
            if seed is not None:
                self.rng.seed(seed)
            tasks = []
            for level in range(1, 6):
                seen = set()
                attempts = 0
                while len(seen) < per_level and attempts < per_level * 50:
                    t = self.generate(level)
                    attempts += 1
                    if t.pattern in seen:
                        continue
                    seen.add(t.pattern)
                    tasks.append(t)
                return tasks

if __name__ == "__main__":
    gen = CFGRegexGenerator(seed_alphabet := DEFAULT_ALPHABET, rng=random.Random(42))
    for task in gen.generate_batch(per_level=10):
        print(f"Level {task.level} ({task.level_name}): {task.pattern}")