"""Content planning for topic and keyword selection."""

from seo_agent.clients.openai_client import OpenAIClient
from seo_agent.models.keyword import Keyword, KeywordGroup


class ContentPlanner:
    """Planner for content strategy and topic selection."""

    def __init__(self, openai_client: OpenAIClient):
        self.openai = openai_client

    async def generate_topics_from_keywords(
        self,
        qualified_keywords: list[Keyword],
        count: int = 5,
    ) -> list[dict]:
        """Generate topic suggestions from qualified keywords."""
        if not qualified_keywords:
            return []

        # Group keywords by potential topic clusters
        keyword_strings = [kw.keyword for kw in qualified_keywords[:15]]

        system_prompt = """You are an SEO content strategist.
Generate blog post topics based on the provided keywords.
Each topic should target 1 primary keyword and 2-3 secondary keywords.
Output ONLY valid JSON array, nothing else."""

        user_prompt = f"""Available keywords (with search volume and KD):
{self._format_keywords(qualified_keywords[:15])}

Generate {count} unique blog post topics. Each topic should:
1. Target one primary keyword from the list
2. Include 2-3 related secondary keywords
3. Have a clear search intent
4. Provide unique value to readers

Return JSON array:
[
    {{
        "title": "Blog Post Title",
        "primary_keyword": "main keyword",
        "secondary_keywords": ["kw1", "kw2"],
        "search_intent": "informational|commercial|transactional",
        "target_audience": "who this is for",
        "unique_angle": "what makes this unique"
    }}
]"""

        response = await self.openai.generate_with_system_prompt(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.8,
        )

        import json
        try:
            clean = response.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1]
                clean = clean.rsplit("```", 1)[0]
            return json.loads(clean)
        except json.JSONDecodeError:
            return []

    def _format_keywords(self, keywords: list[Keyword]) -> str:
        """Format keywords for prompt."""
        lines = []
        for kw in keywords:
            lines.append(
                f"- {kw.keyword} (vol: {kw.metrics.search_volume}, KD: {kw.metrics.keyword_difficulty})"
            )
        return "\n".join(lines)

    def select_best_topic(
        self,
        topics: list[dict],
        existing_titles: list[str],
    ) -> dict | None:
        """Select the best topic that doesn't duplicate existing content."""
        existing_lower = {t.lower() for t in existing_titles}

        for topic in topics:
            title = topic.get("title", "").lower()

            # Check for exact or very similar matches
            is_duplicate = any(
                self._titles_similar(title, existing)
                for existing in existing_lower
            )

            if not is_duplicate:
                return topic

        return topics[0] if topics else None

    def _titles_similar(self, title1: str, title2: str) -> bool:
        """Check if two titles are too similar."""
        # Normalize titles
        t1_words = set(title1.lower().split())
        t2_words = set(title2.lower().split())

        # Remove common words
        common_words = {"the", "a", "an", "to", "for", "of", "in", "on", "and", "or", "how", "what", "why"}
        t1_words -= common_words
        t2_words -= common_words

        if not t1_words or not t2_words:
            return False

        # Calculate Jaccard similarity
        intersection = len(t1_words & t2_words)
        union = len(t1_words | t2_words)

        similarity = intersection / union if union > 0 else 0

        return similarity > 0.6  # Threshold for "too similar"

    def create_keyword_group_from_topic(
        self,
        topic: dict,
        all_keywords: list[Keyword],
    ) -> KeywordGroup:
        """Create a KeywordGroup from a topic and available keywords."""
        primary_kw_str = topic.get("primary_keyword", "").lower()
        secondary_kw_strs = [s.lower() for s in topic.get("secondary_keywords", [])]

        # Find primary keyword
        primary = None
        for kw in all_keywords:
            if kw.keyword.lower() == primary_kw_str:
                primary = kw
                primary.is_primary = True
                break

        if not primary:
            # Create a basic keyword if not found
            primary = Keyword(keyword=topic.get("primary_keyword", ""), is_primary=True)

        # Find secondary keywords
        secondary = []
        for kw in all_keywords:
            if kw.keyword.lower() in secondary_kw_strs:
                secondary.append(kw)

        return KeywordGroup(
            primary_keyword=primary,
            secondary_keywords=secondary,
            topic=topic.get("title", ""),
        )

    async def suggest_content_calendar(
        self,
        category: str,
        topics: list[dict],
        posts_per_week: int = 2,
    ) -> list[dict]:
        """Suggest a content calendar from topics."""
        from datetime import datetime, timedelta

        calendar = []
        current_date = datetime.now()

        for i, topic in enumerate(topics):
            publish_date = current_date + timedelta(days=(i // posts_per_week) * 7 + (i % posts_per_week) * 3)

            calendar.append({
                "week": (i // posts_per_week) + 1,
                "suggested_publish_date": publish_date.strftime("%Y-%m-%d"),
                "topic": topic,
            })

        return calendar

    def prioritize_topics(
        self,
        topics: list[dict],
        keywords: list[Keyword],
    ) -> list[dict]:
        """Prioritize topics based on keyword metrics."""
        # Build keyword lookup
        kw_lookup = {kw.keyword.lower(): kw for kw in keywords}

        def topic_score(topic: dict) -> float:
            primary_kw = topic.get("primary_keyword", "").lower()
            kw = kw_lookup.get(primary_kw)

            if not kw:
                return 0

            # Score = volume / (KD + 1)
            if kw.metrics.keyword_difficulty == 0:
                return kw.metrics.search_volume
            return kw.metrics.search_volume / (kw.metrics.keyword_difficulty + 1)

        return sorted(topics, key=topic_score, reverse=True)


def create_content_planner(openai_client: OpenAIClient) -> ContentPlanner:
    """Factory function to create content planner."""
    return ContentPlanner(openai_client=openai_client)
