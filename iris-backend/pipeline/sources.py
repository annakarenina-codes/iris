"""
Approved Philippine verification sources for IRIS.

VERA Files is searched first because it is the priority fact-checking layer.
The other six sources are searched after VERA Files.
"""

VERA_SOURCE = {
    "name": "VERA Files",
    "domain": "verafiles.org",
    "site_query": "site:verafiles.org",
    "priority": True,
}

NEWS_SOURCES = [
    {
        "name": "GMA News",
        "domain": "gmanetwork.com/news",
        "site_query": "site:gmanetwork.com/news",
    },
    {
        "name": "Philippine Daily Inquirer",
        "domain": "inquirer.net",
        "site_query": "site:inquirer.net",
    },
    {
        "name": "Philippine Star",
        "domain": "philstar.com",
        "site_query": "site:philstar.com",
    },
    {
        "name": "Manila Bulletin",
        "domain": "mb.com.ph",
        "site_query": "site:mb.com.ph",
    },
    {
        "name": "Philippine News Agency",
        "domain": "pna.gov.ph",
        "site_query": "site:pna.gov.ph",
    },
    {
        "name": "Philippine Information Agency",
        "domain": "pia.gov.ph",
        "site_query": "site:pia.gov.ph",
    },
]

ALL_SOURCES = [VERA_SOURCE] + NEWS_SOURCES


def get_vera_source():
    """Returns the VERA Files source configuration."""
    return VERA_SOURCE


def get_news_sources():
    """Returns the six approved Philippine news source configurations."""
    return NEWS_SOURCES


def get_all_sources():
    """Returns VERA Files first, followed by the six approved sources."""
    return ALL_SOURCES
