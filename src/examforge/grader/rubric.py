"""Rubric utilities for structured grading."""

from __future__ import annotations

from examforge.models import RubricCriterion, RubricModel


class Rubric:
    """High-level helper for creating and working with grading rubrics.

    Wraps :class:`RubricModel` with a fluent builder API.
    """

    def __init__(self, name: str = "Custom Rubric") -> None:
        self._name = name
        self._criteria: list[RubricCriterion] = []

    def add_criterion(
        self,
        name: str,
        max_points: float,
        description: str = "",
        levels: dict[str, str] | None = None,
    ) -> Rubric:
        """Add a scoring criterion. Returns self for chaining."""
        self._criteria.append(
            RubricCriterion(
                name=name,
                description=description,
                max_points=max_points,
                levels=levels or {},
            )
        )
        return self

    def build(self) -> RubricModel:
        """Return the finalized :class:`RubricModel`."""
        return RubricModel(name=self._name, criteria=list(self._criteria))

    @property
    def max_total(self) -> float:
        return sum(c.max_points for c in self._criteria)

    @staticmethod
    def from_model(model: RubricModel) -> Rubric:
        """Create a Rubric builder pre-loaded from an existing model."""
        r = Rubric(name=model.name)
        r._criteria = list(model.criteria)
        return r

    def __repr__(self) -> str:
        return f"Rubric(name={self._name!r}, criteria={len(self._criteria)}, max={self.max_total})"
