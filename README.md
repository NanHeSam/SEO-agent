# SEO Agent

SEO article generation automation CLI tool for jobnova.ai/blog.

## Features

- Automated keyword research using DataForSEO API
- SEO-optimized article generation using OpenAI GPT-5.2
- Country selection for geo-targeted keyword research
- Image generation with DALL-E 3
- Optional image upload to Libaspace admin file API (cloud URLs embedded in article)
- Internal cross-linking with fuzzy matching
- Markdown + JSON output with YAML frontmatter

## Installation

```bash
pip install -e .
```

## Configuration

Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
```

Required environment variables:
- `OPENAI_API_KEY` - OpenAI API key
- `DATAFORSEO_API_CREDENTIALS` - DataForSEO credentials (base64-encoded `login:password`)

Optional workflow environment variables:
- `DEFAULT_TOPIC_COUNT` - Number of topic ideas to generate from qualified keywords (default: `1`)
- `DEFAULT_COUNTRY` - Default country name (display only; used in logs/prompts)
- `DEFAULT_LOCATION_CODE` - DataForSEO `location_code` used for keyword research (default: `2840` for United States). If you don’t want to deal with codes, set `DEFAULT_COUNTRY` to `United States`, `Canada`, or `Singapore` and the code will be auto-selected.
- `DEFAULT_LANGUAGE_CODE` - DataForSEO `language_code` used for keyword research (default: `en`)

Optional environment variables for posting:
- `BLOG_API_ADMIN_URL` - Blog admin API base URL (default: `https://test-api-admin.libaspace.com/api`)
- `BLOG_API_TOKEN` - Blog admin API JWT token (required for `post` or `--post`)

When `BLOG_API_TOKEN` is set, generated images (including the featured/cover image) are uploaded via:

- `POST https://test-api-admin.libaspace.com/api/admin/file/upload` (multipart form-data)
- Uses the same `token` header as blog posting
- The returned `data.url` is embedded directly in the article Markdown/HTML

To generate the DataForSEO credentials:
```bash
echo -n "your_login:your_password" | base64
```

---

## Workflow Overview

### SEO AI Agent Workflow Steps

| Step | Description | Command | Status |
|------|-------------|---------|--------|
| **1** | Scan blog for existing titles/content | `seo-agent scrape` | ✅ |
| **2** | Select country (geo targeting for keyword research) | `seo-agent workflow --interactive` or `--country ...` | ✅ |
| **3** | LLM suggests new keywords | `seo-agent research --workflow original` | ✅ |
| **4** | Filter: KD < 30, volume > 5k | `--min-volume 5000 --max-kd 30` | ✅ |
| **5** | LLM generates 1 topic and drafts the article | `seo-agent workflow --mode original` | ✅ |
| **6** | Generate images (3-4 per 1k words) + featured image | Automatic | ✅ |
| **6.1** | Upload images and embed cloud URLs (optional) | Automatic when `BLOG_API_TOKEN` is set | ✅ |
| **7** | Cross-link to other blogs (3-4 per 1k words) | Automatic | ✅ |
| **8** | Humanize AI content (reduce AI detection) | ❌ Not implemented | |

### Alternative Workflow (Steps 4* and 5*)

| Step | Description | Command |
|------|-------------|---------|
| **4*** | LLM suggests a unique topic (single topic) | `seo-agent research --workflow alternative` |
| **5*** | API generates 10-11 keywords and workflow drafts the article | Automatic in alternative workflow |

---

## Usage

### Step 1: Scrape Existing Content

```bash
# Fetch existing blog posts (cached by default)
seo-agent scrape

# Force fresh fetch (ignore cache)
seo-agent scrape --force

# Cache full content (slower, larger cache)
seo-agent scrape --include-content
```

### Steps 2-3: Keyword Research

**Original Workflow** - GPT suggests keywords, DataForSEO validates:
```bash
seo-agent research --workflow original --min-volume 5000 --max-kd 30

# With country targeting (overrides DEFAULT_LOCATION_CODE/DEFAULT_LANGUAGE_CODE)
seo-agent research --workflow original --country "USA"
```

**Alternative Workflow** - GPT suggests topic, DataForSEO generates keywords:
```bash
seo-agent research --workflow alternative

# With country targeting
seo-agent research --workflow alternative --country "Singapore"
```

### Step 4: Article Generation

```bash
# Generate a single article with specific keywords
seo-agent generate "Best Remote Jobs in 2025" \
  --keywords "remote jobs,work from home,entry level remote jobs" \
  --intent informational

# Generate and post in one step
seo-agent generate "Best Remote Jobs in 2025" \
  --keywords "remote jobs,work from home,entry level remote jobs" \
  --intent informational \
  --post
```

### Full Automated Workflow

Workflow now generates a single topic and drafts the article automatically.

```bash
# Original workflow (interactive, generates 1 topic + article)
seo-agent workflow --mode original --interactive

# Alternative workflow (generates 1 topic + article)
seo-agent workflow --mode alternative --interactive

# Country targeting without interactive prompt
seo-agent workflow --mode original --no-interactive --country "Canada"

# Run workflow and post on completion
seo-agent workflow --mode original --interactive --post
```

### Post a Generated Article

```bash
seo-agent post best-entry-level-remote-jobs-in-2025
```

You can optionally override the cover image on posting:

```bash
seo-agent post best-entry-level-remote-jobs-in-2025 \
  --cover-url "https://static.libaspace.com/image/....jpg" \
  --cover-alt "Best Remote Jobs in 2025 - remote jobs"
```

---

## Output

Generated files are saved to:
- **Articles**: `data/generated/articles/` (Markdown + JSON)
- **Images**: `data/generated/images/` (PNG with SEO filenames)

### Markdown Output Includes:
- YAML frontmatter with SEO metadata
- Primary keyword in title, first paragraph, H2, and conclusion
- Secondary keywords distributed naturally (1-2% density)
- Images with alt text and captions
- Internal cross-links to related posts

### Image SEO:
- Filename: `{topic-slug}-{keyword}-{index}.png`
- Alt text: `{section heading} - {keyword}`
- 3-4 images per 1,000 words

### Cloud image upload (optional):
- When `BLOG_API_TOKEN` is set, each generated image is uploaded and the returned public URL is used in the article content.
- The featured image is also used as the blog cover via `coverUrl` and `coverAlt` when posting.

---

## Example Workflow

```bash
# 1. Research keywords (original workflow)
seo-agent research --workflow original --min-volume 100 --max-kd 50

# Output:
# Found 20 keywords, 6 qualified
# - remote customer service jobs (246K volume, KD 20)
# - entry level remote jobs (60.5K volume, KD 21)
# ...

# 2. Generate article
seo-agent generate "Best Entry Level Remote Jobs in 2025" \
  -k "entry level remote jobs,remote jobs no experience,remote customer service jobs" \
  -i informational

# Output:
# Generated 2696 words
# Generated 10 images
# Saved to data/generated/articles/best-entry-level-remote-jobs-...md
```

---

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with verbose output
pytest -v
```

---

## Project Structure

```
seo-agent/
├── src/seo_agent/
│   ├── cli.py                 # CLI commands (Typer)
│   ├── config.py              # Settings (pydantic-settings)
│   ├── clients/
│   │   ├── openai_client.py   # GPT-5.2 + DALL-E 3
│   │   └── dataforseo_client.py
│   ├── core/
│   │   ├── workflow.py        # Main orchestration
│   │   └── content_planner.py
│   ├── services/
│   │   ├── scraper.py         # Blog scraping
│   │   ├── keyword_research.py
│   │   ├── content_generator.py
│   │   ├── image_generator.py
│   │   └── cross_linker.py
│   ├── models/                # Pydantic models
│   └── output/                # Markdown + JSON writers
├── data/
│   ├── existing_content/
│   └── generated/
│       ├── articles/
│       └── images/
└── tests/
```
