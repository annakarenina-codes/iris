"""
Approved Philippine verification sources for IRIS.

The two fact-checking organizations (VERA Files, then Rappler) are the priority
layer and are searched first. The nine news sources follow.

Each source declares how IRIS reads its articles:
- "full_text": the article page is downloaded and its text extracted.
- "search_excerpt": the publisher blocks automated downloads, so IRIS uses the
  article passages returned by the Brave Search API for that result instead of
  downloading the page. See SOURCES.md for the policy record.
"""

FULL_TEXT = "full_text"
SEARCH_EXCERPT = "search_excerpt"

VERA_SOURCE = {
    "name": "VERA Files",
    "domain": "verafiles.org",
    "site_query": "site:verafiles.org/articles",
    "priority": True,
    "access": FULL_TEXT,
    # Its fact-checks are not always in the web-search index (saved case C08), so IRIS also
    # looks them up in the sitemap VERA publishes.
    "sitemap": "https://verafiles.org/sitemap.xml",
    # Its pages now answer automated requests with a challenge page, so the article text is
    # read through the public article API the same site publishes. See SOURCES.md.
    "content_api": "https://verafiles.org/wp-json/wp/v2/posts",
}

FACT_CHECK_SOURCES = [
    VERA_SOURCE,
    {
        "name": "Rappler",
        "domain": "rappler.com",
        "site_query": "site:rappler.com",
        "priority": True,
        "access": FULL_TEXT,
    },
]

NEWS_SOURCES = [
    {
        "name": "ABS-CBN News",
        "domain": "abs-cbn.com",
        "site_query": "site:abs-cbn.com",
        "access": FULL_TEXT,
    },
    {
        "name": "GMA News",
        "domain": "gmanetwork.com",
        "site_query": "site:gmanetwork.com",
        "access": FULL_TEXT,
    },
    {
        "name": "Philippine Daily Inquirer",
        "domain": "inquirer.net",
        "site_query": "site:inquirer.net",
        "access": SEARCH_EXCERPT,
    },
    {
        "name": "Philippine Star",
        "domain": "philstar.com",
        "site_query": "site:philstar.com",
        "access": FULL_TEXT,
    },
    {
        "name": "Manila Bulletin",
        "domain": "mb.com.ph",
        "site_query": "site:mb.com.ph",
        "access": SEARCH_EXCERPT,
    },
    {
        "name": "Philippine News Agency",
        "domain": "pna.gov.ph",
        "site_query": "site:pna.gov.ph",
        "access": SEARCH_EXCERPT,
    },
    {
        "name": "Philippine Information Agency",
        "domain": "pia.gov.ph",
        "site_query": "site:pia.gov.ph",
        "access": SEARCH_EXCERPT,
    },
    {
        "name": "DZRH News",
        "domain": "dzrh.com.ph",
        "site_query": "site:dzrh.com.ph",
        "access": FULL_TEXT,
    },
    {
        "name": "OneNews.PH",
        "domain": "onenews.ph",
        "site_query": "site:onenews.ph",
        "access": FULL_TEXT,
    },
]

ALL_SOURCES = FACT_CHECK_SOURCES + NEWS_SOURCES
FACT_CHECK_SOURCE_NAMES = frozenset(source["name"] for source in FACT_CHECK_SOURCES)


def get_vera_source():
    """Returns the VERA Files source configuration."""
    return VERA_SOURCE


def get_fact_check_sources():
    """Returns the priority fact-checking sources, VERA Files first."""
    return FACT_CHECK_SOURCES


def get_news_sources():
    """Returns the nine approved Philippine news source configurations."""
    return NEWS_SOURCES


def get_all_sources():
    """Returns the fact-checking sources first, followed by the news sources."""
    return ALL_SOURCES


def get_source_by_name(name):
    """Returns the source configuration with this display name, if approved."""
    for source in ALL_SOURCES:
        if source["name"] == name:
            return source
    return None


def is_fact_check_source(name):
    return name in FACT_CHECK_SOURCE_NAMES


def uses_search_excerpts(name):
    """True when IRIS must not download this publisher's pages directly."""
    source = get_source_by_name(name)
    return bool(source) and source.get("access") == SEARCH_EXCERPT
