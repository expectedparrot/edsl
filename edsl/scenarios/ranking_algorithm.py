from collections import defaultdict, deque
from typing import Sequence

from .scenario_list import ScenarioList
from .scenario import Scenario


class PairwiseRanker:
    """
    A class for ranking elements based on pairwise comparisons using MWFAS algorithm.
    """

    def __init__(self, pairwise_comparisons):
        """
        Initialize the ranker with pairwise comparisons.

        Args:
            pairwise_comparisons: List of tuples (u, v, weight) where u beats v with given weight
        """
        self.pairwise_comparisons = pairwise_comparisons
        self.adj_list = None
        self.edge_weights = None
        self.vertices = None
        self._create_graph()

    def _create_graph(self):
        """Create graph from list of tuples (u, v, w)."""
        self.adj_list = defaultdict(list)
        self.edge_weights = {}
        self.vertices = set()

        for u, v, w in self.pairwise_comparisons:
            self.adj_list[u].append(v)
            self.edge_weights[(u, v)] = w
            self.vertices.add(u)
            self.vertices.add(v)

    def _find_cycle_dfs(self, adj_list, vertices):
        """Find a cycle using DFS. Returns the cycle as a list of vertices."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {v: WHITE for v in vertices}

        def dfs(v, path):
            color[v] = GRAY
            path.append(v)

            for u in adj_list.get(v, []):
                if color[u] == GRAY:  # Back edge found
                    # Found cycle - extract it from path
                    cycle_start = path.index(u)
                    return path[cycle_start:] + [u]
                elif color[u] == WHITE:
                    result = dfs(u, path)
                    if result:
                        return result

            path.pop()
            color[v] = BLACK
            return None

        for v in vertices:
            if color[v] == WHITE:
                result = dfs(v, [])
                if result:
                    return result

        return []

    def _find_mwfas(self, adj_list, edge_weights, vertices):
        """Find Minimum Weighted Feedback Arc Set."""
        removed_edges = []
        current_adj = defaultdict(list)
        current_weights = edge_weights.copy()

        # Copy adjacency list
        for u in adj_list:
            current_adj[u] = adj_list[u][:]

        # Phase 1: Remove cycles
        while True:
            cycle = self._find_cycle_dfs(current_adj, vertices)
            if not cycle:
                break

            # Find edges in the cycle
            cycle_edges = []
            for i in range(len(cycle)):
                u = cycle[i]
                v = cycle[(i + 1) % len(cycle)]
                if v in current_adj.get(u, []):
                    cycle_edges.append((u, v))

            if not cycle_edges:
                break

            # Find minimum weight in cycle
            min_weight = min(current_weights.get(edge, float('inf')) for edge in cycle_edges)

            # Reduce weights and remove zero-weight edges
            for edge in cycle_edges:
                current_weights[edge] -= min_weight
                if current_weights[edge] <= 1e-9:  # Consider as zero
                    u, v = edge
                    current_adj[u].remove(v)
                    removed_edges.append((edge, current_weights[edge] + min_weight))

        # Phase 2: Try to re-add edges
        removed_edges.sort(key=lambda x: x[1], reverse=True)

        for (u, v), weight in removed_edges:
            # Check if adding edge creates cycle
            current_adj[u].append(v)
            if self._find_cycle_dfs(current_adj, vertices):
                current_adj[u].remove(v)
            else:
                # Keep the edge
                current_weights[(u, v)] = weight

        return current_adj, current_weights

    def _topological_sort(self, adj_list, vertices):
        """Perform topological sort and return vertex rankings."""
        # Calculate in-degrees
        in_degree = {v: 0 for v in vertices}
        for u in adj_list:
            for v in adj_list[u]:
                in_degree[v] += 1

        # Initialize queue with vertices having 0 in-degree
        queue = deque([v for v in vertices if in_degree[v] == 0])
        topo_order = []

        while queue:
            u = queue.popleft()
            topo_order.append(u)

            for v in adj_list.get(u, []):
                in_degree[v] -= 1
                if in_degree[v] == 0:
                    queue.append(v)

        # Assign rankings based on topological order
        rankings = {}
        for i, v in enumerate(topo_order):
            rankings[v] = i + 1

        return rankings, topo_order

    def _break_ties(self, adj_list, edge_weights, vertices, rankings):
        """Break ties using the score: (sum_out - sum_in) / total_edges."""
        tied_groups = defaultdict(list)
        for v, rank in rankings.items():
            tied_groups[rank].append(v)

        final_rankings = {}
        current_rank = 1

        for rank in sorted(tied_groups.keys()):
            if len(tied_groups[rank]) == 1:
                final_rankings[tied_groups[rank][0]] = current_rank
                current_rank += 1
            else:
                # Calculate scores for tied vertices
                scores = []
                for v in tied_groups[rank]:
                    out_sum = sum(edge_weights.get((v, u), 0) for u in adj_list.get(v, []))
                    in_sum = sum(edge_weights.get((u, v), 0) for u in vertices
                               if v in adj_list.get(u, []))
                    total_edges = len(adj_list.get(v, [])) + \
                                sum(1 for u in vertices if v in adj_list.get(u, []))

                    score = (out_sum - in_sum) / total_edges if total_edges > 0 else 0
                    scores.append((score, v))

                # Sort by score (higher is better)
                scores.sort(reverse=True)

                for _, v in scores:
                    final_rankings[v] = current_rank
                    current_rank += 1

        return final_rankings

    def generate_ranking(self):
        """
        Generate rankings based on pairwise comparisons.

        Returns:
            Dictionary containing rankings, topological order, removed edges, and total removed weight
        """
        # Step 1: Find MWFAS
        dag_adj, dag_weights = self._find_mwfas(self.adj_list, self.edge_weights, self.vertices)

        # Step 2: Compute vertex rankings
        rankings, topo_order = self._topological_sort(dag_adj, self.vertices)

        # Step 3: Break ties
        final_rankings = self._break_ties(dag_adj, dag_weights, self.vertices, rankings)

        # Calculate removed edges info
        removed_edges = []
        removed_weight = 0
        for (u, v), w in self.edge_weights.items():
            if v not in dag_adj.get(u, []):
                removed_edges.append((u, v, w))
                removed_weight += w

        return {
            'rankings': final_rankings,
            'topological_order': topo_order,
            'removed_edges': removed_edges,
            'removed_weight': removed_weight
        }


def results_to_ranked_scenario_list(
    scenario_list: "ScenarioList",
    option_fields: Sequence[str],
    answer_field: str,
    include_rank: bool = True,
    rank_field: str = "rank",
    item_field: str = "item",
) -> "ScenarioList":
    """
    Convert pairwise comparison rows into a ranked `ScenarioList`.

    The caller explicitly provides the option fields (two or more `scenario.*` columns)
    and the single `answer.*` column. For each row, the value in `answer_field` is
    assumed to equal exactly one of the option field values; that option is treated
    as the winner versus all other options in the row.

    Args:
        scenario_list: The data containing `scenario.*` and `answer.*` columns.
        option_fields: List/sequence of `scenario.*` column names (length >= 2).
        answer_field: Name of the `answer.*` column containing the chosen option's value.
        include_rank: If True, include a rank field on each returned `Scenario`.
        rank_field: Name of the rank field to include when `include_rank` is True.
        item_field: Field name used to store the ranked item value on each `Scenario`.

    Returns:
        ScenarioList ordered best-to-worst according to pairwise ranking.
    """
    if not option_fields or len(option_fields) < 2:
        raise ValueError("option_fields must include at least two scenario columns")

    # Convert to row dicts with original prefixes so we can reference provided field names
    rows = scenario_list.to_dicts(remove_prefix=False)

    # Validate provided fields exist
    first_row_keys = set(rows[0].keys()) if rows else set()
    missing_options = [f for f in option_fields if f not in first_row_keys]
    if missing_options:
        raise ValueError(f"Missing option fields in data: {missing_options}")
    if answer_field not in first_row_keys:
        raise ValueError(f"Missing answer field in data: {answer_field}")

    # Aggregate pairwise wins as weighted edges
    edge_counts = {}
    all_items = set()

    for row in rows:
        option_values = [row.get(field) for field in option_fields]
        if any(value is None for value in option_values):
            continue

        answer_value = row.get(answer_field)
        if answer_value is None:
            continue

        winner_indices = [idx for idx, value in enumerate(option_values) if value == answer_value]
        if len(winner_indices) != 1:
            # Skip rows where the answer does not uniquely match one option
            continue

        winner_value = option_values[winner_indices[0]]
        for idx, value in enumerate(option_values):
            if idx == winner_indices[0]:
                continue
            all_items.add(value)
            all_items.add(winner_value)
            edge = (winner_value, value)
            edge_counts[edge] = edge_counts.get(edge, 0.0) + 1.0

    pairwise = [(u, v, w) for (u, v), w in edge_counts.items()]
    if not pairwise and all_items:
        # No informative edges; return items with deterministic ordering and ranks
        sorted_items = sorted(all_items, key=lambda x: str(x))
        scenarios = []
        for idx, item in enumerate(sorted_items, start=1):
            if include_rank:
                scenarios.append(Scenario({item_field: item, rank_field: idx}))
            else:
                scenarios.append(Scenario({item_field: item}))
        return ScenarioList(scenarios)

    ranker = PairwiseRanker(pairwise)
    ranking_result = ranker.generate_ranking()
    rankings = ranking_result['rankings']

    # Sort items by increasing rank (1 is best)
    sorted_items = sorted(rankings.keys(), key=lambda x: rankings[x])
    scenarios = []
    for item in sorted_items:
        rank_value = rankings[item]
        if include_rank:
            scenarios.append(Scenario({item_field: item, rank_field: rank_value}))
        else:
            scenarios.append(Scenario({item_field: item}))
    return ScenarioList(scenarios)

# Example usage
if __name__ == "__main__":
    # Example 1: Simple cycle
    comparisons = [
        (1, 2, 3.0),  # 1 beats 2 with weight 3.0
        (2, 3, 2.0),  # 2 beats 3 with weight 2.0
        (3, 1, 1.0),  # 3 beats 1 with weight 1.0 (creates cycle)
        (1, 4, 4.0),  # 1 beats 4 with weight 4.0
        (3, 4, 2.5),  # 3 beats 4 with weight 2.5
    ]

    ranker = PairwiseRanker(comparisons)
    result = ranker.generate_ranking()

    print("Rankings:")
    for vertex, rank in sorted(result['rankings'].items(), key=lambda x: x[1]):
        print(f"  Element {vertex}: Rank {rank}")

    print(f"\nTopological Order: {result['topological_order']}")
    print(f"\nRemoved Edges: {result['removed_edges']}")
    print(f"Total Removed Weight: {result['removed_weight']:.2f}")

    # Example 2: Tournament results
    print("\n" + "="*50 + "\n")
    print("Example 2: Tournament Rankings")

    # A beats B strongly, B beats C moderately, C beats A weakly
    # A also beats D, B beats D weakly
    tournament = [
        ('A', 'B', 5.0),
        ('B', 'C', 3.0),
        ('C', 'A', 1.0),
        ('A', 'D', 4.0),
        ('B', 'D', 1.5),
    ]

    tournament_ranker = PairwiseRanker(tournament)
    result2 = tournament_ranker.generate_ranking()

    print("\nTournament Rankings:")
    for player, rank in sorted(result2['rankings'].items(), key=lambda x: x[1]):
        print(f"  Player {player}: Rank {rank}")