import re

from scraper.database.database import get_domain_id
from scraper.entity.domain import Domain
from scraper.entity.page import Page
from scraper.language import language
from urllib.parse import urlparse
import urllib.robotparser as urobot
import ssl
import pyhash
import zlib

rp = urobot.RobotFileParser()
ssl._create_default_https_context = ssl._create_unverified_context
fp = pyhash.farm_fingerprint_64()


def get_text(soup):
    for s in soup(['script', 'style']):
        s.decompose()
    return ' '.join(soup.stripped_strings)


def get_domain(url):
    domain = urlparse(url).netloc
    return "http://" + domain if "http://" in url else "https://" + domain


def get_favicon(url, soup):
    domain = get_domain(url)

    icon_link = soup.find("link", rel="shortcut icon")
    if icon_link is None:
        icon_link = soup.find("link", rel="icon")
    if icon_link is None:
        return domain + '/favicon.ico'
    result = icon_link["href"]

    if url_is_valid(result):
        return result
    return domain + result


def get_canoncial(soup):
    canonical = soup.find('link', {'rel': 'canonical'})
    return canonical['href']


def get_urls(url, soup):
    urls = [link.get('href') for link in soup.find_all('a')]
    urls = list(filter(None, urls))
    add_prefit = lambda x: x if (("http://" in x) or ("https://" in x)) else url + x

    return list(set(map(add_prefit, urls)))


def extract_content(url, soup, current_time):
    # The main function
    page = Page(url=url,
                title=soup.title.string.capitalize().strip(),
                meta=None,
                domain_id=None,
                divs=None,
                headings=None,
                current_time=current_time,
                urls=None)

    domain_obj = Domain(domain=get_domain(url),
                        favicon=None,
                        current_time=current_time)

    # Get meta
    meta = [meta['content'] for meta in soup.findAll(attrs={"name": re.compile(r"description", re.I)})]
    if meta:
        page.meta = meta[0]

    # Get favicon
    domain_obj.favicon = get_favicon(url, soup)


    # Get canonical
    canonical = get_canoncial(soup)
    if canonical:
        page.url = canonical


    list_of_divs = [r.text for r in soup.findAll('div')]
    if list_of_divs:
        list_of_divs = [word.replace("\n", " ") for word in list_of_divs]
        list_of_divs = [" ".join(word.split()) for word in list_of_divs]
        list_of_divs = [i for i in list_of_divs if i]

        page.divs = list_of_divs

    # TODO: use them Get all headings
    list_of_headings = [headlines.text.strip() for headlines in soup.find_all(re.compile('^h[1-6]$'))]
    if list_of_headings:
        page.headings = list_of_headings
    # Get all urls
    page.add_urls(get_urls(url, soup))

    word_count = language.word_count(get_text(soup))

    page.domain_id = get_domain_id(domain_obj.domain, domain_obj)


    return word_count, page


def calculate_fingerprint(page_data):
    values_as_str = ''.join('{}{}'.format(key, val) for key, val in page_data.items())
    rest = fp(values_as_str)
    return rest


def compress_urls(list_of_urls):
    list_of_urls.sort()
    my_string = ','.join(map(str, list_of_urls)).encode()
    return zlib.compress(my_string, 2)


def de_compress(compressed_string):
    decoded = zlib.decompress(compressed_string).decode("utf-8")
    return decoded.split(",")


def get_initial_domain_content(url, current_time, favicon):
    domain = urlparse(url).netloc
    domain = "http://" + domain if "http://" in url else "https://" + domain

    domain_data = {
        "domain_url": domain,
        "favicon": favicon,
        "is_secure": "https" in domain,
        "last_crawl_time_UTC": current_time,
        "first_crawl_time_UTC": current_time,
    }
    return domain_data


def url_is_valid(url):
    regex = re.compile(
        r'^(?:http|ftp)s?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return re.match(regex, url) is not None