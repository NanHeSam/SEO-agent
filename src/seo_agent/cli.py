"""CLI commands for SEO Agent using Typer."""

import asyncio
from enum import Enum
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from seo_agent.config import get_settings
from seo_agent.core.workflow import create_workflow
from seo_agent.clients.dataforseo_client import DataForSEOError
from seo_agent.services.blog_api_client import create_blog_api_client


app = typer.Typer(
    name="seo-agent",
    help="SEO article generation automation CLI tool",
    no_args_is_help=True,
)

console = Console()


class WorkflowMode(str, Enum):
    """Workflow mode selection."""
    original = "original"
    alternative = "alternative"


# --- Scrape Command ---


@app.command()
def scrape(
    force: bool = typer.Option(False, "--force", "-f", help="Force fresh fetch"),
    include_content: bool = typer.Option(False, "--include-content", help="Cache full content"),
):
    """Fetch blog posts from the API."""
    settings = get_settings()
    blog_api = create_blog_api_client(
        base_url=settings.blog_api_url,
        cache_file=settings.blog_cache_file,
    )

    async def run():
        # Check for cached content
        if not force and blog_api.is_cache_valid(settings.blog_cache_max_age_hours):
            cached = blog_api.load_cache()
            if cached:
                # If we need content but cache doesn't have it, continue to fetch
                if include_content and not cached.include_content:
                    console.print("[yellow]Cache doesn't include content, fetching fresh...[/yellow]")
                else:
                    console.print(f"[yellow]Using cached content ({len(cached.posts)} posts)[/yellow]")
                    console.print("[dim]Use --force to fetch fresh[/dim]")
                    _display_posts(cached.posts)
                    return cached

        console.print(f"[cyan]Fetching posts from {settings.blog_api_url}...[/cyan]")

        cache = await blog_api.get_posts(
            force=True,
            include_content=include_content,
            max_age_hours=settings.blog_cache_max_age_hours,
        )

        console.print(f"[green]Fetched {len(cache.posts)} posts[/green]")
        if include_content:
            console.print("[dim]Content included in cache[/dim]")

        _display_posts(cache.posts)
        return cache

    asyncio.run(run())


def _display_posts(posts: list) -> None:
    """Display a list of posts."""
    if posts:
        console.print("\n[bold]Posts found:[/bold]")
        for post in posts[:10]:
            console.print(f"  - {post.title}")
        if len(posts) > 10:
            console.print(f"  ... and {len(posts) - 10} more")


# --- Research Command ---


@app.command()
def research(
    workflow: WorkflowMode = typer.Option(
        WorkflowMode.original, "--workflow", "-w", help="Workflow type"
    ),
    min_volume: int = typer.Option(5000, "--min-volume", help="Minimum search volume"),
    max_kd: int = typer.Option(30, "--max-kd", help="Maximum keyword difficulty"),
):
    """Research keywords based on existing blog content."""
    settings = get_settings()
    wf = create_workflow(settings)

    async def run():
        try:
            # Load existing content from API cache
            cache = await wf._load_existing_posts()
            existing_titles = [p.title for p in cache.posts] if cache else []

            console.print(f"[cyan]Running {workflow.value} workflow...[/cyan]")
            console.print(f"[dim]Analyzing {len(existing_titles)} existing posts[/dim]")

            if workflow == WorkflowMode.original:
                keywords = await wf.keyword_service.original_workflow(
                    category="",  # No category needed
                    existing_titles=existing_titles,
                )

                # Filter
                qualified = wf.keyword_service.filter_keywords(
                    keywords, min_volume=min_volume, max_kd=max_kd
                )
                qualified = wf.keyword_service.rank_keywords(qualified)

                console.print(
                    f"\n[green]Found {len(keywords)} keywords, {len(qualified)} qualified[/green]"
                )

                if qualified:
                    table = Table(title="Qualified Keywords")
                    table.add_column("Keyword", style="cyan")
                    table.add_column("Volume", justify="right")
                    table.add_column("KD", justify="right")
                    table.add_column("CPC", justify="right")

                    for kw in qualified[:15]:
                        table.add_row(
                            kw.keyword,
                            str(kw.metrics.search_volume),
                            f"{kw.metrics.keyword_difficulty:.1f}",
                            f"${kw.metrics.cpc:.2f}",
                        )

                    console.print(table)

            else:  # alternative workflow
                topic, keywords = await wf.keyword_service.alternative_workflow(
                    category="",  # No category needed
                    existing_titles=existing_titles,
                )

                console.print(f"\n[bold]Suggested Topic:[/bold] {topic.get('title')}")
                console.print(f"[dim]Primary keyword: {topic.get('primary_keyword')}[/dim]")
                console.print(f"[dim]Intent: {topic.get('search_intent')}[/dim]")

                if keywords:
                    console.print(f"\n[green]Generated {len(keywords)} keywords[/green]")
                    for kw in keywords[:10]:
                        console.print(f"  - {kw.keyword} (vol: {kw.metrics.search_volume})")
        except DataForSEOError as exc:
            console.print("[red]DataForSEO error while researching keywords.[/red]")
            console.print(f"[dim]{exc}[/dim]")
            if exc.status_message and "fund" in exc.status_message.lower():
                console.print("[yellow]Hint: Check your DataForSEO balance and billing status.[/yellow]")
            if wf.logger:
                wf.logger.log_error("dataforseo_research", exc)
            raise typer.Exit(1)

    asyncio.run(run())


# --- Generate Command ---


@app.command()
def generate(
    topic: str = typer.Argument(..., help="Article topic/title"),
    keywords: str = typer.Option(..., "--keywords", "-k", help="Comma-separated keywords"),
    intent: str = typer.Option(
        "informational", "--intent", "-i", help="Search intent (informational/commercial/transactional)"
    ),
    category: str = typer.Option("", "--category", "-c", help="Blog category (optional)"),
):
    """Generate a single SEO article."""
    settings = get_settings()
    wf = create_workflow(settings)

    keyword_list = [k.strip() for k in keywords.split(",") if k.strip()]

    if not keyword_list:
        console.print("[red]At least one keyword is required[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold]Generating article:[/bold] {topic}")
    console.print(f"[dim]Keywords: {', '.join(keyword_list)}[/dim]")
    console.print(f"[dim]Intent: {intent}[/dim]")
    if category:
        console.print(f"[dim]Category: {category}[/dim]")

    async def run():
        article = await wf.generate_single_article(
            topic=topic,
            keywords=keyword_list,
            search_intent=intent,
            category=category,
        )

        if article:
            console.print(f"\n[bold green]Article generated![/bold green]")
            console.print(f"  Title: {article.metadata.title}")
            console.print(f"  Words: {article.metadata.word_count}")
            console.print(f"  Images: {len(article.images)}")
            console.print(f"  Links: {len(article.internal_links)}")

    asyncio.run(run())


# --- Workflow Command ---


@app.command()
def workflow(
    mode: WorkflowMode = typer.Option(
        WorkflowMode.original, "--mode", "-m", help="Workflow mode"
    ),
    interactive: bool = typer.Option(True, "--interactive/--no-interactive", help="Interactive mode"),
    min_volume: int = typer.Option(5000, "--min-volume", help="Minimum search volume"),
    max_kd: int = typer.Option(30, "--max-kd", help="Maximum keyword difficulty"),
):
    """Run full automated workflow."""
    settings = get_settings()
    wf = create_workflow(settings)

    console.print(f"\n[bold]Running {mode.value} workflow[/bold]\n")

    async def run():
        try:
            if mode == WorkflowMode.original:
                article = await wf.run_original_workflow(
                    interactive=interactive,
                    min_volume=min_volume,
                    max_kd=max_kd,
                )
            else:
                article = await wf.run_alternative_workflow(
                    interactive=interactive,
                )

            if not article:
                console.print("[yellow]No article generated[/yellow]")
                raise typer.Exit(1)
        except DataForSEOError as exc:
            console.print("[red]DataForSEO error during workflow.[/red]")
            console.print(f"[dim]{exc}[/dim]")
            if exc.status_message and "fund" in exc.status_message.lower():
                console.print("[yellow]Hint: Check your DataForSEO balance and billing status.[/yellow]")
            if wf.logger:
                wf.logger.log_error("dataforseo_workflow", exc)
                wf.logger.log_workflow_end(f"{mode.value}_workflow", False, {
                    "reason": "DataForSEO error",
                    "message": str(exc),
                })
            raise typer.Exit(1)

    asyncio.run(run())


# --- Suggest Command ---


@app.command()
def suggest(
    include_content: bool = typer.Option(False, "--include-content", help="Include full content for better suggestions"),
    force: bool = typer.Option(False, "--force", "-f", help="Force fresh API fetch"),
    count: int = typer.Option(10, "--count", "-n", help="Number of suggestions"),
    auto_generate: bool = typer.Option(False, "--auto-generate", "-g", help="Auto-generate article from selection"),
):
    """Suggest new topics and keywords based on existing blog content."""
    settings = get_settings()
    blog_api = create_blog_api_client(
        base_url=settings.blog_api_url,
        cache_file=settings.blog_cache_file,
    )

    from seo_agent.clients.openai_client import create_openai_client
    openai_client = create_openai_client(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
    )

    async def run():
        # Step 1-2: Check cache or fetch fresh
        console.print("[cyan]Loading existing blog posts...[/cyan]")
        cache = await blog_api.get_posts(
            force=force,
            include_content=include_content,
            max_age_hours=settings.blog_cache_max_age_hours,
        )
        console.print(f"[green]Loaded {len(cache.posts)} posts[/green]")

        # Step 3: Prepare data for AI
        posts_data = []
        for post in cache.posts:
            post_dict = {
                "title": post.title,
                "summary": post.summary,
            }
            if include_content and post.content:
                post_dict["content"] = post.content
            posts_data.append(post_dict)

        # Step 4: Call OpenAI to analyze and suggest
        console.print("[cyan]Analyzing content and generating suggestions...[/cyan]")
        suggestions = await openai_client.suggest_topics_and_keywords(
            existing_posts=posts_data,
            suggestion_count=count,
        )

        # Step 5: Display results
        _display_suggestions(suggestions)

        # Step 6: Interactive selection (if auto-generate enabled)
        if auto_generate and suggestions.get("topic_ideas"):
            selected = _interactive_topic_selection(suggestions["topic_ideas"])
            if selected:
                console.print(f"\n[bold]Selected:[/bold] {selected['title']}")
                console.print("[cyan]Starting article generation workflow...[/cyan]")

                wf = create_workflow(settings)
                article = await wf.generate_single_article(
                    topic=selected["title"],
                    keywords=[selected.get("primary_keyword", "")] + selected.get("secondary_keywords", []),
                    search_intent=selected.get("search_intent", "informational"),
                    category="",
                )

                if article:
                    console.print(f"\n[bold green]Article generated![/bold green]")
                    console.print(f"  Title: {article.metadata.title}")
                    console.print(f"  Words: {article.metadata.word_count}")

    asyncio.run(run())


def _display_suggestions(suggestions: dict) -> None:
    """Display AI suggestions in formatted tables."""
    # Topic Ideas
    topic_ideas = suggestions.get("topic_ideas", [])
    if topic_ideas:
        console.print("\n[bold]Topic Ideas:[/bold]")
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("#", style="dim", width=3)
        table.add_column("Title", style="green")
        table.add_column("Primary Keyword", style="yellow")
        table.add_column("Intent")
        table.add_column("Rationale", width=40)

        for i, topic in enumerate(topic_ideas, 1):
            table.add_row(
                str(i),
                topic.get("title", "")[:50],
                topic.get("primary_keyword", ""),
                topic.get("search_intent", ""),
                topic.get("rationale", "")[:40] + "..." if len(topic.get("rationale", "")) > 40 else topic.get("rationale", ""),
            )
        console.print(table)

    # Keyword Suggestions
    keyword_suggestions = suggestions.get("keyword_suggestions", [])
    if keyword_suggestions:
        console.print("\n[bold]Keyword Suggestions:[/bold]")
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Keyword", style="green")
        table.add_column("Intent")
        table.add_column("Difficulty")
        table.add_column("Rationale", width=50)

        for kw in keyword_suggestions[:10]:
            table.add_row(
                kw.get("keyword", ""),
                kw.get("intent", ""),
                kw.get("difficulty_estimate", ""),
                kw.get("rationale", "")[:50],
            )
        console.print(table)

    # Content Gaps
    content_gaps = suggestions.get("content_gaps", [])
    if content_gaps:
        console.print("\n[bold]Content Gaps:[/bold]")
        for gap in content_gaps[:5]:
            priority = gap.get("priority", "medium")
            priority_color = {"high": "red", "medium": "yellow", "low": "green"}.get(priority, "white")
            console.print(f"  [{priority_color}][{priority.upper()}][/{priority_color}] {gap.get('gap', '')}")
            console.print(f"       [dim]Opportunity: {gap.get('opportunity', '')}[/dim]")


def _interactive_topic_selection(topics: list[dict]) -> dict | None:
    """Interactive topic selection."""
    console.print("\n[bold]Select a topic to generate:[/bold]")

    while True:
        choice = console.input("Enter topic number (or 'q' to quit): ")
        if choice.lower() == 'q':
            return None

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(topics):
                return topics[idx]
        except ValueError:
            pass

        console.print("[red]Invalid choice. Try again.[/red]")


# --- Entry Point ---


def main():
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
