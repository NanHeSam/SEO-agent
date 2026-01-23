"""Main workflow orchestration for SEO article generation."""

from pathlib import Path
from typing import Callable

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from seo_agent.clients.dataforseo_client import DataForSEOClient, create_dataforseo_client
from seo_agent.clients.openai_client import OpenAIClient, create_openai_client
from seo_agent.config import Settings
from seo_agent.core.content_planner import ContentPlanner
from seo_agent.core.workflow_logger import WorkflowLogger, create_workflow_logger, set_logger
from seo_agent.models.article import Article
from seo_agent.models.blog_post import BlogCache
from seo_agent.models.image import GeneratedImage
from seo_agent.models.keyword import Keyword, KeywordGroup
from seo_agent.output.json_writer import JSONWriter
from seo_agent.output.markdown_writer import MarkdownWriter
from seo_agent.services.blog_api_client import BlogApiClient, create_blog_api_client
from seo_agent.services.content_generator import ContentGeneratorService
from seo_agent.services.cross_linker import CrossLinkerService
from seo_agent.services.image_generator import ImageGeneratorService
from seo_agent.services.keyword_research import KeywordResearchService


console = Console()


class WorkflowOrchestrator:
    """Orchestrates the full SEO article generation workflow."""

    def __init__(self, settings: Settings, enable_logging: bool = True):
        self.settings = settings
        settings.ensure_directories()

        # Initialize workflow logger
        self.logger: WorkflowLogger | None = None
        if enable_logging:
            self.logger = create_workflow_logger(logs_dir=settings.logs_dir)
            set_logger(self.logger)
            console.print(f"[dim]Workflow log: {self.logger.log_file}[/dim]")

        # Initialize clients
        self.openai_client = create_openai_client(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            image_model=settings.openai_image_model,
        )
        self.dataforseo_client = create_dataforseo_client(
            api_credentials=settings.dataforseo_api_credentials,
        )

        # Initialize blog API client
        self.blog_api = create_blog_api_client(
            base_url=settings.blog_api_url,
            cache_file=settings.blog_cache_file,
        )

        # Initialize services
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

        # Initialize writers
        self.markdown_writer = MarkdownWriter(output_dir=settings.generated_articles_dir)
        self.json_writer = JSONWriter(output_dir=settings.generated_articles_dir)

    async def run_original_workflow(
        self,
        interactive: bool = True,
        min_volume: int | None = None,
        max_kd: float | None = None,
        topic_selector: Callable[[list[dict]], dict] | None = None,
    ) -> Article | None:
        """
        Run the original workflow:
        1. Load existing content from API
        2. GPT suggests keywords
        3. DataForSEO validates keywords
        4. Filter by volume/KD
        5. Generate topics
        6. User selects topic + provides intent
        7. Generate article with images and cross-links
        """
        min_vol = min_volume or self.settings.default_min_volume
        max_difficulty = max_kd or self.settings.default_max_kd

        # Log workflow start
        if self.logger:
            self.logger.log_workflow_start("original_workflow", {
                "min_volume": min_vol,
                "max_kd": max_difficulty,
                "interactive": interactive,
            })

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # Step 1: Load existing content from API
            task = progress.add_task("Loading existing content...", total=None)
            cache = await self._load_existing_posts()
            existing_titles = [p.title for p in cache.posts] if cache else []
            progress.update(task, completed=True)
            console.print(f"[green]Found {len(existing_titles)} existing posts[/green]")

            # Log existing posts
            if self.logger:
                self.logger.log_existing_posts_loaded(len(existing_titles), existing_titles)

            # Step 2-3: Get and validate keywords
            task = progress.add_task("Researching keywords...", total=None)
            keywords = await self.keyword_service.original_workflow(
                existing_titles=existing_titles,
            )
            progress.update(task, completed=True)
            console.print(f"[green]Found {len(keywords)} keywords[/green]")

            # Step 4: Filter keywords
            qualified = self.keyword_service.filter_keywords(
                keywords, min_volume=min_vol, max_kd=max_difficulty
            )

            # Log filtering results
            if self.logger:
                all_kw_data = [
                    {
                        "keyword": kw.keyword,
                        "search_volume": kw.metrics.search_volume,
                        "keyword_difficulty": kw.metrics.keyword_difficulty,
                    }
                    for kw in keywords
                ]
                qualified_kw_data = [
                    {
                        "keyword": kw.keyword,
                        "search_volume": kw.metrics.search_volume,
                        "keyword_difficulty": kw.metrics.keyword_difficulty,
                    }
                    for kw in qualified
                ]
                self.logger.log_keyword_filtering(
                    all_kw_data, qualified_kw_data, min_vol, max_difficulty
                )

            qualified = self.keyword_service.rank_keywords(qualified)
            console.print(f"[green]{len(qualified)} keywords passed filters[/green]")

            # Log ranking results
            if self.logger:
                ranked_kw_data = [
                    {
                        "keyword": kw.keyword,
                        "search_volume": kw.metrics.search_volume,
                        "keyword_difficulty": kw.metrics.keyword_difficulty,
                    }
                    for kw in qualified
                ]
                self.logger.log_keyword_ranking(ranked_kw_data)

            if not qualified:
                console.print("[red]No qualified keywords found[/red]")
                if self.logger:
                    self.logger.log_workflow_end("original_workflow", False, {
                        "reason": "No qualified keywords found"
                    })
                return None

            # Step 5: Generate topics
            task = progress.add_task("Generating topics...", total=None)
            topics = await self.content_planner.generate_topics_from_keywords(
                qualified_keywords=qualified,
                count=5,
            )
            progress.update(task, completed=True)

            # Log generated topics
            if self.logger and topics:
                self.logger.log_topics_generated(topics)

            if not topics:
                console.print("[red]Failed to generate topics[/red]")
                if self.logger:
                    self.logger.log_workflow_end("original_workflow", False, {
                        "reason": "Failed to generate topics"
                    })
                return None

        # Step 6: Select topic
        if interactive and topic_selector is None:
            topic = await self._interactive_topic_selection(topics)
            selection_method = "interactive"
        elif topic_selector:
            topic = topic_selector(topics)
            selection_method = "custom_selector"
        else:
            topic = self.content_planner.select_best_topic(topics, existing_titles)
            selection_method = "auto"

        if not topic:
            console.print("[red]No topic selected[/red]")
            if self.logger:
                self.logger.log_workflow_end("original_workflow", False, {
                    "reason": "No topic selected"
                })
            return None

        # Log selected topic
        if self.logger:
            self.logger.log_topic_selected(topic, selection_method)

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
            category="",
            blog_cache=cache,
        )

    async def run_alternative_workflow(
        self,
        interactive: bool = True,
    ) -> Article | None:
        """
        Run the alternative workflow:
        1. Load existing titles from API
        2. GPT suggests unique topic
        3. DataForSEO generates keywords for topic
        4. Continue with article generation
        """
        # Log workflow start
        if self.logger:
            self.logger.log_workflow_start("alternative_workflow", {
                "interactive": interactive,
            })

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # Step 1: Load existing content from API
            task = progress.add_task("Loading existing content...", total=None)
            cache = await self._load_existing_posts()
            existing_titles = [p.title for p in cache.posts] if cache else []
            progress.update(task, completed=True)

            # Log existing posts
            if self.logger:
                self.logger.log_existing_posts_loaded(len(existing_titles), existing_titles)

            # Step 2-3: Get topic and keywords
            task = progress.add_task("Generating topic and keywords...", total=None)
            topic, keywords = await self.keyword_service.alternative_workflow(
                existing_titles=existing_titles,
            )
            progress.update(task, completed=True)

        console.print(f"\n[bold]Suggested topic:[/bold] {topic.get('title')}")
        console.print(f"[dim]Keywords: {', '.join(kw.keyword for kw in keywords[:5])}[/dim]")

        # Log topic and keywords from alternative workflow
        if self.logger:
            self.logger.log_topics_generated([topic])
            if keywords:
                kw_data = [
                    {
                        "keyword": kw.keyword,
                        "search_volume": kw.metrics.search_volume,
                        "keyword_difficulty": kw.metrics.keyword_difficulty,
                    }
                    for kw in keywords
                ]
                self.logger.log_keyword_ranking(kw_data)

        if interactive:
            if not self._confirm("Proceed with this topic?"):
                if self.logger:
                    self.logger.log_workflow_end("alternative_workflow", False, {
                        "reason": "User declined topic"
                    })
                return None

        # Log topic selected
        if self.logger:
            self.logger.log_topic_selected(topic, "alternative_workflow")

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
            category="",
            blog_cache=cache,
        )

    async def generate_single_article(
        self,
        topic: str,
        keywords: list[str],
        search_intent: str,
        category: str = "",
    ) -> Article | None:
        """Generate a single article with provided parameters."""
        # Load existing content for cross-linking
        cache = await self._load_existing_posts()

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
            blog_cache=cache,
        )

    async def _generate_full_article(
        self,
        topic: dict,
        keyword_group: KeywordGroup,
        search_intent: str,
        category: str,
        blog_cache: BlogCache | None,
    ) -> Article:
        """Generate a complete article with images and cross-links."""
        # Convert API posts to cross-link format
        existing_posts = []
        if blog_cache:
            existing_posts = [
                {"title": p.title, "url": p.url}
                for p in blog_cache.posts
            ]

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

            # Log article generation
            if self.logger:
                self.logger.log_article_generated({
                    "title": article.metadata.title,
                    "word_count": article.metadata.word_count,
                    "primary_keyword": article.metadata.primary_keyword,
                    "secondary_keywords": article.metadata.secondary_keywords,
                    "search_intent": article.metadata.search_intent,
                    "meta_description": article.metadata.meta_description,
                })

            # Generate images
            task = progress.add_task("Generating images...", total=None)
            images = await self.image_generator.generate_images_for_article(article)
            featured_image = await self.image_generator.generate_featured_image(article)
            all_images = [featured_image] + images
            progress.update(task, completed=True)
            console.print(f"[green]Generated {len(all_images)} images[/green]")

            # Log images generated
            if self.logger:
                images_data = [
                    {"file_path": str(img.file_path), "prompt": img.prompt}
                    for img in all_images if img.file_path
                ]
                self.logger.log_images_generated(images_data)

            # Add cross-links (using blog cache posts)
            task = progress.add_task("Adding cross-links...", total=None)
            if blog_cache:
                # Convert BlogCache to format expected by cross_linker
                from seo_agent.models.blog_post import ScrapedContent, ExistingPost
                scraped = ScrapedContent(
                    category=category,
                    posts=[
                        ExistingPost(
                            title=p.title,
                            url=p.url,
                            excerpt=p.summary,
                        )
                        for p in blog_cache.posts
                    ],
                )
                article = self.cross_linker.add_cross_links(article, scraped)
            progress.update(task, completed=True)
            console.print(f"[green]Added {len(article.internal_links)} internal links[/green]")

            # Log cross-links
            if self.logger:
                links_data = [
                    {"title": link.title, "url": link.url, "anchor_text": link.anchor_text}
                    for link in article.internal_links
                ]
                self.logger.log_cross_links_added(links_data)

            # Update article with images
            article.images = [str(img.file_path) for img in all_images if img.file_path]

            # Write output files
            task = progress.add_task("Writing output files...", total=None)
            md_path = await self.markdown_writer.write_article(article, all_images)
            json_path = await self.json_writer.write_article(article, all_images, keyword_group)
            progress.update(task, completed=True)

            # Log output files
            if self.logger:
                self.logger.log_output_files(str(md_path), str(json_path))
                self.logger.log_workflow_end("article_generation", True, {
                    "title": article.metadata.title,
                    "word_count": article.metadata.word_count,
                    "images_count": len(all_images),
                    "cross_links_count": len(article.internal_links),
                })

            console.print(f"\n[bold green]Article generated successfully![/bold green]")
            console.print(f"  Markdown: {md_path}")
            console.print(f"  JSON: {json_path}")

        return article

    async def _load_existing_posts(
        self,
        force: bool = False,
        include_content: bool = False,
    ) -> BlogCache | None:
        """Load existing posts from API cache or fetch fresh."""
        if not force and self.blog_api.is_cache_valid(self.settings.blog_cache_max_age_hours):
            cache = self.blog_api.load_cache()
            if cache:
                # If we need content but cache doesn't have it, fetch fresh
                if include_content and not cache.include_content:
                    pass  # Fall through to fetch
                else:
                    console.print(f"[dim]Loaded {len(cache.posts)} cached posts[/dim]")
                    return cache

        # Fetch fresh from API
        console.print(f"[dim]Fetching posts from API: {self.blog_api.base_url}[/dim]")
        cache = await self.blog_api.get_posts(
            force=True,
            include_content=include_content,
            max_age_hours=self.settings.blog_cache_max_age_hours,
        )
        console.print(f"[dim]Fetched {len(cache.posts)} posts from API[/dim]")

        if cache.posts:
            for post in cache.posts[:5]:
                console.print(f"[dim]  - {post.title}[/dim]")
            if len(cache.posts) > 5:
                console.print(f"[dim]  ... and {len(cache.posts) - 5} more[/dim]")

        return cache

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
