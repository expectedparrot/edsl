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

        # First pass: copy data while tracking indices
        indices = list(range(len(self.results.data)))

        # Second pass: Fisher-Yates shuffle on indices
        for i in range(len(indices) - 1, 0, -1):
            j = random.randrange(i + 1)
            indices[i], indices[j] = indices[j], indices[i]

        # Collect items in shuffled order (Results is immutable, create with full data)
        shuffled_data = [self.results.data[idx] for idx in indices]

        # Create new Results object with shuffled data
        return Results(
            survey=self.results.survey,
            data=shuffled_data,
            created_columns=self.results.created_columns,
            data_class=self.results._data_class,
        )

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

        # Import here to avoid circular imports
        from .results import Results

        if with_replacement:
            # For sampling with replacement, generate indices and collect items
            indices = [random.randrange(len(self.results.data)) for _ in range(n)]
            sampled_data = [self.results.data[i] for i in indices]
        else:
            # For sampling without replacement
            if n > len(self.results.data):
                raise ResultsError(
                    f"Cannot sample {n} items from a list of length {len(self.results.data)}."
                )

            # Use random.sample for simple random sampling without replacement
            sampled_data = random.sample(list(self.results.data), n)

        # Create new Results object with sampled data (Results is immutable)
        return Results(
            survey=self.results.survey,
            data=sampled_data,
            created_columns=self.results.created_columns,
            data_class=self.results._data_class,
        )

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
