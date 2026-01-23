"""OpenAI API client for GPT-5.2 text and image generation."""

import base64
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

from seo_agent.core.workflow_logger import get_logger


class OpenAIClient:
    """Client for OpenAI API (GPT-5.2 + image generation)."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-5.2",
        image_model: str = "gpt-image-1-mini",
    ):
        self._client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.image_model = image_model

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> str:
        """Generate a chat completion."""
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_completion_tokens=max_tokens,
            **kwargs,
        )
        return response.choices[0].message.content or ""

    async def generate_with_system_prompt(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        operation_name: str = "llm_call",
    ) -> str:
        """Generate completion with a system and user prompt."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        response = await self.chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Log the LLM call
        logger = get_logger()
        if logger:
            logger.log_llm_call(
                operation=operation_name,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response=response,
                model=self.model,
            )

        return response

    async def suggest_keywords(
        self,
        category: str,
        existing_titles: list[str],
        count: int = 20,
    ) -> list[str]:
        """Suggest SEO keywords based on category and existing content."""
        system_prompt = """You are an SEO expert specializing in keyword research.
Your task is to suggest high-potential keywords for blog content.
Output ONLY a JSON array of keyword strings, nothing else."""

        existing_content = "\n".join(f"- {title}" for title in existing_titles[:20])

        user_prompt = f"""Category: {category}

Existing blog posts:
{existing_content}

Suggest {count} unique, high-potential keywords for this category that:
1. Are NOT already covered by existing posts
2. Have commercial or informational search intent
3. Are long-tail keywords (3-5 words) for better ranking potential
4. Are relevant to job seekers and career development

Return ONLY a JSON array of strings like: ["keyword 1", "keyword 2", ...]"""

        response = await self.generate_with_system_prompt(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.8,
            operation_name="suggest_keywords",
        )

        # Parse JSON array from response
        import json
        try:
            # Handle potential markdown code blocks
            clean_response = response.strip()
            if clean_response.startswith("```"):
                clean_response = clean_response.split("\n", 1)[1]
                clean_response = clean_response.rsplit("```", 1)[0]
            keywords = json.loads(clean_response)

            # Log parsed keywords
            logger = get_logger()
            if logger:
                logger.log_keywords_suggested(keywords, source="gpt")

            return keywords
        except json.JSONDecodeError:
            # Fallback: try to extract keywords from text
            lines = response.strip().split("\n")
            keywords = [line.strip().strip("-").strip('"').strip("'") for line in lines if line.strip()]

            # Log parsed keywords
            logger = get_logger()
            if logger:
                logger.log_keywords_suggested(keywords, source="gpt_fallback")

            return keywords

    async def suggest_topic(
        self,
        category: str,
        existing_titles: list[str],
        keywords: list[str] | None = None,
    ) -> dict[str, Any]:
        """Suggest a unique blog topic that doesn't duplicate existing content."""
        system_prompt = """You are an SEO content strategist.
Your task is to suggest a unique, high-value blog topic.
Output ONLY valid JSON with the specified format, nothing else."""

        existing_content = "\n".join(f"- {title}" for title in existing_titles[:30])
        keywords_context = ""
        if keywords:
            keywords_context = f"\nTarget keywords to incorporate: {', '.join(keywords[:10])}"

        user_prompt = f"""Category: {category}

Existing blog posts (AVOID duplicating these):
{existing_content}
{keywords_context}

Suggest ONE unique blog topic that:
1. Is NOT covered by any existing post
2. Has high search potential
3. Provides unique value to job seekers
4. Can rank for the target keywords (if provided)

Return JSON with this exact format:
{{
    "title": "The Blog Post Title",
    "primary_keyword": "main target keyword",
    "secondary_keywords": ["keyword2", "keyword3"],
    "search_intent": "informational|commercial|transactional",
    "target_audience": "description of target reader",
    "unique_angle": "what makes this topic unique"
}}"""

        response = await self.generate_with_system_prompt(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.8,
            operation_name="suggest_topic",
        )

        import json
        try:
            clean_response = response.strip()
            if clean_response.startswith("```"):
                clean_response = clean_response.split("\n", 1)[1]
                clean_response = clean_response.rsplit("```", 1)[0]
            return json.loads(clean_response)
        except json.JSONDecodeError:
            return {
                "title": "Suggested Topic",
                "primary_keyword": "",
                "secondary_keywords": [],
                "search_intent": "informational",
                "target_audience": "",
                "unique_angle": response,
            }

    async def generate_article(
        self,
        topic: str,
        primary_keyword: str,
        secondary_keywords: list[str],
        search_intent: str,
        word_count: int = 2000,
        existing_posts: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Generate a full SEO-optimized article."""
        system_prompt = """You are an expert SEO content writer specializing in career and job search content.
Write engaging, informative articles that rank well in search engines.
Follow SEO best practices for keyword placement and content structure.
Output the article in Markdown format with proper heading hierarchy."""

        cross_links_context = ""
        if existing_posts:
            links_list = "\n".join(
                f"- [{post['title']}]({post['url']})"
                for post in existing_posts[:10]
            )
            cross_links_context = f"""

Available posts for internal linking (include 3-4 relevant links naturally):
{links_list}"""

        user_prompt = f"""Write a comprehensive SEO article with these specifications:

**Topic:** {topic}
**Primary Keyword:** {primary_keyword}
**Secondary Keywords:** {', '.join(secondary_keywords)}
**Search Intent:** {search_intent}
**Target Word Count:** {word_count} words
{cross_links_context}

**SEO Requirements:**
1. Include the primary keyword in:
   - Title (H1)
   - First paragraph
   - At least one H2 heading
   - Conclusion
2. Distribute secondary keywords naturally (1-2% density)
3. Use proper heading hierarchy (H1 > H2 > H3)
4. Include a meta description (150-160 characters)
5. Match the search intent throughout the content
6. Add internal links to relevant existing posts (if provided)

**Output Format:**
Start with YAML frontmatter containing:
- title
- meta_description
- primary_keyword
- secondary_keywords
- search_intent

Then the full article in Markdown format."""

        response = await self.generate_with_system_prompt(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.7,
            max_tokens=8192,
            operation_name="generate_article",
        )

        # Parse the response to extract frontmatter and content
        return self._parse_article_response(response, primary_keyword, secondary_keywords)

    def _parse_article_response(
        self,
        response: str,
        primary_keyword: str,
        secondary_keywords: list[str],
    ) -> dict[str, Any]:
        """Parse article response to extract metadata and content."""
        import re

        # Try to extract YAML frontmatter
        frontmatter_match = re.match(
            r'^---\s*\n(.*?)\n---\s*\n(.*)$',
            response,
            re.DOTALL
        )

        if frontmatter_match:
            import yaml
            try:
                metadata = yaml.safe_load(frontmatter_match.group(1))
                content = frontmatter_match.group(2).strip()
            except yaml.YAMLError:
                metadata = {}
                content = response
        else:
            metadata = {}
            content = response

        # Extract title from content if not in metadata
        title = metadata.get("title", "")
        if not title:
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            if title_match:
                title = title_match.group(1)

        # Extract or generate meta description
        meta_description = metadata.get("meta_description", "")
        if not meta_description:
            # Take first paragraph as fallback
            first_para = re.search(r'\n\n([^#\n].+?)(?:\n\n|$)', content)
            if first_para:
                meta_description = first_para.group(1)[:160]

        return {
            "title": title,
            "meta_description": meta_description,
            "primary_keyword": metadata.get("primary_keyword", primary_keyword),
            "secondary_keywords": metadata.get("secondary_keywords", secondary_keywords),
            "search_intent": metadata.get("search_intent", "informational"),
            "content": content,
            "word_count": len(content.split()),
        }

    async def generate_image(
        self,
        prompt: str,
        size: str = "1024x1024",
        output_path: Path | None = None,
    ) -> dict[str, Any]:
        """Generate an image using the configured image model."""
        import httpx

        # Generate image - use URL format for broader compatibility
        response = await self._client.images.generate(
            model=self.image_model,
            prompt=prompt,
            size=size,
            n=1,
        )

        image_data = response.data[0]

        # Get image URL or base64 data depending on response
        image_url = getattr(image_data, "url", None)
        b64_data = getattr(image_data, "b64_json", None)

        result = {
            "prompt": prompt,
            "size": size,
            "b64_data": b64_data,
            "image_url": image_url,
            "revised_prompt": getattr(image_data, "revised_prompt", prompt),
        }

        # Save image to file if output path specified
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)

            if b64_data:
                # Save from base64
                with open(output_path, "wb") as f:
                    f.write(base64.b64decode(b64_data))
                result["file_path"] = str(output_path)
            elif image_url:
                # Download from URL
                async with httpx.AsyncClient() as http_client:
                    img_response = await http_client.get(image_url)
                    img_response.raise_for_status()
                    with open(output_path, "wb") as f:
                        f.write(img_response.content)
                result["file_path"] = str(output_path)

        return result

    async def generate_image_prompt(
        self,
        section_heading: str,
        article_context: str,
        primary_keyword: str,
    ) -> str:
        """Generate an optimized prompt for image generation."""
        system_prompt = """You are an expert at creating image generation prompts.
Create prompts that result in professional, blog-appropriate images.
Output ONLY the image prompt, nothing else."""

        user_prompt = f"""Create an image generation prompt for a blog article image.

Section Heading: {section_heading}
Article Context: {article_context[:500]}
Primary Keyword: {primary_keyword}

Requirements:
1. Professional, clean style suitable for a career/job search blog
2. No text or words in the image
3. Modern, minimalist aesthetic
4. Relevant to the section content

Return ONLY the image prompt (1-2 sentences)."""

        return await self.generate_with_system_prompt(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.7,
            max_tokens=200,
            operation_name="generate_image_prompt",
        )

    async def suggest_topics_and_keywords(
        self,
        existing_posts: list[dict],  # [{title, summary, content?}]
        suggestion_count: int = 10,
    ) -> dict:
        """
        Analyze existing blog content and suggest new topics and keywords.

        Returns:
            {
                "topic_ideas": [...],
                "keyword_suggestions": [...],
                "content_gaps": [...]
            }
        """
        system_prompt = """You are an expert SEO content strategist analyzing a blog's existing content.
Your task is to identify content gaps and suggest new topics and keywords.
Output ONLY valid JSON with the specified format, nothing else."""

        # Prepare content summary for analysis
        posts_summary = []
        for post in existing_posts[:50]:  # Limit to avoid token limits
            summary = {
                "title": post.get("title", ""),
                "summary": post.get("summary", "")[:200],  # Truncate summaries
            }
            # Include content snippet if available
            content = post.get("content", "")
            if content:
                summary["content_preview"] = content[:500]
            posts_summary.append(summary)

        posts_text = "\n".join(
            f"- {p['title']}: {p.get('summary', '')[:100]}"
            for p in posts_summary
        )

        user_prompt = f"""Analyze these existing blog posts and suggest new content opportunities:

Existing Blog Posts ({len(posts_summary)} total):
{posts_text}

Based on this content, provide {suggestion_count} suggestions in this exact JSON format:
{{
    "topic_ideas": [
        {{
            "title": "Suggested article title",
            "description": "Brief description of what this article would cover",
            "primary_keyword": "main target keyword",
            "secondary_keywords": ["keyword2", "keyword3"],
            "search_intent": "informational|commercial|transactional",
            "rationale": "Why this topic would be valuable (content gap, trending, etc.)"
        }}
    ],
    "keyword_suggestions": [
        {{
            "keyword": "long-tail keyword phrase",
            "intent": "informational|commercial|transactional",
            "difficulty_estimate": "low|medium|high",
            "rationale": "Why this keyword is a good opportunity"
        }}
    ],
    "content_gaps": [
        {{
            "gap": "Description of missing content area",
            "opportunity": "How this could be addressed",
            "priority": "high|medium|low"
        }}
    ]
}}

Focus on:
1. Topics NOT already covered by existing posts
2. Long-tail keywords with commercial/informational intent
3. Content gaps that competitors might be filling
4. Trending topics in the career/job search space"""

        response = await self.generate_with_system_prompt(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.8,
            max_tokens=4096,
            operation_name="suggest_topics_and_keywords",
        )

        import json
        try:
            clean_response = response.strip()
            if clean_response.startswith("```"):
                clean_response = clean_response.split("\n", 1)[1]
                clean_response = clean_response.rsplit("```", 1)[0]
            return json.loads(clean_response)
        except json.JSONDecodeError:
            # Return empty structure on parse failure
            return {
                "topic_ideas": [],
                "keyword_suggestions": [],
                "content_gaps": [],
                "raw_response": response,
            }


def create_openai_client(
    api_key: str,
    model: str = "gpt-5.2",
    image_model: str = "gpt-image-1-mini",
) -> OpenAIClient:
    """Factory function to create an OpenAI client."""
    return OpenAIClient(api_key=api_key, model=model, image_model=image_model)
