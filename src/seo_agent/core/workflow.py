"""Main workflow orchestration for SEO article generation."""

from pathlib import Path
from typing import Callable

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from seo_agent.clients.dataforseo_client import DataForSEOClient, create_dataforseo_client
from seo_agent.clients.openai_client import OpenAIClient, create_openai_client
from seo_agent.config import Settings
from seo_agent.core.category_manager import CategoryManager
from seo_agent.core.content_planner import ContentPlanner
from seo_agent.models.article import Article
from seo_agent.models.blog_post import ScrapedContent
from seo_agent.models.image import GeneratedImage
from seo_agent.models.keyword import Keyword, KeywordGroup
from seo_agent.output.json_writer import JSONWriter
from seo_agent.output.markdown_writer import MarkdownWriter
from seo_agent.services.content_generator import ContentGeneratorService
from seo_agent.services.cross_linker import CrossLinkerService
from seo_agent.services.image_generator import ImageGeneratorService
from seo_agent.services.keyword_research import KeywordResearchService
from seo_agent.services.scraper import BlogScraper


console = Console()


class WorkflowOrchestrator:
    """Orchestrates the full SEO article generation workflow."""

    def __init__(self, settings: Settings):
        self.settings = settings
        settings.ensure_directories()

        # Initialize clients
        self.openai_client = create_openai_client(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            image_model=settings.openai_image_model,
        )
        self.dataforseo_client = create_dataforseo_client(
            api_credentials=settings.dataforseo_api_credentials,
        )

        # Initialize services
        self.scraper = BlogScraper(base_url=settings.target_blog_url)
        self.keyword_service = KeywordResearchService(
            dataforseo_client=self.dataforseo_client,
            openai_client=self.openai_client,
            min_volume=settings.default_min_volume,
            max_kd=settings.default_max_kd,
        )
        self.content_generator = ContentGeneratorService(
            openai_client=self.openai_client,
        )
        self.image_generator = ImageGeneratorService(
            openai_client=self.openai_client,
            output_dir=settings.generated_images_dir,
        )
        self.cross_linker = CrossLinkerService()
        self.content_planner = ContentPlanner(openai_client=self.openai_client)
        self.category_manager = CategoryManager(categories_file=settings.categories_file)

        # Initialize writers
        self.markdown_writer = MarkdownWriter(output_dir=settings.generated_articles_dir)
        self.json_writer = JSONWriter(output_dir=settings.generated_articles_dir)

    async def run_original_workflow(
        self,
        category: str,
        interactive: bool = True,
        min_volume: int | None = None,
        max_kd: float | None = None,
        topic_selector: Callable[[list[dict]], dict] | None = None,
    ) -> Article | None:
        """
        Run the original workflow:
        1. Scrape existing content
        2. GPT suggests keywords
        3. DataForSEO validates keywords
        4. Filter by volume/KD
        5. Generate topics
        6. User selects topic + provides intent
        7. Generate article with images and cross-links
        """
        min_vol = min_volume or self.settings.default_min_volume
        max_difficulty = max_kd or self.settings.default_max_kd

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # Step 1: Scrape existing content
            task = progress.add_task("Scraping existing content...", total=None)
            scraped = await self._scrape_or_load(category)
            existing_titles = scraped.titles if scraped else []
            progress.update(task, completed=True)
            console.print(f"[green]Found {len(existing_titles)} existing posts[/green]")

            # Step 2-3: Get and validate keywords
            task = progress.add_task("Researching keywords...", total=None)
            keywords = await self.keyword_service.original_workflow(
                category=category,
                existing_titles=existing_titles,
            )
            progress.update(task, completed=True)
            console.print(f"[green]Found {len(keywords)} keywords[/green]")

            # Step 4: Filter keywords
            qualified = self.keyword_service.filter_keywords(
                keywords, min_volume=min_vol, max_kd=max_difficulty
            )
            qualified = self.keyword_service.rank_keywords(qualified)
            console.print(f"[green]{len(qualified)} keywords passed filters[/green]")

            if not qualified:
                console.print("[red]No qualified keywords found[/red]")
                return None

            # Step 5: Generate topics
            task = progress.add_task("Generating topics...", total=None)
            topics = await self.content_planner.generate_topics_from_keywords(
                qualified_keywords=qualified,
                category=category,
                count=5,
            )
            progress.update(task, completed=True)

            if not topics:
                console.print("[red]Failed to generate topics[/red]")
                return None

        # Step 6: Select topic
        if interactive and topic_selector is None:
            topic = await self._interactive_topic_selection(topics)
        elif topic_selector:
            topic = topic_selector(topics)
        else:
            topic = self.content_planner.select_best_topic(topics, existing_titles)

        if not topic:
            console.print("[red]No topic selected[/red]")
            return None

        console.print(f"\n[bold]Selected topic:[/bold] {topic.get('title')}")

        # Get search intent
        search_intent = topic.get("search_intent", "informational")

        # Create keyword group
        keyword_group = self.content_planner.create_keyword_group_from_topic(topic, qualified)

        # Steps 7-10: Generate article, images, cross-links, output
        return await self._generate_full_article(
            topic=topic,
            keyword_group=keyword_group,
            search_intent=search_intent,
            category=category,
            scraped_content=scraped,
        )

    async def run_alternative_workflow(
        self,
        category: str,
        interactive: bool = True,
    ) -> Article | None:
        """
        Run the alternative workflow:
        1. Scrape existing titles
        2. GPT suggests unique topic
        3. DataForSEO generates keywords for topic
        4. Continue with article generation
        """
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # Step 1: Scrape existing content
            task = progress.add_task("Scraping existing content...", total=None)
            scraped = await self._scrape_or_load(category)
            existing_titles = scraped.titles if scraped else []
            progress.update(task, completed=True)

            # Step 2-3: Get topic and keywords
            task = progress.add_task("Generating topic and keywords...", total=None)
            topic, keywords = await self.keyword_service.alternative_workflow(
                category=category,
                existing_titles=existing_titles,
            )
            progress.update(task, completed=True)

        console.print(f"\n[bold]Suggested topic:[/bold] {topic.get('title')}")
        console.print(f"[dim]Keywords: {', '.join(kw.keyword for kw in keywords[:5])}[/dim]")

        if interactive:
            if not self._confirm("Proceed with this topic?"):
                return None

        # Create keyword group
        primary = keywords[0] if keywords else Keyword(keyword=topic.get("primary_keyword", ""))
        primary.is_primary = True

        keyword_group = KeywordGroup(
            primary_keyword=primary,
            secondary_keywords=keywords[1:4] if len(keywords) > 1 else [],
            topic=topic.get("title", ""),
        )

        return await self._generate_full_article(
            topic=topic,
            keyword_group=keyword_group,
            search_intent=topic.get("search_intent", "informational"),
            category=category,
            scraped_content=scraped,
        )

    async def generate_single_article(
        self,
        topic: str,
        keywords: list[str],
        search_intent: str,
        category: str,
    ) -> Article | None:
        """Generate a single article with provided parameters."""
        # Load existing content for cross-linking
        scraped = await self._scrape_or_load(category)

        # Create keyword objects
        primary = Keyword(keyword=keywords[0] if keywords else topic, is_primary=True)
        secondary = [Keyword(keyword=kw) for kw in keywords[1:]]

        keyword_group = KeywordGroup(
            primary_keyword=primary,
            secondary_keywords=secondary,
            topic=topic,
        )

        topic_data = {
            "title": topic,
            "primary_keyword": primary.keyword,
            "secondary_keywords": [kw.keyword for kw in secondary],
            "search_intent": search_intent,
        }

        return await self._generate_full_article(
            topic=topic_data,
            keyword_group=keyword_group,
            search_intent=search_intent,
            category=category,
            scraped_content=scraped,
        )

    async def _generate_full_article(
        self,
        topic: dict,
        keyword_group: KeywordGroup,
        search_intent: str,
        category: str,
        scraped_content: ScrapedContent | None,
    ) -> Article:
        """Generate a complete article with images and cross-links."""
        existing_posts = scraped_content.to_link_references() if scraped_content else []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # Generate article content
            task = progress.add_task("Generating article content...", total=None)
            article = await self.content_generator.generate_article(
                topic=topic.get("title", keyword_group.topic),
                primary_keyword=keyword_group.primary_keyword.keyword,
                secondary_keywords=[kw.keyword for kw in keyword_group.secondary_keywords],
                search_intent=search_intent,
                category=category,
                existing_posts=existing_posts[:10],
            )
            progress.update(task, completed=True)
            console.print(f"[green]Generated {article.metadata.word_count} words[/green]")

            # Generate images
            task = progress.add_task("Generating images...", total=None)
            images = await self.image_generator.generate_images_for_article(article)
            featured_image = await self.image_generator.generate_featured_image(article)
            all_images = [featured_image] + images
            progress.update(task, completed=True)
            console.print(f"[green]Generated {len(all_images)} images[/green]")

            # Add cross-links
            task = progress.add_task("Adding cross-links...", total=None)
            if scraped_content:
                article = self.cross_linker.add_cross_links(article, scraped_content)
            progress.update(task, completed=True)
            console.print(f"[green]Added {len(article.internal_links)} internal links[/green]")

            # Update article with images
            article.images = [str(img.file_path) for img in all_images if img.file_path]

            # Write output files
            task = progress.add_task("Writing output files...", total=None)
            md_path = await self.markdown_writer.write_article(article, all_images)
            json_path = await self.json_writer.write_article(article, all_images, keyword_group)
            progress.update(task, completed=True)

            console.print(f"\n[bold green]Article generated successfully![/bold green]")
            console.print(f"  Markdown: {md_path}")
            console.print(f"  JSON: {json_path}")

            # Update category post count
            self.category_manager.increment_post_count(category)

        return article

    async def _scrape_or_load(self, category: str) -> ScrapedContent | None:
        """Load cached content or scrape fresh."""
        # Try to load cached
        cached = self.scraper.load_scraped_content(
            category=category,
            data_dir=self.settings.existing_content_dir,
        )

        if cached:
            return cached

        # Scrape fresh
        scraped = await self.scraper.scrape_category(category)
        await self.scraper.save_scraped_content(
            content=scraped,
            output_dir=self.settings.existing_content_dir,
        )

        return scraped

    async def _interactive_topic_selection(self, topics: list[dict]) -> dict | None:
        """Interactive topic selection."""
        console.print("\n[bold]Available topics:[/bold]")
        for i, topic in enumerate(topics, 1):
            console.print(f"  {i}. {topic.get('title')}")
            console.print(f"     [dim]Keyword: {topic.get('primary_keyword')}[/dim]")
            console.print(f"     [dim]Intent: {topic.get('search_intent')}[/dim]")

        while True:
            choice = console.input("\nSelect topic number (or 'q' to quit): ")
            if choice.lower() == 'q':
                return None

            try:
                idx = int(choice) - 1
                if 0 <= idx < len(topics):
                    return topics[idx]
            except ValueError:
                pass

            console.print("[red]Invalid choice. Try again.[/red]")

    def _confirm(self, message: str) -> bool:
        """Prompt for confirmation."""
        response = console.input(f"{message} [y/N]: ")
        return response.lower() in ('y', 'yes')


def create_workflow(settings: Settings) -> WorkflowOrchestrator:
    """Factory function to create workflow orchestrator."""
    return WorkflowOrchestrator(settings=settings)
