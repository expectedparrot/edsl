"""
KL Divergence computation for comparing distributions in ScenarioLists.

This module provides utilities for computing Kullback-Leibler (KL) divergence
between distributions defined by groups in a ScenarioList.
"""

from __future__ import annotations
from typing import Optional, Union, Dict, Any, TYPE_CHECKING
from collections import Counter

if TYPE_CHECKING:
    import numpy as np


class KLDivergenceCalculator:
    """
    Calculate KL divergence between distributions in a ScenarioList.

    The KL divergence KL(P||Q) measures how much the distribution P diverges
    from the distribution Q. It's asymmetric: KL(P||Q) ≠ KL(Q||P).

    Parameters
    ----------
    scenario_list : ScenarioList
        The scenario list containing grouped data
    group_field : str
        Field that defines the groups (e.g., 'condition', 'persona')
    value_field : str
        Field containing values to compare distributions of
    bins : int or str, optional
        For continuous data: number of bins or 'auto' (default: None = categorical)
    base : float, optional
        Logarithm base for KL divergence (default: 2 for bits, use e for nats)
    laplace_smooth : float, optional
        Small value to add to avoid log(0) (default: 1e-10)
    """

    def __init__(
        self,
        scenario_list,
        group_field: str,
        value_field: str,
        bins: Optional[Union[int, str]] = None,
        base: float = 2.0,
        laplace_smooth: float = 1e-10,
    ):
        self.scenario_list = scenario_list
        self.group_field = group_field
        self.value_field = value_field
        self.bins = bins
        self.base = base
        self.laplace_smooth = laplace_smooth

        # Extract and organize data
        self.distributions = self._extract_distributions()

    def _extract_distributions(self) -> Dict[Any, Dict[Any, float]]:
        """
        Extract distributions for each group.

        Returns
        -------
        Dict[group_name, Dict[value, probability]]
            Probability distributions for each group
        """
        # Group data by group_field
        grouped_data = {}
        for scenario in self.scenario_list:
            group = scenario.get(self.group_field)
            value = scenario.get(self.value_field)

            if group is None or value is None:
                continue

            if group not in grouped_data:
                grouped_data[group] = []
            grouped_data[group].append(value)

        # Convert to probability distributions
        distributions = {}

        # Check if we need binning (continuous data)
        if self.bins is not None:
            distributions = self._bin_continuous_data(grouped_data)
        else:
            distributions = self._categorical_distributions(grouped_data)

        return distributions

    def _categorical_distributions(
        self, grouped_data: Dict[Any, list]
    ) -> Dict[Any, Dict[Any, float]]:
        """Convert categorical data to probability distributions."""
        distributions = {}

        for group, values in grouped_data.items():
            # Count occurrences
            counts = Counter(values)
            total = sum(counts.values())

            # Convert to probabilities
            distributions[group] = {
                value: (count / total) for value, count in counts.items()
            }

        return distributions

    def _bin_continuous_data(
        self, grouped_data: Dict[Any, list]
    ) -> Dict[Any, Dict[Any, float]]:
        """Bin continuous data and create probability distributions."""
        import numpy as np

        distributions = {}

        # Determine bins across all data
        all_values = []
        for values in grouped_data.values():
            all_values.extend(values)

        if self.bins == "auto":
            # Use Sturges' formula
            n_bins = int(np.ceil(np.log2(len(all_values)) + 1))
        else:
            n_bins = self.bins

        # Create bins
        bin_edges = np.histogram_bin_edges(all_values, bins=n_bins)

        # Bin each group's data
        for group, values in grouped_data.items():
            hist, _ = np.histogram(values, bins=bin_edges)
            total = sum(hist)

            # Convert to probabilities, using bin indices as keys
            distributions[group] = {
                i: (count / total) if total > 0 else 0 for i, count in enumerate(hist)
            }

        return distributions

    def kl_divergence(self, from_group: Any, to_group: Any) -> float:
        """
        Compute KL divergence KL(P||Q) where P=from_group and Q=to_group.

        Parameters
        ----------
        from_group : Any
            The reference distribution (P)
        to_group : Any
            The comparison distribution (Q)

        Returns
        -------
        float
            KL divergence in bits (if base=2) or nats (if base=e)

        Notes
        -----
        KL(P||Q) = Σ P(x) * log(P(x) / Q(x))
        """
        if from_group not in self.distributions:
            raise ValueError(f"Group '{from_group}' not found in {self.group_field}")
        if to_group not in self.distributions:
            raise ValueError(f"Group '{to_group}' not found in {self.group_field}")

        p_dist = self.distributions[from_group]
        q_dist = self.distributions[to_group]

        # Get all possible values
        all_values = set(p_dist.keys()) | set(q_dist.keys())

        import numpy as np

        kl = 0.0
        for value in all_values:
            p = p_dist.get(value, 0) + self.laplace_smooth
            q = q_dist.get(value, 0) + self.laplace_smooth

            # Only add to KL if p > 0 (otherwise p * log(p/q) = 0)
            if p > self.laplace_smooth:
                kl += p * np.log(p / q) / np.log(self.base)

        return float(kl)

    def pairwise_kl_divergences(self) -> Dict[str, float]:
        """
        Compute KL divergence for all pairs of groups.

        Returns
        -------
        Dict[str, float]
            Dictionary with keys like "group1→group2" and KL divergence values
        """
        groups = list(self.distributions.keys())
        results = {}

        for i, from_group in enumerate(groups):
            for to_group in groups:
                if from_group != to_group:
                    key = f"{from_group}→{to_group}"
                    results[key] = self.kl_divergence(from_group, to_group)

        return results

    def symmetric_kl_divergence(self, group1: Any, group2: Any) -> tuple[float, float]:
        """
        Compute both directions of KL divergence.

        Returns
        -------
        tuple[float, float]
            (KL(P||Q), KL(Q||P))
        """
        kl_pq = self.kl_divergence(group1, group2)
        kl_qp = self.kl_divergence(group2, group1)
        return kl_pq, kl_qp


def kl_divergence(
    scenario_list,
    group_field: str,
    value_field: str,
    from_group: Optional[Any] = None,
    to_group: Optional[Any] = None,
    bins: Optional[Union[int, str]] = None,
    base: float = 2.0,
    laplace_smooth: float = 1e-10,
) -> Union[float, Dict[str, float]]:
    """
    Compute KL divergence between distributions in a ScenarioList.

    Parameters
    ----------
    scenario_list : ScenarioList
        The scenario list containing grouped data
    group_field : str
        Field that defines the groups (e.g., 'condition', 'persona')
    value_field : str
        Field containing values to compare distributions of
    from_group : Any, optional
        The reference group (P in KL(P||Q)). If None, compute all pairs.
    to_group : Any, optional
        The comparison group (Q in KL(P||Q)). Required if from_group is specified.
    bins : int or str, optional
        For continuous data: number of bins or 'auto' (default: None = categorical)
    base : float, optional
        Logarithm base (default: 2 for bits, use e for nats)
    laplace_smooth : float, optional
        Small value to avoid log(0) (default: 1e-10)

    Returns
    -------
    float or Dict[str, float]
        If from_group and to_group specified: single KL divergence value
        If not specified: dictionary of all pairwise KL divergences

    Examples
    --------
    >>> from edsl.scenarios import Scenario, ScenarioList
    >>> sl = ScenarioList([
    ...     Scenario({'condition': 'A', 'response': 'yes'}),
    ...     Scenario({'condition': 'A', 'response': 'yes'}),
    ...     Scenario({'condition': 'B', 'response': 'no'}),
    ... ])
    >>> kl = kl_divergence(sl, 'condition', 'response', 'A', 'B')  # doctest: +SKIP
    >>> isinstance(kl, float)  # doctest: +SKIP
    True

    Notes
    -----
    KL divergence is asymmetric: KL(P||Q) ≠ KL(Q||P)
    - KL(P||Q) measures how much P diverges from Q
    - Use base=2 for bits, base=e for nats
    - Laplace smoothing prevents log(0) errors
    """
    calc = KLDivergenceCalculator(
        scenario_list, group_field, value_field, bins, base, laplace_smooth
    )

    if from_group is not None and to_group is not None:
        return calc.kl_divergence(from_group, to_group)
    elif from_group is not None or to_group is not None:
        raise ValueError("Both from_group and to_group must be specified together")
    else:
        return calc.pairwise_kl_divergences()
