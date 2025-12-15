"""
Intelligent ScenarioList Agent for multi-source data acquisition.

This module contains the ScenarioAgent class, which acts as an intelligent agent
that tries multiple approaches to create ScenarioList objects from natural language
descriptions. It attempts different data sources in a strategic order:

1. Wikipedia table search - for structured reference data
2. Exa web search - for real-world data from the web
3. AI generation - as a reliable fallback

The agent provides verbose feedback about its search process and can be configured
to enable/disable specific approaches.
"""

from __future__ import annotations
import traceback
from typing import TYPE_CHECKING, List, Optional, Dict, Any

if TYPE_CHECKING:
    from ..scenario_list import ScenarioList
    from ..scenario import Scenario


class ScenarioAgent:
    """
    Intelligent agent for creating ScenarioList objects from multiple sources.

    This agent tries different approaches in sequence to find the best data source
    for a given natural language description. It provides detailed feedback about
    its search process and can be customized to prioritize different approaches.
    """

    def __init__(
        self,
        verbose: bool = True,
        model: str = "gpt-4o-mini",
        temperature: float = 0.1,
    ):
        """
        Initialize the ScenarioAgent with LLM-powered decision making.

        Args:
            verbose: If True, prints progress updates during search
            model: LLM model to use for decision making
            temperature: Temperature for LLM decision calls (low for consistency)
        """
        self.verbose = verbose
        self.model = model
        self.temperature = temperature
        self._client = None

    def _log(self, message: str):
        """Log a message if verbose mode is enabled."""
        if self.verbose:
            print(f"🤖 ScenarioAgent: {message}")

    @property
    def client(self):
        """Get OpenAI client for LLM decision making."""
        if self._client is None:
            from edsl.base.openai_utils import create_openai_client
            self._client = create_openai_client()
        return self._client

    def _decide_search_strategy(self, description: str) -> dict:
        """
        Use LLM to decide the best search strategy for the given description.

        Args:
            description: Natural language description of desired data

        Returns:
            dict: Strategy decision with approach order and reasoning
        """
        system_prompt = """You are an expert at deciding the best data source strategy for different types of queries.

Given a user's request for data, analyze what type of information they're looking for and decide the best approach:

1. **Wikipedia**: Good for well-established reference data, lists, comparisons, historical data, geographic data, etc.
   Examples: "European countries", "Fortune 500 companies", "US presidents", "programming languages"

2. **Exa (Web Search)**: Good for current/recent data, company information, people profiles, emerging topics, news-related data.
   Examples: "AI startups", "current tech leaders", "recent IPOs", "trending topics"

3. **AI Generation**: Good for creative scenarios, hypothetical data, when no existing datasets likely exist.
   Examples: "fictional characters", "hypothetical scenarios", "creative brainstorming topics"

Provide your analysis and recommended order of approaches to try."""

        user_prompt = f"""Query: "{description}"

Analyze this query and decide:
1. What type of data is the user looking for?
2. Which approach is most likely to find good structured data?
3. What should be the order of approaches to try?
4. What specific search terms would work best for Wikipedia?

Respond in this exact JSON format:
{{
    "analysis": "brief analysis of what type of data this is",
    "primary_approach": "wikipedia|exa|ai_generation",
    "approach_order": ["first_approach", "second_approach", "third_approach"],
    "wikipedia_likely": true/false,
    "exa_likely": true/false,
    "ai_generation_likely": true/false,
    "wikipedia_search_terms": ["term1", "term2", "term3"],
    "reasoning": "brief explanation of the recommended strategy"
}}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.temperature,
                response_format={"type": "json_object"}
            )

            import json
            strategy = json.loads(response.choices[0].message.content)
            return strategy

        except Exception as e:
            self._log(f"⚠️  LLM strategy decision failed: {e}, using default strategy")
            # Fallback to default strategy
            return {
                "analysis": "Unable to analyze query",
                "primary_approach": "wikipedia",
                "approach_order": ["wikipedia", "exa", "ai_generation"],
                "wikipedia_likely": True,
                "exa_likely": True,
                "ai_generation_likely": True,
                "wikipedia_search_terms": [description, f"list of {description}"],
                "reasoning": "Using default comprehensive strategy"
            }

    def _intelligent_wikipedia_search(self, description: str, strategy: dict, **kwargs):
        """
        Use LLM-powered search for Wikipedia articles with tables.

        This method uses the LLM strategy to search more intelligently.

        Args:
            description: Natural language description to search for
            strategy: LLM-generated strategy with search terms
            **kwargs: Additional arguments

        Returns:
            ScenarioList or None: Best ScenarioList found, or None if no suitable tables
        """
        from ...utilities.wikipedia import fetch_wikipedia_content

        # Use LLM-generated search terms
        search_terms = strategy.get('wikipedia_search_terms', [description])
        self._log(f"   Using LLM-recommended search terms: {', '.join(search_terms[:3])}" +
                 (f" (and {len(search_terms)-3} more)" if len(search_terms) > 3 else ""))

        # Search Wikipedia for articles
        try:
            wiki_results = fetch_wikipedia_content(search_terms[:5])  # Limit to top 5 searches
        except Exception as e:
            self._log(f"   Wikipedia API search failed: {e}")
            return None

        # Use LLM to assess articles instead of hardcoded rules
        promising_articles = self._assess_articles_with_llm(wiki_results, description)

        if not promising_articles:
            self._log("   No promising articles found")
            return None

        self._log(f"   Found {len(promising_articles)} promising articles, trying top candidates...")

        for score, article in promising_articles[:3]:  # Try top 3 articles
            try:
                self._log(f"   Trying: {article['title']} (LLM score: {score:.2f})")

                # Try to extract tables from this Wikipedia URL using LLM table selection
                result = self._try_wikipedia_tables_with_llm(article['url'], description, **kwargs)
                if result and len(result) > 0:
                    self._log(f"   ✓ Successfully extracted {len(result)} scenarios from '{article['title']}'")
                    return result
                else:
                    self._log(f"   ✗ No usable tables in '{article['title']}'")

            except Exception as e:
                self._log(f"   ✗ Failed to extract from '{article['title']}': {str(e)[:100]}...")
                continue

        return None

    def _assess_articles_with_llm(self, wiki_results: list, description: str) -> list:
        """
        Use LLM to assess which Wikipedia articles are most likely to have useful tables.

        Args:
            wiki_results: List of Wikipedia search results
            description: Original query description

        Returns:
            list: List of (score, article) tuples sorted by relevance
        """
        successful_articles = [r for r in wiki_results if r.get("status") == "Success" and r.get("url")]

        if not successful_articles:
            return []

        # Create prompt for LLM assessment
        articles_info = []
        for article in successful_articles:
            info = {
                "title": article.get("title", ""),
                "content_preview": article.get("content", "")[:800],  # First 800 chars
                "url": article.get("url", ""),
                "categories": article.get("categories", [])[:5]  # Top 5 categories
            }
            articles_info.append(info)

        system_prompt = """You are an expert at identifying Wikipedia articles that contain useful structured data tables.

Analyze the provided Wikipedia articles and score them based on how likely they are to contain tables relevant to the user's query.

Consider:
- Article titles that suggest lists, comparisons, or structured data
- Content that mentions tables, statistics, or structured information
- Categories that indicate reference material
- Relevance to the original query

Score each article from 0-10 (10 = most likely to have useful tables)."""

        # Build article descriptions without backslashes in f-string
        article_descriptions = []
        for i, art in enumerate(articles_info):
            desc = f"{i+1}. Title: {art['title']}"
            if art['categories']:
                desc += f"\n   Categories: {', '.join(art['categories'])}"
            desc += f"\n   Content preview: {art['content_preview'][:200]}..."
            article_descriptions.append(desc)

        user_prompt = f"""Original query: "{description}"

Articles to assess:
{chr(10).join(article_descriptions)}

For each article, provide a score (0-10) and brief reasoning. Respond in this JSON format:
{{
    "assessments": [
        {{"title": "Article Title", "score": 8.5, "reasoning": "brief explanation"}},
        ...
    ]
}}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.temperature,
                response_format={"type": "json_object"}
            )

            import json
            assessment = json.loads(response.choices[0].message.content)

            # Match assessments back to articles and create scored list
            scored_articles = []
            for article in successful_articles:
                for assess in assessment.get('assessments', []):
                    if assess['title'] == article['title']:
                        score = float(assess['score'])
                        if score > 0:
                            scored_articles.append((score, article))
                        self._log(f"   LLM assessed '{article['title']}': {score}/10 - {assess['reasoning']}")
                        break

            # Sort by score
            scored_articles.sort(key=lambda x: x[0], reverse=True)
            return scored_articles

        except Exception as e:
            self._log(f"   ⚠️ LLM article assessment failed: {e}, using fallback")
            # Fallback to simple scoring
            return [(1.0, article) for article in successful_articles[:3]]

    def _generate_wikipedia_search_terms(self, description: str) -> List[str]:
        """
        Generate intelligent search terms for Wikipedia based on the description.

        Args:
            description: Natural language description

        Returns:
            List of search terms to try
        """
        terms = []

        # Add the original description
        terms.append(description)

        # Add "list of" variant which is common on Wikipedia
        if not description.lower().startswith("list of"):
            terms.append(f"list of {description}")

        # Add "comparison of" variant
        if "comparison" not in description.lower():
            terms.append(f"comparison of {description}")

        # Extract key words and create variations
        key_words = [word for word in description.split()
                    if len(word) > 3 and word.lower() not in ['the', 'and', 'for', 'with', 'that']]

        if key_words:
            # Try just the main subject
            terms.append(" ".join(key_words))

            # Try individual key terms
            for word in key_words[:2]:  # Top 2 key words
                terms.append(word)

        return terms[:8]  # Limit to 8 search terms

    def _assess_article_for_tables(self, article: dict, description: str) -> float:
        """
        Assess how likely a Wikipedia article is to contain useful tables for the query.

        Args:
            article: Wikipedia article data from fetch_wikipedia_content
            description: Original search description

        Returns:
            float: Score from 0-10 indicating likelihood of useful tables
        """
        score = 0.0
        title = article.get('title', '').lower()
        content = article.get('content', '').lower()
        categories = [cat.lower() for cat in article.get('categories', [])]

        # Higher score for "list of" articles - these often have tables
        if 'list of' in title:
            score += 3.0

        # Higher score for "comparison" articles
        if 'comparison' in title or 'comparison' in content[:500]:
            score += 2.0

        # Score based on title relevance to description
        desc_words = set(description.lower().split())
        title_words = set(title.split())
        title_overlap = len(desc_words.intersection(title_words))
        score += title_overlap * 0.5

        # Score based on content length (longer articles more likely to have tables)
        content_length = len(content)
        if content_length > 5000:
            score += 1.0
        elif content_length > 2000:
            score += 0.5

        # Look for table-suggesting keywords in content preview
        table_keywords = ['countries', 'companies', 'states', 'cities', 'universities',
                         'software', 'languages', 'currencies', 'awards', 'rankings']
        for keyword in table_keywords:
            if keyword in content[:1000]:  # Check first 1000 chars
                score += 0.5

        # Bonus for relevant categories
        list_categories = ['lists', 'rankings', 'comparisons', 'tables']
        for cat in categories:
            for list_cat in list_categories:
                if list_cat in cat:
                    score += 1.0
                    break

        return min(score, 10.0)  # Cap at 10.0

    def _try_wikipedia_tables_with_llm(self, url: str, description: str, **kwargs):
        """
        Use LLM to intelligently select the best table from a Wikipedia URL.

        Args:
            url: Wikipedia URL to extract tables from
            description: Original query description for relevance assessment
            **kwargs: Additional arguments

        Returns:
            ScenarioList or None: Best table found, or None if no suitable tables
        """
        from ..scenario_list import ScenarioList
        from ..sources.wikipedia_source import WikipediaSource

        try:
            # First get all tables from the article
            tables = WikipediaSource.all_tables(url)

            if not tables or len(tables) == 0:
                return None

            # If only one table, use it
            if len(tables) == 1:
                return tables[0]

            # Multiple tables - use LLM to decide
            self._log(f"     Found {len(tables)} tables, using LLM to select best one...")

            # Get table summaries for LLM assessment
            table_summaries = tables.get_table_summaries()

            # Use LLM to select the best table
            selected_table_index = self._select_best_table_with_llm(table_summaries, description)

            if selected_table_index is not None and 0 <= selected_table_index < len(tables):
                selected_table = tables[selected_table_index]
                self._log(f"     LLM selected table {selected_table_index} with {len(selected_table)} rows")
                return selected_table
            else:
                # Fallback to largest table
                largest_index, largest_table = tables.get_largest_table()
                self._log(f"     LLM selection failed, using largest table with {len(largest_table)} rows")
                return largest_table

        except Exception as e:
            # If multi-table approach fails, try the old method
            self._log(f"     Multi-table approach failed: {str(e)[:50]}..., trying fallback")
            return self._try_wikipedia_tables(url, **kwargs)

    def _select_best_table_with_llm(self, table_summaries: list, description: str) -> int:
        """
        Use LLM to select the best table from available summaries.

        Args:
            table_summaries: List of table metadata dicts
            description: Original query description

        Returns:
            int or None: Index of best table, or None if selection fails
        """
        system_prompt = """You are an expert at selecting the most relevant data table for a user's query.

Given table summaries from a Wikipedia article, choose the table most likely to contain the structured data the user is looking for.

Consider:
- Column names and their relevance to the query
- Number of rows (more data is generally better)
- Table structure and completeness
- Direct relevance to the user's request"""

        # Format table info for LLM
        tables_info = []
        for i, summary in enumerate(table_summaries):
            info = f"Table {i}: {summary.get('rows', 0)} rows, {summary.get('cols', 0)} columns\n"
            info += f"   Columns: {', '.join(summary.get('columns', [])[:8])}" # Show first 8 columns
            if len(summary.get('columns', [])) > 8:
                info += f" (and {len(summary.get('columns', [])) - 8} more)"
            tables_info.append(info)

        user_prompt = f"""Query: "{description}"

Available tables:
{chr(10).join(tables_info)}

Which table is most relevant for the query "{description}"?

Respond in this JSON format:
{{
    "selected_table_index": 2,
    "reasoning": "brief explanation of why this table is best"
}}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.temperature,
                response_format={"type": "json_object"}
            )

            import json
            selection = json.loads(response.choices[0].message.content)
            table_index = selection.get('selected_table_index')
            reasoning = selection.get('reasoning', 'No reasoning provided')

            self._log(f"     LLM table selection: Table {table_index} - {reasoning}")

            return table_index

        except Exception as e:
            self._log(f"     ⚠️ LLM table selection failed: {e}")
            return None

    def _try_wikipedia_tables(self, url: str, **kwargs):
        """
        Try to extract tables from a Wikipedia URL, handling multiple tables intelligently.

        Args:
            url: Wikipedia URL to extract tables from
            **kwargs: Additional arguments

        Returns:
            ScenarioList or None: Best table found, or None if no suitable tables
        """
        from ..scenario_list import ScenarioList
        from ..sources.wikipedia_source import WikipediaSource

        try:
            # First try to get all tables from the article
            tables = WikipediaSource.all_tables(url)

            if not tables or len(tables) == 0:
                return None

            # If only one table, use it
            if len(tables) == 1:
                return tables[0]

            # Multiple tables - find the largest/most promising one
            self._log(f"     Found {len(tables)} tables, selecting best one...")

            # Get the largest table by row count
            largest_index, largest_table = tables.get_largest_table()

            # If the largest table has a reasonable number of rows, use it
            if len(largest_table) >= 5:  # At least 5 rows
                self._log(f"     Selected largest table with {len(largest_table)} rows")
                return largest_table

            # Otherwise try tables in order until we find one with reasonable data
            for i, table in enumerate(tables.scenario_lists):
                if len(table) >= 3:  # At least 3 rows
                    self._log(f"     Selected table {i} with {len(table)} rows")
                    return table

            # If no good tables found, return the largest anyway
            self._log(f"     No ideal tables found, using largest with {len(largest_table)} rows")
            return largest_table

        except Exception as e:
            # If multi-table approach fails, try the default single table approach
            if "table_index" not in str(e).lower():
                # This is some other error, re-raise it
                raise

            # Try to extract the default table (index 0)
            try:
                return ScenarioList.from_source("wikipedia", url, table_index=0, **kwargs)
            except:
                # If that fails, try a few more table indices
                for table_idx in [1, 2, 3]:
                    try:
                        result = ScenarioList.from_source("wikipedia", url, table_index=table_idx, **kwargs)
                        if result and len(result) > 0:
                            return result
                    except:
                        continue
                return None

    def create_scenario_list(
        self,
        description: str,
        *,
        exa_count: int = 50,
        generator_count: int = 10,
        **kwargs
    ) -> "ScenarioList":
        """
        Create a ScenarioList using LLM-powered intelligent multi-source approach.

        Args:
            description: Natural language description of desired data
            exa_count: Number of results to request from Exa (default: 50)
            generator_count: Number of scenarios to generate with AI (default: 10)
            **kwargs: Additional arguments passed to underlying methods

        Returns:
            ScenarioList: Created from the best available source

        Raises:
            RuntimeError: If all approaches fail
        """
        from ..scenario_list import ScenarioList
        from ..scenario import Scenario
        from ...dataset.vibes.scenario_generator import ScenarioGenerator

        approaches_tried = []
        last_error = None

        self._log(f"Starting LLM-powered intelligent search for: '{description}'")

        # Step 1: Use LLM to decide the best strategy (unless overridden)
        override_strategy = kwargs.pop('_override_strategy', None)

        if override_strategy:
            self._log("🎯 Using predefined strategy override...")
            strategy = override_strategy
            # Add missing fields for compatibility
            strategy.setdefault('analysis', 'Using predefined strategy')
            strategy.setdefault('reasoning', 'Strategy override applied')
            strategy.setdefault('wikipedia_search_terms', [description, f"list of {description}"])
        else:
            self._log("🧠 Analyzing query and deciding optimal strategy...")
            strategy = self._decide_search_strategy(description)

        self._log(f"📊 Analysis: {strategy['analysis']}")
        self._log(f"🎯 Strategy: {strategy['reasoning']}")
        self._log(f"📋 Approach order: {' → '.join(strategy['approach_order'])}")

        # Step 2: Execute approaches in LLM-recommended order
        for approach in strategy['approach_order']:

            if approach == "wikipedia" and strategy['wikipedia_likely']:
                self._log("🔍 Trying Wikipedia table search...")
                approaches_tried.append("Wikipedia")
                try:
                    wikipedia_result = self._intelligent_wikipedia_search(description, strategy, **kwargs)
                    if wikipedia_result and len(wikipedia_result) > 0:
                        self._log(f"✅ Success! Found {len(wikipedia_result)} scenarios from Wikipedia tables")
                        self._log("📊 Data source: Wikipedia")
                        return wikipedia_result
                    else:
                        self._log("❌ Wikipedia search returned no results")
                except Exception as e:
                    last_error = e
                    self._log(f"❌ Wikipedia search failed: {str(e)}")

            elif approach == "exa" and strategy['exa_likely']:
                self._log("🌐 Trying Exa web search...")
                approaches_tried.append("Exa")
                try:
                    search_query = f"{description}"
                    exa_kwargs = {
                        k: v for k, v in kwargs.items()
                        if k in ['criteria', 'enrichments', 'api_key', 'wait_for_completion', 'max_wait_time']
                    }
                    result = ScenarioList.from_exa(
                        query=search_query,
                        count=exa_count,
                        **exa_kwargs
                    )
                    if len(result) > 0:
                        self._log(f"✅ Success! Found {len(result)} scenarios from Exa web search")
                        self._log("📊 Data source: Exa (web search)")
                        return result
                    else:
                        self._log("❌ Exa search returned no results")
                except Exception as e:
                    last_error = e
                    self._log(f"❌ Exa search failed: {str(e)}")

            elif approach == "ai_generation" and strategy['ai_generation_likely']:
                self._log("🧠 Trying AI generation...")
                approaches_tried.append("AI Generator")
                try:
                    gen = ScenarioGenerator(
                        model=kwargs.get("model", "gpt-4o"),
                        temperature=kwargs.get("temperature", 0.7)
                    )
                    generator_kwargs = {k: v for k, v in kwargs.items() if k in ['fields']}
                    result = gen.generate_scenarios(
                        description,
                        count=generator_count,
                        **generator_kwargs
                    )
                    scenarios = ScenarioList([Scenario(scenario) for scenario in result["scenarios"]])
                    self._log(f"✅ Success! Generated {len(scenarios)} scenarios using AI")
                    self._log("📊 Data source: AI Generation")
                    return scenarios
                except Exception as e:
                    last_error = e
                    self._log(f"❌ AI generation failed: {str(e)}")

        # If we get here, all approaches failed
        approaches_str = ", ".join(approaches_tried) if approaches_tried else "None"
        error_msg = f"All recommended approaches failed for query '{description}'. Tried: {approaches_str}"
        if last_error:
            error_msg += f". Last error: {str(last_error)}"

        self._log(f"💥 {error_msg}")
        raise RuntimeError(error_msg)

    def search_with_strategy(
        self,
        description: str,
        strategy: str = "comprehensive",
        **kwargs
    ) -> "ScenarioList":
        """
        Search using a predefined strategy (now all LLM-powered).

        Args:
            description: Natural language description of desired data
            strategy: Strategy to use ('comprehensive', 'fast', 'web_only', 'ai_only')
            **kwargs: Additional arguments

        Returns:
            ScenarioList from the specified strategy
        """
        if strategy == "comprehensive":
            # Use full LLM-powered comprehensive approach
            return self.create_scenario_list(description, **kwargs)
        elif strategy == "fast":
            # Use LLM but skip Exa for speed - modify the LLM strategy accordingly
            kwargs['_override_strategy'] = {
                'approach_order': ['wikipedia', 'ai_generation'],
                'wikipedia_likely': True,
                'exa_likely': False,
                'ai_generation_likely': True
            }
            return self.create_scenario_list(description, **kwargs)
        elif strategy == "web_only":
            # Only try web sources (Wikipedia and Exa), skip AI generation
            kwargs['_override_strategy'] = {
                'approach_order': ['wikipedia', 'exa'],
                'wikipedia_likely': True,
                'exa_likely': True,
                'ai_generation_likely': False
            }
            return self.create_scenario_list(description, **kwargs)
        elif strategy == "ai_only":
            # Only use AI generation
            kwargs['_override_strategy'] = {
                'approach_order': ['ai_generation'],
                'wikipedia_likely': False,
                'exa_likely': False,
                'ai_generation_likely': True
            }
            return self.create_scenario_list(description, **kwargs)
        else:
            raise ValueError(f"Unknown strategy '{strategy}'. Valid strategies: 'comprehensive', 'fast', 'web_only', 'ai_only'")


# Convenience functions for direct usage
def from_vibes_intelligent(
    description: str,
    *,
    verbose: bool = True,
    strategy: str = "comprehensive",
    **kwargs
) -> "ScenarioList":
    """
    Convenience function to create a ScenarioList using the intelligent agent approach.

    Args:
        description: Natural language description of desired data
        verbose: If True, shows progress updates
        strategy: Search strategy ('comprehensive', 'fast', 'web_only', 'ai_only')
        **kwargs: Additional arguments passed to the agent

    Returns:
        ScenarioList created using the intelligent multi-source approach
    """
    agent = ScenarioAgent(verbose=verbose)
    return agent.search_with_strategy(description, strategy=strategy, **kwargs)