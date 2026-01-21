"""CLI commands for SEO Agent using Typer."""

import asyncio
from enum import Enum
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from seo_agent.config import get_settings
from seo_agent.core.category_manager import CategoryManager
from seo_agent.core.workflow import create_workflow
from seo_agent.services.scraper import BlogScraper


app = typer.Typer(
    name="seo-agent",
    help="SEO article generation automation CLI tool",
    no_args_is_help=True,
)

categories_app = typer.Typer(help="Category management commands")
app.add_typer(categories_app, name="categories")

console = Console()


class WorkflowMode(str, Enum):
    """Workflow mode selection."""
    original = "original"
    alternative = "alternative"


# --- Category Commands ---


@categories_app.command("list")
def categories_list():
    """List all categories."""
    settings = get_settings()
    manager = CategoryManager(categories_file=settings.categories_file)

    categories = manager.list_categories()

    if not categories:
        console.print("[yellow]No categories found. Add one with 'categories add'[/yellow]")
        return

    table = Table(title="Blog Categories")
    table.add_column("Name", style="cyan")
    table.add_column("Display Name", style="green")
    table.add_column("Posts", justify="right")
    table.add_column("Description")

    for cat in categories:
        table.add_row(
            cat.name,
            cat.display_name,
            str(cat.post_count),
            cat.description[:50] + "..." if len(cat.description) > 50 else cat.description,
        )

    console.print(table)


@categories_app.command("add")
def categories_add(
    name: str = typer.Argument(..., help="Category name/slug"),
    display_name: Optional[str] = typer.Option(None, "--display", "-d", help="Display name"),
    description: Optional[str] = typer.Option(None, "--desc", help="Category description"),
):
    """Add a new category."""
    settings = get_settings()
    manager = CategoryManager(categories_file=settings.categories_file)

    try:
        category = manager.add_category(
            name=name,
            display_name=display_name or "",
            description=description or "",
        )
        console.print(f"[green]Added category:[/green] {category.name} ({category.display_name})")
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@categories_app.command("remove")
def categories_remove(
    name: str = typer.Argument(..., help="Category name to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Remove a category."""
    settings = get_settings()
    manager = CategoryManager(categories_file=settings.categories_file)

    if not manager.category_exists(name):
        console.print(f"[red]Category '{name}' not found[/red]")
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm(f"Remove category '{name}'?")
        if not confirm:
            raise typer.Abort()

    if manager.remove_category(name):
        console.print(f"[green]Removed category:[/green] {name}")
    else:
        console.print(f"[red]Failed to remove category[/red]")


# --- Scrape Command ---


@app.command()
def scrape(
    category: str = typer.Argument(..., help="Category to scrape"),
    force: bool = typer.Option(False, "--force", "-f", help="Force fresh scrape"),
    max_posts: int = typer.Option(50, "--max", "-m", help="Maximum posts to scrape"),
):
    """Scrape existing blog content for a category."""
    settings = get_settings()
    scraper = BlogScraper(base_url=settings.target_blog_url)

    async def run():
        # Check for cached content
        if not force:
            cached = scraper.load_scraped_content(
                category=category,
                data_dir=settings.existing_content_dir,
            )
            if cached:
                console.print(f"[yellow]Using cached content ({len(cached.posts)} posts)[/yellow]")
                console.print("[dim]Use --force to scrape fresh[/dim]")
                return cached

        console.print(f"[cyan]Scraping {category} from {settings.target_blog_url}...[/cyan]")

        scraped = await scraper.scrape_category(category, max_posts=max_posts)
        await scraper.save_scraped_content(
            content=scraped,
            output_dir=settings.existing_content_dir,
        )

        console.print(f"[green]Scraped {len(scraped.posts)} posts[/green]")

        # Show titles
        if scraped.posts:
            console.print("\n[bold]Posts found:[/bold]")
            for post in scraped.posts[:10]:
                console.print(f"  - {post.title}")
            if len(scraped.posts) > 10:
                console.print(f"  ... and {len(scraped.posts) - 10} more")

        return scraped

    asyncio.run(run())


# --- Research Command ---


@app.command()
def research(
    category: str = typer.Argument(..., help="Category to research"),
    workflow: WorkflowMode = typer.Option(
        WorkflowMode.original, "--workflow", "-w", help="Workflow type"
    ),
    min_volume: int = typer.Option(5000, "--min-volume", help="Minimum search volume"),
    max_kd: int = typer.Option(30, "--max-kd", help="Maximum keyword difficulty"),
):
    """Research keywords for a category."""
    settings = get_settings()
    wf = create_workflow(settings)

    async def run():
        # Load existing content
        scraped = await wf._scrape_or_load(category)
        existing_titles = scraped.titles if scraped else []

        console.print(f"[cyan]Running {workflow.value} workflow...[/cyan]")

        if workflow == WorkflowMode.original:
            keywords = await wf.keyword_service.original_workflow(
                category=category,
                existing_titles=existing_titles,
            )

            # Filter
            qualified = wf.keyword_service.filter_keywords(
                keywords, min_volume=min_volume, max_kd=max_kd
            )
            qualified = wf.keyword_service.rank_keywords(qualified)

            console.print(f"\n[green]Found {len(keywords)} keywords, {len(qualified)} qualified[/green]")

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
                category=category,
                existing_titles=existing_titles,
            )

            console.print(f"\n[bold]Suggested Topic:[/bold] {topic.get('title')}")
            console.print(f"[dim]Primary keyword: {topic.get('primary_keyword')}[/dim]")
            console.print(f"[dim]Intent: {topic.get('search_intent')}[/dim]")

            if keywords:
                console.print(f"\n[green]Generated {len(keywords)} keywords[/green]")
                for kw in keywords[:10]:
                    console.print(f"  - {kw.keyword} (vol: {kw.metrics.search_volume})")

    asyncio.run(run())


# --- Generate Command ---


@app.command()
def generate(
    topic: str = typer.Argument(..., help="Article topic/title"),
    keywords: str = typer.Option(..., "--keywords", "-k", help="Comma-separated keywords"),
    intent: str = typer.Option(
        "informational", "--intent", "-i", help="Search intent (informational/commercial/transactional)"
    ),
    category: str = typer.Option(..., "--category", "-c", help="Blog category"),
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
    console.print(f"[dim]Category: {category}[/dim]\n")

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
    category: str = typer.Argument(..., help="Category to generate content for"),
    mode: WorkflowMode = typer.Option(
        WorkflowMode.original, "--mode", "-m", help="Workflow mode"
    ),
    interactive: bool = typer.Option(True, "--interactive/--no-interactive", help="Interactive mode"),
    min_volume: int = typer.Option(5000, "--min-volume", help="Minimum search volume"),
    max_kd: int = typer.Option(30, "--max-kd", help="Maximum keyword difficulty"),
):
    """Run full automated workflow."""
    settings = get_settings()

    # Ensure category exists
    manager = CategoryManager(categories_file=settings.categories_file)
    if not manager.category_exists(category):
        console.print(f"[yellow]Category '{category}' not found. Creating it...[/yellow]")
        manager.add_category(category)

    wf = create_workflow(settings)

    console.print(f"\n[bold]Running {mode.value} workflow for '{category}'[/bold]\n")

    async def run():
        if mode == WorkflowMode.original:
            article = await wf.run_original_workflow(
                category=category,
                interactive=interactive,
                min_volume=min_volume,
                max_kd=max_kd,
            )
        else:
            article = await wf.run_alternative_workflow(
                category=category,
                interactive=interactive,
            )

        if not article:
            console.print("[yellow]No article generated[/yellow]")
            raise typer.Exit(1)

    asyncio.run(run())


# --- Entry Point ---


def main():
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
