# SEO Agent

SEO article generation automation CLI tool for jobnova.ai/blog.

## Features

- Automated keyword research using DataForSEO API
- SEO-optimized article generation using OpenAI GPT-5.2
- Image generation with DALL-E 3
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

To generate the DataForSEO credentials:
```bash
echo -n "your_login:your_password" | base64
```

---

## Workflow Overview

### SEO AI Agent Workflow Steps

| Step | Description | Command | Status |
|------|-------------|---------|--------|
| **1** | Create category list for your product | `seo-agent categories add` | ✅ |
| **2** | Scan blog for existing titles/content | `seo-agent scrape` | ✅ |
| **3** | LLM suggests new keywords for category | `seo-agent research --workflow original` | ✅ |
| **4** | Filter: KD < 30, volume > 5k | `--min-volume 5000 --max-kd 30` | ✅ |
| **5** | LLM generates topics from qualified keywords | `seo-agent workflow --mode original` | ✅ |
| **6** | Generate SEO blog (topic + keywords + intent) | `seo-agent generate` | ✅ |
| **7** | Humanize AI content (reduce AI detection) | ❌ Not implemented | |
| **8** | Generate images (3-4 per 1k words) with SEO metadata | Automatic | ✅ |
| **9** | Cross-link to other blogs (3-4 per 1k words) | Automatic | ✅ |

### Alternative Workflow (Steps 4* and 5*)

| Step | Description | Command |
|------|-------------|---------|
| **4*** | LLM suggests unique topic (no duplicates) | `seo-agent research --workflow alternative` |
| **5*** | API generates 10-11 keywords for the topic | Automatic in alternative workflow |

---

## Usage

### Step 1: Category Management

```bash
# List all categories
seo-agent categories list

# Add a new category
seo-agent categories add "remote-work" --desc "Remote work tips and strategies"

# Remove a category
seo-agent categories remove "remote-work"
```

### Step 2: Scrape Existing Content

```bash
# Scrape existing blog content for cross-linking
seo-agent scrape remote-work

# Force fresh scrape (ignore cache)
seo-agent scrape remote-work --force

# Limit number of posts
seo-agent scrape remote-work --max 50
```

### Steps 3-5: Keyword Research

**Original Workflow** - GPT suggests keywords, DataForSEO validates:
```bash
seo-agent research remote-work --workflow original --min-volume 5000 --max-kd 30
```

**Alternative Workflow** - GPT suggests topic, DataForSEO generates keywords:
```bash
seo-agent research remote-work --workflow alternative
```

### Step 6: Article Generation

```bash
# Generate a single article with specific keywords
seo-agent generate "Best Remote Jobs in 2025" \
  --keywords "remote jobs,work from home,entry level remote jobs" \
  --intent informational \
  --category remote-work
```

### Full Automated Workflow

```bash
# Original workflow (interactive)
seo-agent workflow remote-work --mode original --interactive

# Alternative workflow
seo-agent workflow remote-work --mode alternative --interactive
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

---

## Example Workflow

```bash
# 1. Add category
seo-agent categories add "remote-work" --desc "Remote work tips"

# 2. Research keywords (original workflow)
seo-agent research remote-work --workflow original --min-volume 100 --max-kd 50

# Output:
# Found 20 keywords, 6 qualified
# - remote customer service jobs (246K volume, KD 20)
# - entry level remote jobs (60.5K volume, KD 21)
# ...

# 3. Generate article
seo-agent generate "Best Entry Level Remote Jobs in 2025" \
  -k "entry level remote jobs,remote jobs no experience,remote customer service jobs" \
  -i informational \
  -c remote-work

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
│   │   ├── category_manager.py
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
│   ├── categories.json
│   ├── existing_content/
│   └── generated/
│       ├── articles/
│       └── images/
└── tests/
```
