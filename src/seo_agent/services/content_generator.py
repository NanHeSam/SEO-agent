"""Content generation service for SEO articles."""

from seo_agent.clients.openai_client import OpenAIClient
from seo_agent.models.article import Article, ArticleMetadata
from seo_agent.models.keyword import Keyword, KeywordGroup


class ContentGeneratorService:
    """Service for generating SEO-optimized article content."""

    def __init__(
        self,
        openai_client: OpenAIClient,
        default_word_count: int = 2000,
    ):
        self.openai = openai_client
        self.default_word_count = default_word_count

    async def generate_article(
        self,
        topic: str,
        primary_keyword: str,
        secondary_keywords: list[str],
        search_intent: str,
        word_count: int | None = None,
        existing_posts: list[dict[str, str]] | None = None,
    ) -> Article:
        """Generate a complete SEO-optimized article."""
        target_word_count = word_count or self.default_word_count

        # Generate article content via OpenAI
        result = await self.openai.generate_article(
            topic=topic,
            primary_keyword=primary_keyword,
            secondary_keywords=secondary_keywords,
            search_intent=search_intent,
            word_count=target_word_count,
            existing_posts=existing_posts,
        )

        # Calculate reading time (average 200 words per minute)
        actual_word_count = result.get("word_count", len(result["content"].split()))
        reading_time = max(1, actual_word_count // 200)

        # Create metadata
        metadata = ArticleMetadata(
            title=result.get("title", topic),
            meta_description=result.get("meta_description", "")[:160],
            primary_keyword=primary_keyword,
            secondary_keywords=secondary_keywords,
            search_intent=search_intent,
            word_count=actual_word_count,
            reading_time_minutes=reading_time,
        )

        return Article(
            metadata=metadata,
            content=result["content"],
        )

    async def generate_article_from_keyword_group(
        self,
        keyword_group: KeywordGroup,
        search_intent: str,
        word_count: int | None = None,
        existing_posts: list[dict[str, str]] | None = None,
    ) -> Article:
        """Generate article from a KeywordGroup."""
        return await self.generate_article(
            topic=keyword_group.topic or keyword_group.primary_keyword.keyword,
            primary_keyword=keyword_group.primary_keyword.keyword,
            secondary_keywords=[kw.keyword for kw in keyword_group.secondary_keywords],
            search_intent=search_intent,
            word_count=word_count,
            existing_posts=existing_posts,
        )

    async def generate_meta_description(
        self,
        title: str,
        primary_keyword: str,
        content_preview: str = "",
    ) -> str:
        """Generate an optimized meta description."""
        system_prompt = """You are an SEO expert. Generate a compelling meta description.
Output ONLY the meta description, nothing else.
Requirements:
- 150-160 characters
- Include the primary keyword naturally
- Be compelling and encourage clicks
- Accurately represent the content"""

        user_prompt = f"""Title: {title}
Primary Keyword: {primary_keyword}
Content Preview: {content_preview[:500]}

Generate a meta description:"""

        result = await self.openai.generate_with_system_prompt(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.7,
            max_tokens=100,
        )

        return result.strip()[:160]

    async def generate_outline(
        self,
        topic: str,
        primary_keyword: str,
        secondary_keywords: list[str],
        search_intent: str,
    ) -> dict:
        """Generate an article outline before full content."""
        system_prompt = """You are an SEO content strategist.
Generate a detailed article outline in JSON format.
The outline should follow SEO best practices."""

        user_prompt = f"""Create an outline for:

Topic: {topic}
Primary Keyword: {primary_keyword}
Secondary Keywords: {', '.join(secondary_keywords)}
Search Intent: {search_intent}

Return JSON with this format:
{{
    "title": "SEO-optimized title",
    "meta_description": "150-160 char description",
    "sections": [
        {{
            "heading": "H2 heading",
            "key_points": ["point 1", "point 2"],
            "target_keyword": "keyword to include"
        }}
    ],
    "estimated_word_count": 2000,
    "call_to_action": "suggested CTA"
}}"""

        response = await self.openai.generate_with_system_prompt(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.7,
        )

        import json
        try:
            clean = response.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1]
                clean = clean.rsplit("```", 1)[0]
            return json.loads(clean)
        except json.JSONDecodeError:
            return {
                "title": topic,
                "sections": [],
                "outline_text": response,
            }

    async def improve_article(
        self,
        article: Article,
        feedback: str,
    ) -> Article:
        """Improve an existing article based on feedback."""
        system_prompt = """You are an SEO content editor.
Improve the article based on the provided feedback.
Maintain SEO optimization while making improvements.
Output the improved article in Markdown format."""

        user_prompt = f"""Original Article:
{article.content}

Feedback to address:
{feedback}

Primary Keyword: {article.metadata.primary_keyword}
Secondary Keywords: {', '.join(article.metadata.secondary_keywords)}

Please improve the article while maintaining SEO optimization."""

        improved_content = await self.openai.generate_with_system_prompt(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.7,
            max_tokens=8192,
        )

        # Update article with improved content
        new_word_count = len(improved_content.split())
        article.metadata.word_count = new_word_count
        article.metadata.reading_time_minutes = max(1, new_word_count // 200)
        article.content = improved_content

        return article

    def calculate_keyword_density(
        self,
        content: str,
        keyword: str,
    ) -> float:
        """Calculate keyword density as a percentage."""
        content_lower = content.lower()
        keyword_lower = keyword.lower()

        word_count = len(content_lower.split())
        if word_count == 0:
            return 0.0

        keyword_count = content_lower.count(keyword_lower)
        keyword_words = len(keyword_lower.split())

        return (keyword_count * keyword_words / word_count) * 100

    def analyze_seo_score(self, article: Article) -> dict:
        """Analyze article for SEO optimization."""
        content = article.content.lower()
        primary_kw = article.metadata.primary_keyword.lower()

        checks = {
            "keyword_in_title": primary_kw in article.metadata.title.lower(),
            "keyword_in_first_paragraph": self._check_first_paragraph(content, primary_kw),
            "keyword_in_h2": self._check_h2_headings(content, primary_kw),
            "meta_description_length": 150 <= len(article.metadata.meta_description) <= 160,
            "keyword_density": self.calculate_keyword_density(content, primary_kw),
            "word_count": article.metadata.word_count,
            "has_internal_links": len(article.internal_links) > 0,
        }

        # Calculate score
        score = 0
        if checks["keyword_in_title"]:
            score += 20
        if checks["keyword_in_first_paragraph"]:
            score += 20
        if checks["keyword_in_h2"]:
            score += 15
        if checks["meta_description_length"]:
            score += 15
        if 1.0 <= checks["keyword_density"] <= 2.5:
            score += 15
        if checks["word_count"] >= 1500:
            score += 10
        if checks["has_internal_links"]:
            score += 5

        return {
            "score": score,
            "max_score": 100,
            "checks": checks,
        }

    def _check_first_paragraph(self, content: str, keyword: str) -> bool:
        """Check if keyword is in the first paragraph."""
        paragraphs = content.split("\n\n")
        for p in paragraphs:
            if p.strip() and not p.strip().startswith("#"):
                return keyword in p.lower()
        return False

    def _check_h2_headings(self, content: str, keyword: str) -> bool:
        """Check if keyword is in any H2 heading."""
        import re
        h2_pattern = r'^##\s+(.+)$'
        h2_matches = re.findall(h2_pattern, content, re.MULTILINE)
        return any(keyword in h2.lower() for h2 in h2_matches)


def create_content_generator(
    openai_client: OpenAIClient,
    default_word_count: int = 2000,
) -> ContentGeneratorService:
    """Factory function to create content generator service."""
    return ContentGeneratorService(
        openai_client=openai_client,
        default_word_count=default_word_count,
    )
