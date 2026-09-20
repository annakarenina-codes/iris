"""Approved publisher article URLs, never search/category pages as evidence."""
from urllib.parse import parse_qsl, unquote, urlsplit, urlunsplit, urlencode

from pipeline.sources import get_all_sources


def clean_article_url(url):
    try:
        parts = urlsplit(str(url or '').strip().rstrip(').,;]'))
        query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True)
                 if key.lower() not in {'fbclid', 'gclid'} and not key.lower().startswith('utm_')]
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ''))
    except ValueError:
        return ''


# A column is its author's argument, not the publisher reporting a fact. Saved case B07
# supported a factual claim with an Inquirer opinion piece and a Rappler thought-leaders column.
OPINION_HOSTS = {'opinion.inquirer.net'}
OPINION_SEGMENTS = {'opinion', 'opinions', 'opinyon', 'column', 'columns', 'columnist',
                    'editorial', 'editorials', 'commentary', 'voices', 'thought-leaders',
                    'blog', 'blogs'}


def is_opinion_url(url):
    """True for a publisher's opinion, column or editorial section."""
    parts = urlsplit(clean_article_url(url))
    host = (parts.hostname or '').lower()
    if host in OPINION_HOSTS:
        return True
    segments = {unquote(segment).casefold() for segment in parts.path.split('/') if segment}
    return bool(segments & OPINION_SEGMENTS)


def article_url_rejection(url, expected_source=None):
    try:
        parts = urlsplit(clean_article_url(url))
        host = (parts.hostname or '').lower()
        if parts.scheme not in {'http', 'https'} or not host or parts.username or parts.password:
            return 'invalid_url'
        if parts.port not in {None, 80, 443}:
            return 'invalid_port'
        approved = [s for s in get_all_sources() if not expected_source or s['name'] == expected_source]
        domains = [s['domain'].split('/')[0] for s in approved]
        if not any(host == domain or host.endswith('.' + domain) for domain in domains):
            return 'unapproved_publisher'
        segments = [unquote(s).casefold() for s in parts.path.split('/') if s]
        query_keys = {key.casefold() for key, _ in parse_qsl(parts.query)}
        if query_keys & {'s', 'q', 'search', 'query', 'search_query'}:
            return 'search_results_page'
        if not segments or any(s in {'search', 'search-results', 'tag', 'tags', 'topic', 'topics',
                                     'category', 'categories', 'author', 'authors', 'feed'}
                               for s in segments):
            return 'listing_page'
        if host == 'verafiles.org' or host.endswith('.verafiles.org'):
            if len(segments) != 2 or segments[0] != 'articles':
                return 'not_vera_article'
        if len(segments) < 2:
            return 'listing_page'
        if host == 'rappler.com' or host.endswith('.rappler.com'):
            if '-' not in segments[-1]:
                return 'listing_page'
        if host == 'dzrh.com.ph' or host.endswith('.dzrh.com.ph'):
            if len(segments) != 2 or segments[0] != 'post':
                return 'listing_page'
        if host == 'onenews.ph' or host.endswith('.onenews.ph'):
            if len(segments) != 2 or segments[0] != 'articles':
                return 'listing_page'
        if host == 'abs-cbn.com' or host.endswith('.abs-cbn.com'):
            if len(segments) < 4:
                return 'listing_page'
        if segments[-1] in {'news', 'latest', 'headlines', 'entertainment', 'lifestyle', 'sports'}:
            return 'listing_page'
        return None
    except (TypeError, ValueError):
        return 'invalid_url'
