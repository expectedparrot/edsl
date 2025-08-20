"""Sampling and shuffling functionality for Results objects."""

import random
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .results import Results

from .exceptions import ResultsError


class ResultsSampler:
    """Handles random sampling and shuffling operations for Results objects.

    This class encapsulates all randomization functionality including:
    - Shuffling results using Fisher-Yates algorithm
    - Random sampling with or without replacement
    - Legacy sampling for backward compatibility

    The class maintains the same interface as the original Results methods
    but provides better separation of concerns for random operations.
    """

    def __init__(self, results: "Results"):
        """Initialize the sampler with a Results object.

        Args:
            results: The Results object to perform sampling operations on
        """
        self.results = results

    def shuffle(self, seed: Optional[str] = "edsl") -> "Results":
        """Return a shuffled copy of the results using Fisher-Yates algorithm.

        Args:
            seed: Random seed for reproducibility.

        Returns:
            Results: A new Results object with shuffled data.
        """
        if seed != "edsl":
            random.seed(seed)

        # Import here to avoid circular imports
        from .results import Results

        # Create new Results object with same properties but empty data
        shuffled_results = Results(
            survey=self.results.survey,
            data=[],
            created_columns=self.results.created_columns,
            data_class=self.results._data_class,
        )

        # First pass: copy data while tracking indices
        indices = list(range(len(self.results.data)))

        # Second pass: Fisher-Yates shuffle on indices
        for i in range(len(indices) - 1, 0, -1):
            j = random.randrange(i + 1)
            indices[i], indices[j] = indices[j], indices[i]

        # Final pass: append items in shuffled order
        for idx in indices:
            shuffled_results.append(self.results.data[idx])

        return shuffled_results

    def sample(
        self,
        n: Optional[int] = None,
        frac: Optional[float] = None,
        with_replacement: bool = True,
        seed: Optional[str] = None,
    ) -> "Results":
        """Return a random sample of the results.

        Args:
            n: The number of samples to take.
            frac: The fraction of samples to take (alternative to n).
            with_replacement: Whether to sample with replacement.
            seed: Random seed for reproducibility.

        Returns:
            Results: A new Results object containing the sampled data.
        """
        if seed:
            random.seed(seed)

        if n is None and frac is None:
            raise ResultsError("You must specify either n or frac.")

        if n is not None and frac is not None:
            raise ResultsError("You cannot specify both n and frac.")

        if frac is not None:
            n = int(frac * len(self.results.data))

        # At this point, n should not be None
        assert n is not None, "n should be set by now"

        # Import here to avoid circular imports
        from .results import Results

        # Create new Results object with same properties but empty data
        sampled_results = Results(
            survey=self.results.survey,
            data=[],
            created_columns=self.results.created_columns,
            data_class=self.results._data_class,
        )

        if with_replacement:
            # For sampling with replacement, we can generate indices and sample one at a time
            indices = (random.randrange(len(self.results.data)) for _ in range(n))
            for i in indices:
                sampled_results.append(self.results.data[i])
        else:
            # For sampling without replacement, use reservoir sampling
            if n > len(self.results.data):
                raise ResultsError(
                    f"Cannot sample {n} items from a list of length {len(self.results.data)}."
                )

            # Reservoir sampling algorithm
            for i, item in enumerate(self.results.data):
                if i < n:
                    # Fill the reservoir initially
                    sampled_results.append(item)
                else:
                    # Randomly replace items with decreasing probability
                    j = random.randrange(i + 1)
                    if j < n:
                        sampled_results.data[j] = item

        return sampled_results

    def sample_legacy(self, n: int) -> "Results":
        """Return a random sample of the results using legacy algorithm.

        This method is kept for backward compatibility but now delegates to the
        main sample() method since the original legacy algorithm is incompatible
        with the current Results data structure. Use sample() instead.

        Args:
            n: The number of samples to return.

        Returns:
            Results: A new Results object with sampled data.

        Examples:
            >>> from edsl.results import Results
            >>> from edsl.results.results_sampler import ResultsSampler
            >>> r = Results.example()
            >>> sampler = ResultsSampler(r)
            >>> len(sampler.sample_legacy(2))
            2
        """
        # The original legacy algorithm was designed for a different data structure
        # and is no longer compatible. Delegate to the main sample method instead.
        return self.sample(n=n, with_replacement=False)
