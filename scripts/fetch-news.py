import json
import os
import re
import ssl
import sys
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT = os.path.join(ROOT, 'news.json')

RSS_FEEDS = [
    'https://news.google.com/rss/search?q=estafas+Uruguay&hl=es-419&gl=UY&ceid=UY:es-419',
    'https://news.google.com/rss/search?q=fraude+Uruguay&hl=es-419&gl=UY&ceid=UY:es-419',
    'https://news.google.com/rss/search?q=ciberseguridad+Uruguay&hl=es-419&gl=UY&ceid=UY:es-419',
    'https://news.google.com/rss/search?q=phishing+Uruguay&hl=es-419&gl=UY&ceid=UY:es-419'
]

KEYWORDS = [
    'estafa', 'estafas', 'fraude', 'fraudes', 'ciberseguridad', 'llamada', 'llamadas',
    'telefono', 'teléfono', 'scam', 'phishing', 'robos', 'delito', 'sospechoso'
]

CURATED_NEWS_ITEMS = [
    {
        'title': 'Hombre de 90 años cayó con el cuento del tío en Fray Bentos y sacó un préstamo para pagarle a su falso nieto',
        'link': 'https://www.elpais.com.uy/informacion/policiales/hombre-de-90-anos-cayo-con-el-cuento-del-tio-en-fray-bentos-y-saco-un-prestamo-para-pagarle-a-su-falso-nieto',
        'description': 'Caso de estafa en Fray Bentos con un supuesto nieto que pidió dinero para un supuesto problema.',
        'source': 'El País',
        'published_at': '2026-08-08T00:00:00+00:00'
    },
    {
        'title': 'Estafas telefónicas: nuevos casos llaman la atención por altas sumas y perfil de víctima',
        'link': 'https://www.montevideo.com.uy/Noticias/Estafas-telefonicas-nuevos-casos-llaman-la-atencion-por-altas-sumas-y-perfil-de-victima-uc965550',
        'description': 'Reportaje sobre estafas telefónicas con montos elevados y víctimas con perfiles específicos.',
        'source': 'Montevideo Portal',
        'published_at': '2026-08-08T00:00:00+00:00'
    },
    {
        'title': 'Nuevo caso del cuento del tío en Montevideo: una mujer entregó $1.500.000 y US$50.000 a delincuentes',
        'link': 'https://www.subrayado.com.uy/nuevo-caso-del-cuento-del-tio-montevideo-una-mujer-entrego-1500000-pesos-y-50000-dolares-delincuentes-n1010644',
        'description': 'Nuevo caso de estafa por el conocido “cuento del tío” en Montevideo.',
        'source': 'Subrayado',
        'published_at': '2026-08-08T00:00:00+00:00'
    }
]


def fetch_url(url: str):
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    context = ssl._create_unverified_context()
    with urlopen(req, context=context, timeout=20) as resp:
        return resp.read().decode('utf-8', errors='ignore')


def parse_date(value: str):
    if not value:
        return None
    text = value.strip()
    try:
        parsed = parsedate_to_datetime(text)
        if parsed is not None:
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
    except Exception:
        pass
    try:
        parsed = datetime.fromisoformat(text.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def parse_feed(feed_url: str):
    text = fetch_url(feed_url)
    root = ET.fromstring(text)
    items = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)

    for entry in root.findall('.//item'):
        title = (entry.findtext('title') or '').strip()
        link = (entry.findtext('link') or '').strip()
        description = (entry.findtext('description') or entry.findtext('{http://purl.org/rss/1.0/modules/content/}encoded') or '').strip()
        pub_date = (entry.findtext('pubDate') or entry.findtext('published') or entry.findtext('updated') or '').strip()
        published_at = parse_date(pub_date)
        if not title or not link:
            continue
        if published_at is None:
            published_at = datetime.now(timezone.utc)
        if published_at < cutoff:
            continue
        text_blob = f"{title} {description}".lower()
        if not any(k in text_blob for k in KEYWORDS):
            continue
        items.append({
            'title': re.sub(r'\s+', ' ', title).strip(),
            'link': link,
            'description': re.sub(r'<[^>]+>', ' ', description)[:220].strip(),
            'source': urlparse(feed_url).netloc.replace('www.', ''),
            'published_at': published_at.isoformat()
        })

    return items


def build_news():
    all_items = []
    for feed in RSS_FEEDS:
        try:
            all_items.extend(parse_feed(feed))
        except Exception as exc:
            print(f'Error with {feed}: {exc}', file=sys.stderr)

    seen = set()
    unique = []
    for item in all_items:
        key = (item['title'], item['link'])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    unique = unique[:6]
    if len(unique) < 3:
        for item in CURATED_NEWS_ITEMS:
            if not any(existing['link'] == item['link'] for existing in unique):
                unique.append(item)

    payload = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'items': unique
    }
    with open(OUTPUT, 'w', encoding='utf-8') as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    print(f'Wrote {len(unique)} items to {OUTPUT}')


if __name__ == '__main__':
    build_news()
