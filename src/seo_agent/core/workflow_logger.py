"""Workflow logger for capturing intermediate steps."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class WorkflowLogger:
    """Logger for capturing workflow intermediate steps to a timestamped log file."""

    def __init__(self, logs_dir: Path | str = "logs"):
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # Create log file with timestamp
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        self.log_file = self.logs_dir / f"{timestamp}.log"
        self._initialized = False

    def _ensure_file(self) -> None:
        """Create log file with header if not yet initialized."""
        if not self._initialized:
            self._write_line("=" * 80)
            self._write_line(f"SEO Agent Workflow Log - {datetime.now().isoformat()}")
            self._write_line("=" * 80)
            self._write_line("")
            self._initialized = True

    def _write_line(self, line: str) -> None:
        """Write a line to the log file."""
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def _write_section(self, title: str, content: str | dict | list | None = None) -> None:
        """Write a titled section to the log."""
        self._ensure_file()
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._write_line(f"\n[{timestamp}] {title}")
        self._write_line("-" * 60)

        if content is not None:
            if isinstance(content, (dict, list)):
                self._write_line(json.dumps(content, indent=2, ensure_ascii=False, default=str))
            else:
                self._write_line(str(content))
        self._write_line("")

    def log_workflow_start(self, workflow_type: str, params: dict | None = None) -> None:
        """Log workflow start."""
        self._write_section(
            f"WORKFLOW START: {workflow_type}",
            params or {}
        )

    def log_workflow_end(self, workflow_type: str, success: bool, summary: dict | None = None) -> None:
        """Log workflow completion."""
        status = "SUCCESS" if success else "FAILED"
        self._write_section(
            f"WORKFLOW END: {workflow_type} - {status}",
            summary or {}
        )

    def log_existing_posts_loaded(self, count: int, titles: list[str]) -> None:
        """Log loaded existing posts."""
        self._write_section(
            f"EXISTING POSTS LOADED: {count} posts",
            {"count": count, "titles": titles}
        )

    def log_llm_call(
        self,
        operation: str,
        system_prompt: str,
        user_prompt: str,
        response: str | dict | list,
        model: str | None = None,
    ) -> None:
        """Log an LLM call with input and output."""
        self._write_section(f"LLM CALL: {operation}")

        if model:
            self._write_line(f"Model: {model}")
            self._write_line("")

        self._write_line("--- System Prompt ---")
        self._write_line(system_prompt)
        self._write_line("")

        self._write_line("--- User Prompt ---")
        self._write_line(user_prompt)
        self._write_line("")

        self._write_line("--- Response ---")
        if isinstance(response, (dict, list)):
            self._write_line(json.dumps(response, indent=2, ensure_ascii=False, default=str))
        else:
            self._write_line(str(response))
        self._write_line("")

    def log_keywords_suggested(self, keywords: list[str], source: str = "gpt") -> None:
        """Log keywords suggested by GPT or other source."""
        self._write_section(
            f"KEYWORDS SUGGESTED ({source.upper()}): {len(keywords)} keywords",
            keywords
        )

    def log_dataforseo_response(
        self,
        operation: str,
        keywords: list[str],
        response_data: dict[str, dict],
    ) -> None:
        """Log DataForSEO API response with keyword metrics."""
        self._write_section(f"DATAFORSEO API: {operation}")

        # Format as a table-like structure
        self._write_line(f"Keywords queried: {len(keywords)}")
        self._write_line(f"Results returned: {len(response_data)}")
        self._write_line("")

        self._write_line("--- Keyword Metrics ---")
        self._write_line(f"{'Keyword':<40} {'Volume':>10} {'KD':>6} {'CPC':>8} {'Competition':>12}")
        self._write_line("-" * 80)

        for kw, metrics in response_data.items():
            volume = metrics.get("search_volume") or 0
            kd = metrics.get("keyword_difficulty") or 0
            cpc = metrics.get("cpc") or 0
            comp = metrics.get("competition_level", metrics.get("competition", ""))
            self._write_line(f"{kw[:40]:<40} {volume:>10} {kd:>6.1f} {cpc:>8.2f} {str(comp):>12}")

        self._write_line("")

    def log_keyword_filtering(
        self,
        all_keywords: list[dict],
        qualified_keywords: list[dict],
        min_volume: int,
        max_kd: float,
    ) -> None:
        """Log keyword filtering results."""
        self._write_section(
            f"KEYWORD FILTERING: {len(qualified_keywords)}/{len(all_keywords)} passed"
        )

        self._write_line(f"Filter criteria: min_volume >= {min_volume}, max_kd <= {max_kd}")
        self._write_line("")

        # Log all keywords with pass/fail status
        self._write_line("--- Filtering Results ---")
        self._write_line(f"{'Keyword':<40} {'Volume':>10} {'KD':>6} {'Status':>10}")
        self._write_line("-" * 70)

        qualified_set = {kw["keyword"].lower() for kw in qualified_keywords}

        for kw in all_keywords:
            keyword = kw["keyword"]
            volume = kw.get("search_volume") or 0
            kd = kw.get("keyword_difficulty") or 0
            status = "PASS" if keyword.lower() in qualified_set else "FAIL"

            # Add reason for failure
            if status == "FAIL":
                reasons = []
                if volume < min_volume:
                    reasons.append(f"vol<{min_volume}")
                if kd > max_kd:
                    reasons.append(f"kd>{max_kd}")
                status = f"FAIL ({', '.join(reasons)})"

            self._write_line(f"{keyword[:40]:<40} {volume:>10} {kd:>6.1f} {status:>10}")

        self._write_line("")

    def log_keyword_ranking(self, ranked_keywords: list[dict]) -> None:
        """Log ranked keywords with scores."""
        self._write_section(f"KEYWORD RANKING: {len(ranked_keywords)} keywords")

        self._write_line("--- Ranked Keywords (by score: volume / (kd + 1)) ---")
        self._write_line(f"{'Rank':>4} {'Keyword':<40} {'Volume':>10} {'KD':>6} {'Score':>10}")
        self._write_line("-" * 75)

        for i, kw in enumerate(ranked_keywords, 1):
            keyword = kw["keyword"]
            volume = kw.get("search_volume") or 0
            kd = kw.get("keyword_difficulty") or 0
            score = volume / (kd + 1)
            self._write_line(f"{i:>4} {keyword[:40]:<40} {volume:>10} {kd:>6.1f} {score:>10.1f}")

        self._write_line("")

    def log_topics_generated(self, topics: list[dict]) -> None:
        """Log generated topic suggestions."""
        self._write_section(f"TOPICS GENERATED: {len(topics)} topics")

        for i, topic in enumerate(topics, 1):
            self._write_line(f"\n{i}. {topic.get('title', 'Untitled')}")
            self._write_line(f"   Primary keyword: {topic.get('primary_keyword', 'N/A')}")
            self._write_line(f"   Search intent: {topic.get('search_intent', 'N/A')}")
            if topic.get("secondary_keywords"):
                self._write_line(f"   Secondary: {', '.join(topic['secondary_keywords'][:5])}")
            if topic.get("unique_angle"):
                self._write_line(f"   Unique angle: {topic['unique_angle'][:100]}")

        self._write_line("")

    def log_topic_selected(self, topic: dict, selection_method: str = "auto") -> None:
        """Log selected topic."""
        self._write_section(f"TOPIC SELECTED ({selection_method})", topic)

    def log_article_generated(self, article_metadata: dict) -> None:
        """Log generated article metadata."""
        self._write_section("ARTICLE GENERATED", {
            "title": article_metadata.get("title"),
            "word_count": article_metadata.get("word_count"),
            "primary_keyword": article_metadata.get("primary_keyword"),
            "secondary_keywords": article_metadata.get("secondary_keywords"),
            "search_intent": article_metadata.get("search_intent"),
            "meta_description": article_metadata.get("meta_description"),
        })

    def log_images_generated(self, images: list[dict]) -> None:
        """Log generated images."""
        self._write_section(f"IMAGES GENERATED: {len(images)} images")

        for i, img in enumerate(images, 1):
            self._write_line(f"{i}. {img.get('file_path', 'N/A')}")
            self._write_line(f"   Prompt: {img.get('prompt', 'N/A')[:100]}")

        self._write_line("")

    def log_cross_links_added(self, links: list[dict]) -> None:
        """Log cross-links added to article."""
        self._write_section(f"CROSS-LINKS ADDED: {len(links)} links", links)

    def log_output_files(self, markdown_path: str, json_path: str) -> None:
        """Log output file paths."""
        self._write_section("OUTPUT FILES", {
            "markdown": markdown_path,
            "json": json_path,
        })

    def log_error(self, operation: str, error: Exception | str) -> None:
        """Log an error."""
        self._write_section(f"ERROR: {operation}", {
            "error_type": type(error).__name__ if isinstance(error, Exception) else "str",
            "message": str(error),
        })

    def log_dataforseo_error(self, operation: str, details: dict[str, Any]) -> None:
        """Log a DataForSEO API error with structured details."""
        self._write_section(f"DATAFORSEO ERROR: {operation}", details)

    def log_custom(self, title: str, data: Any) -> None:
        """Log custom data."""
        self._write_section(title, data)


# Global logger instance - can be replaced by workflow
_workflow_logger: WorkflowLogger | None = None


def get_logger() -> WorkflowLogger | None:
    """Get the current workflow logger instance."""
    return _workflow_logger


def set_logger(logger: WorkflowLogger | None) -> None:
    """Set the workflow logger instance."""
    global _workflow_logger
    _workflow_logger = logger


def create_workflow_logger(logs_dir: Path | str = "logs") -> WorkflowLogger:
    """Create and set a new workflow logger."""
    logger = WorkflowLogger(logs_dir=logs_dir)
    set_logger(logger)
    return logger
