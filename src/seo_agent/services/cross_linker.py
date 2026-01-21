"""Cross-linking service for internal link management."""

import re
from rapidfuzz import fuzz, process

from seo_agent.models.article import Article
from seo_agent.models.blog_post import ExistingPost, ScrapedContent


class CrossLinkerService:
    """Service for adding internal cross-links to articles."""

    def __init__(
        self,
        links_per_1k_words: float = 3.5,
        min_similarity_score: int = 60,
    ):
        self.links_per_1k_words = links_per_1k_words
        self.min_similarity_score = min_similarity_score

    def add_cross_links(
        self,
        article: Article,
        existing_posts: list[ExistingPost] | ScrapedContent,
    ) -> Article:
        """Add internal cross-links to an article."""
        if isinstance(existing_posts, ScrapedContent):
            posts = existing_posts.posts
        else:
            posts = existing_posts

        if not posts:
            return article

        # Calculate target number of links
        word_count = article.metadata.word_count
        target_links = max(1, int((word_count / 1000) * self.links_per_1k_words))

        # Find relevant posts to link to
        relevant_posts = self._find_relevant_posts(
            article=article,
            posts=posts,
            max_links=target_links + 2,  # Get extra for selection
        )

        # Insert links into content
        content, added_links = self._insert_links(
            content=article.content,
            posts=relevant_posts[:target_links],
        )

        article.content = content
        article.internal_links = added_links

        return article

    def _find_relevant_posts(
        self,
        article: Article,
        posts: list[ExistingPost],
        max_links: int = 5,
    ) -> list[ExistingPost]:
        """Find posts most relevant to the article content."""
        # Combine article title and keywords for matching
        article_text = (
            f"{article.metadata.title} "
            f"{article.metadata.primary_keyword} "
            f"{' '.join(article.metadata.secondary_keywords)}"
        ).lower()

        # Score each post by relevance
        scored_posts = []
        for post in posts:
            # Skip if it's the same article
            if post.title.lower() == article.metadata.title.lower():
                continue

            # Calculate fuzzy match score
            score = fuzz.token_set_ratio(
                article_text,
                f"{post.title} {' '.join(post.tags)}".lower(),
            )

            if score >= self.min_similarity_score:
                scored_posts.append((post, score))

        # Sort by score and return top matches
        scored_posts.sort(key=lambda x: x[1], reverse=True)
        return [post for post, score in scored_posts[:max_links]]

    def _insert_links(
        self,
        content: str,
        posts: list[ExistingPost],
    ) -> tuple[str, list[dict[str, str]]]:
        """Insert links into content at natural positions."""
        added_links = []
        modified_content = content

        for post in posts:
            # Find anchor text candidates from post title
            anchor_candidates = self._generate_anchor_candidates(post.title)

            # Try to find and replace a suitable phrase in the content
            for anchor in anchor_candidates:
                # Look for the phrase (case insensitive, not already a link)
                pattern = rf'(?<!\[)(?<!\()({re.escape(anchor)})(?!\])(?!\))'
                match = re.search(pattern, modified_content, re.IGNORECASE)

                if match:
                    # Replace with link (only first occurrence)
                    original_text = match.group(1)
                    link_md = f"[{original_text}]({post.url})"
                    modified_content = (
                        modified_content[:match.start()]
                        + link_md
                        + modified_content[match.end():]
                    )

                    added_links.append({
                        "title": post.title,
                        "url": post.url,
                        "anchor_text": original_text,
                    })
                    break

        return modified_content, added_links

    def _generate_anchor_candidates(self, title: str) -> list[str]:
        """Generate potential anchor text phrases from a title."""
        candidates = []

        # Clean title
        clean_title = re.sub(r'[^\w\s]', '', title).strip()

        # Full title (cleaned)
        candidates.append(clean_title)

        # Extract key phrases (2-4 word combinations)
        words = clean_title.split()

        # Skip common starting words
        skip_words = {"how", "to", "the", "a", "an", "what", "why", "when", "where"}

        # 3-word phrases
        for i in range(len(words) - 2):
            phrase = " ".join(words[i:i+3])
            if words[i].lower() not in skip_words:
                candidates.append(phrase)

        # 2-word phrases
        for i in range(len(words) - 1):
            phrase = " ".join(words[i:i+2])
            if words[i].lower() not in skip_words:
                candidates.append(phrase)

        # Single important words (longer than 5 chars)
        for word in words:
            if len(word) > 5 and word.lower() not in skip_words:
                candidates.append(word)

        return candidates

    def suggest_link_opportunities(
        self,
        article: Article,
        existing_posts: list[ExistingPost],
    ) -> list[dict]:
        """Suggest link opportunities without automatically inserting."""
        suggestions = []
        article_text = article.content.lower()

        for post in existing_posts:
            if post.title.lower() == article.metadata.title.lower():
                continue

            anchor_candidates = self._generate_anchor_candidates(post.title)

            for anchor in anchor_candidates:
                if anchor.lower() in article_text:
                    # Check if not already linked
                    link_pattern = rf'\[{re.escape(anchor)}\]'
                    if not re.search(link_pattern, article.content, re.IGNORECASE):
                        suggestions.append({
                            "post_title": post.title,
                            "post_url": post.url,
                            "suggested_anchor": anchor,
                            "context": self._get_context(article.content, anchor),
                        })
                        break

        return suggestions

    def _get_context(self, content: str, phrase: str, context_chars: int = 50) -> str:
        """Get surrounding context for a phrase in content."""
        pattern = rf'(.{{0,{context_chars}}})({re.escape(phrase)})(.{{0,{context_chars}}})'
        match = re.search(pattern, content, re.IGNORECASE)

        if match:
            before, target, after = match.groups()
            return f"...{before}**{target}**{after}..."

        return ""

    def analyze_link_distribution(self, article: Article) -> dict:
        """Analyze the distribution of links in an article."""
        content = article.content

        # Find all markdown links
        link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
        links = re.findall(link_pattern, content)

        # Calculate positions
        total_length = len(content)
        link_positions = []

        for anchor, url in links:
            match = re.search(re.escape(f"[{anchor}]({url})"), content)
            if match:
                position = match.start() / total_length
                link_positions.append({
                    "anchor": anchor,
                    "url": url,
                    "position_percent": round(position * 100, 1),
                })

        return {
            "total_links": len(links),
            "internal_links": len([l for l in links if "jobnova.ai" in l[1]]),
            "external_links": len([l for l in links if "jobnova.ai" not in l[1]]),
            "links_per_1k_words": round(len(links) / (article.metadata.word_count / 1000), 2),
            "distribution": link_positions,
        }


def create_cross_linker(
    links_per_1k_words: float = 3.5,
    min_similarity_score: int = 60,
) -> CrossLinkerService:
    """Factory function to create cross-linker service."""
    return CrossLinkerService(
        links_per_1k_words=links_per_1k_words,
        min_similarity_score=min_similarity_score,
    )
