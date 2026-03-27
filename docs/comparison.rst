.. _comparison:

Comparing Results
=================

The ``edsl.results.comparison`` module lets you compare survey results across agents, models, or scenarios.
It provides three levels of comparison:

1. **Result pair comparison** -- compare two individual ``Result`` objects question by question
2. **Gold standard comparison** -- compare a set of candidate results against known-good "gold" results
3. **Distribution comparison** -- compare answer distributions across populations using statistical distance metrics


Comparing Two Results
---------------------

Use ``ResultPairComparison`` to compare two ``Result`` objects across all shared questions:

.. code-block:: python

   from edsl.results.comparison import ResultPairComparison

   # Suppose `results` is a Results object from running a survey
   rpc = ResultPairComparison(results[0], results[1])

   # See which questions were compared
   rpc.comparisons.keys()
   # => dict_keys(['how_feeling', 'how_feeling_yesterday'])

   # Inspect a single question's comparison
   rpc.comparisons['how_feeling']
   # => {
   #     'metrics': {'exact_match': False, 'overlap': None, 'jaccard_similarity': None},
   #     'answer_a': 'OK',
   #     'answer_b': 'Great',
   #     'question_text': 'How are you?',
   #     'question_type': 'multiple_choice',
   # }

The default metrics are ``exact_match``, ``overlap``, and ``jaccard_similarity``.
Overlap and jaccard return ``None`` for non-iterable answers (like strings), since they
operate on sets.


Converting to a ScenarioList
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For downstream analysis you can flatten the comparisons into a ``ScenarioList`` with
one row per question-metric pair:

.. code-block:: python

   sl = rpc.to_scenario_list()
   # Each scenario has: question_name, answer_a, answer_b, metric_name, metric_value


Serialization
~~~~~~~~~~~~~

``ResultPairComparison`` supports round-trip serialization:

.. code-block:: python

   d = rpc.to_dict()
   rpc2 = ResultPairComparison.from_dict(d)


Metrics
-------

Built-in Metrics
~~~~~~~~~~~~~~~~

Every metric is a plain function with signature ``(a, b) -> float | bool | None``:

.. code-block:: python

   from edsl.results.comparison import exact_match, overlap, jaccard_similarity

   exact_match("yes", "yes")          # => True
   exact_match("yes", "no")           # => False

   overlap(["a", "b", "c"], ["b", "c", "d"])     # => 0.667
   jaccard_similarity(["a", "b", "c"], ["b", "c", "d"])  # => 0.5

   # Non-iterable inputs return None for overlap/jaccard
   overlap("hello", "world")          # => None

- **exact_match(a, b)** -- ``True`` if ``a == b``
- **overlap(a, b)** -- ``|intersection| / min(|a|, |b|)`` for iterables; ``None`` otherwise
- **jaccard_similarity(a, b)** -- ``|intersection| / |union|`` for iterables; ``None`` otherwise


Custom Metrics
~~~~~~~~~~~~~~

Add any function with the right signature:

.. code-block:: python

   from edsl.results.comparison import MetricsCollection

   def case_insensitive_match(a, b):
       if isinstance(a, str) and isinstance(b, str):
           return a.lower() == b.lower()
       return a == b

   mc = MetricsCollection({
       "exact_match": exact_match,
       "case_insensitive": case_insensitive_match,
   })

   rpc = ResultPairComparison(results[0], results[1], metrics_collection=mc)


Cosine Similarity with Embeddings
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The module provides three ways to add cosine similarity, depending on your embedding provider.

**Generic: bring your own embedding function**

The core building block is ``cosine_metric_from_embed_fn``. Pass any function that takes a
string and returns a vector (list or numpy array):

.. code-block:: python

   from edsl.results.comparison import cosine_metric_from_embed_fn, MetricsCollection
   from edsl.results.comparison.metrics import default_metrics

   def my_embed(text: str) -> list[float]:
       # your embedding logic here
       ...

   metrics = default_metrics()
   metrics["cosine"] = cosine_metric_from_embed_fn(my_embed)
   mc = MetricsCollection(metrics)

**OpenAI embeddings**

.. code-block:: python

   from edsl.results.comparison import make_openai_cosine_metric
   from edsl.results.comparison.metrics import default_metrics

   metrics = default_metrics()
   metrics["cosine"] = make_openai_cosine_metric()  # uses text-embedding-3-small

   # Or specify a different model
   metrics["cosine"] = make_openai_cosine_metric("text-embedding-3-large")

   # Or pass your own client
   from openai import OpenAI
   client = OpenAI(api_key="sk-...")
   metrics["cosine"] = make_openai_cosine_metric(client=client)

The OpenAI client is created lazily on first use, so no API call is made until
you actually compare two answers. Requires the ``openai`` package.

**Sentence-transformers (local)**

.. code-block:: python

   from edsl.results.comparison import make_cosine_metric
   from edsl.results.comparison.metrics import default_metrics

   metrics = default_metrics()
   metrics["cosine"] = make_cosine_metric()  # uses all-MiniLM-L6-v2

   # Or specify a different model
   metrics["cosine"] = make_cosine_metric("all-mpnet-base-v2")

The model is loaded lazily on first use. Requires the ``sentence-transformers`` package.

**Using cosine metrics in a comparison**

Once you have a metrics dict with cosine similarity added, pass it as a ``MetricsCollection``:

.. code-block:: python

   from edsl.results.comparison import ResultPairComparison, MetricsCollection
   from edsl.results.comparison.metrics import default_metrics
   from edsl.results.comparison import make_openai_cosine_metric

   metrics = default_metrics()
   metrics["cosine"] = make_openai_cosine_metric()
   mc = MetricsCollection(metrics)

   rpc = ResultPairComparison(results[0], results[1], metrics_collection=mc)
   rpc.comparisons['how_feeling']['metrics']['cosine']
   # => 0.923  (for example)


Weighted Scoring
----------------

Use ``weighted_score`` to reduce a comparison to a single number in [0, 1]:

.. code-block:: python

   from edsl.results.comparison import weighted_score

   # Equal weights on all metrics and questions (the default)
   score = weighted_score(rpc.comparisons)

   # Weight exact_match more heavily
   score = weighted_score(
       rpc.comparisons,
       metric_weights={"exact_match": 3.0, "overlap": 1.0, "jaccard_similarity": 1.0},
   )

   # Weight specific questions more heavily
   score = weighted_score(
       rpc.comparisons,
       question_weights={"how_feeling": 2.0, "how_feeling_yesterday": 1.0},
   )

Weights are normalised internally, so they don't need to sum to 1. ``None`` metric
values (e.g., overlap on a string answer) are skipped. Boolean metrics are converted
to 1.0/0.0.


Comparing Against a Gold Standard
----------------------------------

``CompareResultsToGold`` compares a set of candidate results against known-good
"gold" results, matching by agent base name:

.. code-block:: python

   from edsl.results.comparison import CompareResultsToGold

   comparison = CompareResultsToGold(candidate_results, gold_results)

   # Dict-like: maps base agent name -> {full_agent_name: ResultPairComparison}
   for base_agent, agent_comparisons in comparison.items():
       for full_name, rpc in agent_comparisons.items():
           print(f"{full_name}: {weighted_score(rpc.comparisons)}")

Agents are matched by ``agent.base_name``. A ``ValueError`` is raised if a candidate
agent has no corresponding gold agent.

Serialization works the same way:

.. code-block:: python

   d = comparison.to_dict()
   comparison2 = CompareResultsToGold.from_dict(d)


Comparing Answer Distributions
-------------------------------

``AnswersCompare`` compares the *distribution* of answers to a question across two
populations, using statistical distance metrics:

.. code-block:: python

   from edsl.results.comparison import AnswersCompare

   # qa1, qa2 are QuestionAnalysis objects from results.analyze('question_name')
   compare = AnswersCompare(qa1, qa2)

   compare.jensen_shannon_divergence()   # symmetric, bounded [0, ln(2)]
   compare.hellinger_distance()          # bounded [0, 1]
   compare.total_variation_distance()    # bounded [0, 1]
   compare.kl_divergence()              # asymmetric D_KL(P||Q)
   compare.kl_divergence(reverse=True)  # D_KL(Q||P)
   compare.chi_squared()                # unbounded
   compare.bhattacharyya_distance()     # unbounded

   # All at once
   compare.all_metrics()
   # => {'kl_divergence': 0.23, 'kl_divergence_reverse': 0.19, ...}

   # Custom distance function
   compare.custom_metric(lambda p, q: sum(abs(p[k] - q[k]) for k in p))


API Reference
-------------

**Classes**

- ``ResultPairComparison(result_a, result_b, metrics_collection=None)``
- ``CompareResultsToGold(candidate_results, gold_results, metrics_collection=None)``
- ``MetricsCollection(metrics=None)``
- ``AnswersCompare(qa1, qa2)``

**Metric functions**

- ``exact_match(a, b) -> bool``
- ``overlap(a, b) -> float | None``
- ``jaccard_similarity(a, b) -> float | None``

**Cosine similarity factories**

- ``cosine_metric_from_embed_fn(embed_fn) -> Metric`` -- generic, any embedding function
- ``make_cosine_metric(model_name="all-MiniLM-L6-v2") -> Metric`` -- sentence-transformers
- ``make_openai_cosine_metric(model="text-embedding-3-small", client=None) -> Metric`` -- OpenAI

**Scoring**

- ``weighted_score(comparisons, metric_weights=None, question_weights=None) -> float``
