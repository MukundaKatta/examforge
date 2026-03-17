"""Bloom's Taxonomy classification for exam questions."""

from __future__ import annotations

import re

from examforge.models import BloomLevel, Question

# Verb banks aligned with each cognitive level of Bloom's revised taxonomy.
BLOOM_VERB_MAP: dict[BloomLevel, set[str]] = {
    BloomLevel.REMEMBER: {
        "define", "list", "name", "identify", "recall", "recognise", "recognize",
        "state", "label", "match", "memorize", "repeat", "describe", "select",
        "reproduce", "outline", "enumerate",
    },
    BloomLevel.UNDERSTAND: {
        "explain", "summarize", "summarise", "paraphrase", "classify", "compare",
        "contrast", "interpret", "discuss", "distinguish", "illustrate", "infer",
        "restate", "translate", "exemplify", "predict",
    },
    BloomLevel.APPLY: {
        "apply", "demonstrate", "solve", "use", "calculate", "execute", "implement",
        "compute", "modify", "operate", "practice", "show", "sketch", "experiment",
    },
    BloomLevel.ANALYZE: {
        "analyze", "analyse", "differentiate", "examine", "inspect", "deconstruct",
        "categorize", "categorise", "correlate", "deduce", "diagnose", "investigate",
        "organize", "organise", "relate", "separate", "dissect",
    },
    BloomLevel.EVALUATE: {
        "evaluate", "assess", "judge", "justify", "critique", "defend", "argue",
        "appraise", "prioritize", "prioritise", "rank", "rate", "support",
        "validate", "recommend", "weigh",
    },
    BloomLevel.CREATE: {
        "create", "design", "construct", "develop", "formulate", "compose",
        "generate", "invent", "plan", "produce", "propose", "synthesize",
        "synthesise", "assemble", "devise", "build", "author",
    },
}

# Precompute a flat verb -> level lookup for fast matching.
_VERB_TO_LEVEL: dict[str, BloomLevel] = {}
# Higher levels overwrite lower ones on collision, so iterate low-to-high.
for _level in BloomLevel:
    for _verb in BLOOM_VERB_MAP[_level]:
        _VERB_TO_LEVEL[_verb] = _level


class BloomTaxonomy:
    """Classify questions by Bloom's taxonomy cognitive level.

    Classification is based on action-verb analysis of the question text.
    When multiple verbs match, the highest cognitive level wins.
    """

    @staticmethod
    def classify(question: Question | str) -> BloomLevel:
        """Determine the Bloom's taxonomy level of a question.

        Args:
            question: A Question object or raw question string.

        Returns:
            The detected BloomLevel; defaults to REMEMBER if no verbs match.
        """
        text = question.text if isinstance(question, Question) else question
        words = set(re.findall(r"[a-z]+", text.lower()))

        best_level = BloomLevel.REMEMBER
        best_rank = 0

        level_order = list(BloomLevel)
        for word in words:
            level = _VERB_TO_LEVEL.get(word)
            if level is not None:
                rank = level_order.index(level)
                if rank > best_rank:
                    best_rank = rank
                    best_level = level

        return best_level

    @staticmethod
    def classify_and_tag(question: Question) -> Question:
        """Classify and mutate the question's bloom_level in place, then return it."""
        question.bloom_level = BloomTaxonomy.classify(question)
        return question

    @staticmethod
    def get_verbs(level: BloomLevel) -> set[str]:
        """Return the verb bank for a given Bloom's level."""
        return BLOOM_VERB_MAP.get(level, set())

    @staticmethod
    def all_levels() -> list[BloomLevel]:
        """Return all Bloom's levels in ascending cognitive order."""
        return list(BloomLevel)
