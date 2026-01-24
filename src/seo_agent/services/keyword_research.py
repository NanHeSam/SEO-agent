"""Keyword research service combining DataForSEO and OpenAI."""

from typing import Any

from seo_agent.clients.dataforseo_client import DataForSEOClient
from seo_agent.clients.openai_client import OpenAIClient
from seo_agent.models.keyword import Keyword, KeywordGroup, KeywordMetrics


class KeywordResearchService:
    """Service for keyword research using both workflows."""

    def __init__(
        self,
        dataforseo_client: DataForSEOClient,
        openai_client: OpenAIClient,
        min_volume: int = 5000,
        max_kd: float = 30,
    ):
        self.dataforseo = dataforseo_client
        self.openai = openai_client
        self.min_volume = min_volume
        self.max_kd = max_kd

    async def original_workflow(
        self,
        existing_posts: list[dict[str, str]],
        keyword_count: int = 20,
        llm_fields: list[str] | None = None,
    ) -> list[Keyword]:
        """
        Original workflow: GPT suggests keywords, DataForSEO validates.

        1. GPT-5.2 suggests keywords based on existing content
        2. DataForSEO gets metrics for each keyword
        3. Filter by KD < 30 AND volume > 5000
        """
        # Step 1: Get keyword suggestions from GPT
        suggested_keywords = await self.openai.suggest_keywords(
            existing_posts=existing_posts,
            count=keyword_count,
            fields=llm_fields,
        )

        if not suggested_keywords:
            return []

        # Step 2: Get metrics from DataForSEO
        async with self.dataforseo:
            metrics_data = await self._get_metrics_for_keywords(suggested_keywords)

        # Step 3: Create Keyword objects and filter
        keywords = []
        for kw_str in suggested_keywords:
            metrics = metrics_data.get(kw_str.lower(), {})
            keyword = Keyword(
                keyword=kw_str,
                metrics=KeywordMetrics(
                    search_volume=metrics.get("search_volume") or 0,
                    keyword_difficulty=metrics.get("keyword_difficulty") or 0,
                    cpc=metrics.get("cpc") or 0,
                    competition=metrics.get("competition") or 0,
                    competition_level=metrics.get("competition_level", ""),
                ),
                source="gpt_suggested",
            )
            keywords.append(keyword)

        return keywords

    async def alternative_workflow(
        self,
        existing_posts: list[dict[str, str]],
        keyword_count: int = 10,
        llm_fields: list[str] | None = None,
    ) -> tuple[Any, list[Keyword]]:
        """
        Alternative workflow: GPT suggests topic, DataForSEO generates keywords.

        1. GPT-5.2 suggests unique topic (no duplicates with existing)
        2. DataForSEO generates 10-11 keywords for the topic
        """
        # Step 1: Get topic suggestion from GPT
        topic_data = await self.openai.suggest_topic(
            existing_posts=existing_posts,
            fields=llm_fields,
        )

        # Step 2: Use topic to get related keywords from DataForSEO
        seed_keyword = topic_data.get("primary_keyword", topic_data.get("title", ""))

        if not seed_keyword:
            return topic_data, []

        async with self.dataforseo:
            suggestions = await self.dataforseo.get_keyword_suggestions(
                seed_keyword=seed_keyword,
                limit=keyword_count + 5,  # Get extra to filter
            )

            # Get difficulty scores
            kw_strings = [s["keyword"] for s in suggestions[:keyword_count]]
            difficulty_data = await self.dataforseo.get_bulk_keyword_difficulty(kw_strings)

        # Merge and create Keyword objects
        keywords = []
        for suggestion in suggestions[:keyword_count]:
            kw_lower = suggestion["keyword"].lower()
            difficulty = difficulty_data.get(kw_lower, {}).get("keyword_difficulty", 0)

            keyword = Keyword(
                keyword=suggestion["keyword"],
                metrics=KeywordMetrics(
                    search_volume=suggestion.get("search_volume") or 0,
                    keyword_difficulty=difficulty or 0,
                    cpc=suggestion.get("cpc") or 0,
                    competition=suggestion.get("competition") or 0,
                    competition_level=suggestion.get("competition_level", ""),
                ),
                source="dataforseo_suggested",
            )
            keywords.append(keyword)

        return topic_data, keywords

    async def _get_metrics_for_keywords(
        self,
        keywords: list[str],
    ) -> Any:
        """Get metrics for a list of keywords."""
        # Get exact search volume for keywords
        volume_data = await self.dataforseo.get_search_volume(keywords)

        # Get keyword difficulty
        difficulty = await self.dataforseo.get_bulk_keyword_difficulty(keywords)

        # Build metrics map combining both data sources
        metrics_map = {}

        # Start with volume data
        for kw, vol_data in volume_data.items():
            metrics_map[kw] = {
                "search_volume": vol_data.get("search_volume") or 0,
                "cpc": vol_data.get("cpc") or 0,
                "competition": vol_data.get("competition") or 0,
                "competition_level": vol_data.get("competition_level", ""),
                "keyword_difficulty": 0,
            }

        # Add difficulty data
        for kw, diff_data in difficulty.items():
            if kw in metrics_map:
                metrics_map[kw]["keyword_difficulty"] = diff_data.get("keyword_difficulty") or 0
            else:
                metrics_map[kw] = {
                    "keyword_difficulty": diff_data.get("keyword_difficulty") or 0,
                    "search_volume": 0,
                    "cpc": 0,
                    "competition": 0,
                    "competition_level": "",
                }

        return metrics_map

    def filter_keywords(
        self,
        keywords: list[Keyword],
        min_volume: int | None = None,
        max_kd: float | None = None,
    ) -> list[Keyword]:
        """Filter keywords by volume and difficulty thresholds."""
        min_vol = min_volume if min_volume is not None else self.min_volume
        max_difficulty = max_kd if max_kd is not None else self.max_kd

        return [
            kw for kw in keywords
            if kw.qualifies(min_volume=min_vol, max_kd=max_difficulty)
        ]

    def rank_keywords(self, keywords: list[Keyword]) -> list[Keyword]:
        """Rank keywords by a composite score (volume / difficulty)."""
        def score(kw: Keyword) -> float:
            if kw.metrics.keyword_difficulty == 0:
                return kw.metrics.search_volume
            return kw.metrics.search_volume / (kw.metrics.keyword_difficulty + 1)

        return sorted(keywords, key=score, reverse=True)

    async def generate_topics_from_keywords(
        self,
        keywords: list[Keyword],
        count: int = 5,
    ) -> list[Any]:
        """Generate topic suggestions from qualified keywords."""
        keyword_strings = [kw.keyword for kw in keywords[:10]]

        topics = []
        for i in range(0, len(keyword_strings), 3):
            batch = keyword_strings[i:i+3]
            topic = await self.openai.suggest_topic(
                existing_posts=[],  # Not checking duplicates here
                keywords=batch,
            )
            topics.append(topic)

            if len(topics) >= count:
                break

        return topics

    def create_keyword_group(
        self,
        primary: Keyword,
        secondary: list[Keyword],
        topic: str = "",
    ) -> KeywordGroup:
        """Create a keyword group for an article."""
        primary.is_primary = True
        return KeywordGroup(
            primary_keyword=primary,
            secondary_keywords=secondary,
            topic=topic,
        )


def create_keyword_research_service(
    dataforseo_client: DataForSEOClient,
    openai_client: OpenAIClient,
    min_volume: int = 5000,
    max_kd: float = 30,
) -> KeywordResearchService:
    """Factory function to create keyword research service."""
    return KeywordResearchService(
        dataforseo_client=dataforseo_client,
        openai_client=openai_client,
        min_volume=min_volume,
        max_kd=max_kd,
    )
