"""Image generation service with SEO metadata."""

import re
from pathlib import Path

from seo_agent.clients.openai_client import OpenAIClient
from seo_agent.models.article import Article
from seo_agent.models.image import (
    GeneratedImage,
    ImageMetadata,
    generate_alt_text,
    generate_image_filename,
)


class ImageGeneratorService:
    """Service for generating images with SEO-optimized metadata."""

    def __init__(
        self,
        openai_client: OpenAIClient,
        output_dir: Path,
        images_per_1k_words: float = 3.5,
    ):
        self.openai = openai_client
        self.output_dir = output_dir
        self.images_per_1k_words = images_per_1k_words

    async def generate_images_for_article(
        self,
        article: Article,
        size: str = "1024x1024",
    ) -> list[GeneratedImage]:
        """Generate images for an article based on word count and sections."""
        # Calculate number of images needed (3-4 per 1k words)
        word_count = article.metadata.word_count
        num_images = max(1, int((word_count / 1000) * self.images_per_1k_words))

        # Extract section headings from content
        sections = self._extract_sections(article.content)

        # Limit to available sections or max images
        num_images = min(num_images, len(sections), 10)

        images = []
        topic_slug = article.metadata.slug

        for i, section in enumerate(sections[:num_images]):
            image = await self._generate_image_for_section(
                section_heading=section["heading"],
                section_content=section["content"],
                primary_keyword=article.metadata.primary_keyword,
                topic_slug=topic_slug,
                index=i + 1,
                size=size,
            )
            images.append(image)

        return images

    async def _generate_image_for_section(
        self,
        section_heading: str,
        section_content: str,
        primary_keyword: str,
        topic_slug: str,
        index: int,
        size: str = "1024x1024",
    ) -> GeneratedImage:
        """Generate a single image for a section."""
        # Generate optimized prompt
        prompt = await self.openai.generate_image_prompt(
            section_heading=section_heading,
            article_context=section_content,
            primary_keyword=primary_keyword,
        )

        # Generate filename and metadata
        filename = generate_image_filename(
            topic_slug=topic_slug,
            keyword=primary_keyword,
            index=index,
        )

        alt_text = generate_alt_text(
            section_heading=section_heading,
            keyword=primary_keyword,
        )

        # Create output path
        output_path = self.output_dir / filename

        # Generate image
        result = await self.openai.generate_image(
            prompt=prompt,
            size=size,
            output_path=output_path,
        )

        # Create metadata
        metadata = ImageMetadata(
            filename=filename,
            alt_text=alt_text,
            caption=section_heading,
            section_heading=section_heading,
            primary_keyword=primary_keyword,
        )

        return GeneratedImage(
            metadata=metadata,
            prompt=prompt,
            revised_prompt=result.get("revised_prompt") or prompt,
            file_path=output_path if output_path.exists() else None,
            size=size,
            index=index,
        )

    def _extract_sections(self, content: str) -> list[dict]:
        """Extract sections (H2 headings and their content) from Markdown."""
        sections = []

        # Split by H2 headings
        h2_pattern = r'^##\s+(.+)$'
        parts = re.split(h2_pattern, content, flags=re.MULTILINE)

        # First part is content before first H2
        current_heading = "Introduction"
        current_content = parts[0] if parts else ""

        if current_content.strip():
            sections.append({
                "heading": current_heading,
                "content": current_content.strip()[:500],
            })

        # Process remaining parts (heading, content pairs)
        for i in range(1, len(parts), 2):
            if i + 1 < len(parts):
                heading = parts[i].strip()
                content_text = parts[i + 1].strip()[:500]

                if heading and content_text:
                    sections.append({
                        "heading": heading,
                        "content": content_text,
                    })

        return sections

    async def generate_featured_image(
        self,
        article: Article,
        size: str = "1792x1024",
    ) -> GeneratedImage:
        """Generate a featured/hero image for the article."""
        prompt = await self.openai.generate_image_prompt(
            section_heading=article.metadata.title,
            article_context=article.content[:1000],
            primary_keyword=article.metadata.primary_keyword,
        )

        # Enhance prompt for featured image
        enhanced_prompt = f"Professional blog featured image: {prompt}. Modern, clean design suitable for article header."

        filename = generate_image_filename(
            topic_slug=article.metadata.slug,
            keyword=article.metadata.primary_keyword,
            index=0,
        )
        filename = filename.replace("-0.", "-featured.")

        output_path = self.output_dir / filename

        result = await self.openai.generate_image(
            prompt=enhanced_prompt,
            size=size,
            output_path=output_path,
        )

        metadata = ImageMetadata(
            filename=filename,
            alt_text=f"{article.metadata.title} - {article.metadata.primary_keyword}",
            caption=article.metadata.title,
            section_heading=article.metadata.title,
            primary_keyword=article.metadata.primary_keyword,
        )

        return GeneratedImage(
            metadata=metadata,
            prompt=enhanced_prompt,
            revised_prompt=result.get("revised_prompt") or enhanced_prompt,
            file_path=output_path if output_path.exists() else None,
            size=size,
            index=0,
        )

    def insert_images_into_content(
        self,
        article: Article,
        images: list[GeneratedImage],
    ) -> str:
        """Insert image references into article content at appropriate positions."""
        content = article.content
        sections = self._extract_sections(content)

        # Map images to sections by heading
        image_map = {}
        for img in images:
            heading = img.metadata.section_heading
            if heading:
                image_map[heading.lower()] = img

        # Insert images after their respective section headings
        for section in sections:
            heading = section["heading"]
            img = image_map.get(heading.lower())

            if img:
                # Find the heading in content and insert image after it
                pattern = rf'(##\s+{re.escape(heading)})\n'
                replacement = rf'\1\n\n{img.markdown_reference}\n'
                content = re.sub(pattern, replacement, content, count=1, flags=re.IGNORECASE)

        return content

    def get_image_references_markdown(
        self,
        images: list[GeneratedImage],
    ) -> str:
        """Get Markdown formatted image references."""
        lines = []
        for img in images:
            lines.append(f"- {img.markdown_reference}")
            lines.append(f"  - Alt: {img.metadata.alt_text}")
            lines.append(f"  - Caption: {img.metadata.caption}")
        return "\n".join(lines)


def create_image_generator(
    openai_client: OpenAIClient,
    output_dir: Path,
    images_per_1k_words: float = 3.5,
) -> ImageGeneratorService:
    """Factory function to create image generator service."""
    return ImageGeneratorService(
        openai_client=openai_client,
        output_dir=output_dir,
        images_per_1k_words=images_per_1k_words,
    )
