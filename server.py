"""Onde: service personnel de collecte EPG et d'export XMLTV."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlparse
from datetime import datetime
from zoneinfo import ZoneInfo
from threading import RLock
import os, json, gzip, base64, hmac, xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent
DATA = Path(os.environ.get('ONDE_DATA', ROOT / 'data'))
LOCK = RLock()

def load():
    with LOCK:
        return json.loads((DATA / 'state.json').read_text()) if (DATA / 'state.json').exists() else {'sources': [], 'programs': [], 'errors': []}

def save(state):
    with LOCK:
        DATA.mkdir(parents=True, exist_ok=True)
        temp = DATA / 'state.tmp'
        temp.write_text(json.dumps(state, ensure_ascii=False))
        temp.replace(DATA / 'state.json')

def date(value, timezone):
    value = datetime.fromisoformat(str(value).strip().replace('Z', '+00:00'))
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo(timezone))
    return value.isoformat()

def collect(source):
    url = source['url']
    if urlparse(url).scheme not in ('http', 'https'):
        raise ValueError('Une URL HTTP ou HTTPS est requise.')
    with urlopen(Request(url, headers={'User-Agent': 'OndeEPG/1.0'}), timeout=25) as response:
        raw = response.read(5_000_001)
        if len(raw) > 5_000_000:
            raise ValueError('Page supérieure à 5 Mo.')
    soup = BeautifulSoup(raw, 'html.parser')
    records = []
    if source.get('mode', 'jsonld') == 'jsonld':
        def walk(obj):
            if isinstance(obj, list):
                for item in obj: walk(item)
            elif isinstance(obj, dict):
                if obj.get('startDate') and obj.get('endDate'):
                    work = obj.get('workPerformed') or obj.get('publication') or {}
                    title = obj.get('name') or (work.get('name') if isinstance(work, dict) else None)
                    if title:
                        records.append({'title': title, 'start': obj['startDate'], 'stop': obj['endDate'], 'description': obj.get('description', '')})
                for item in obj.values():
                    if isinstance(item, (list, dict)): walk(item)
        for script in soup.select('script[type="application/ld+json"]'):
            try: walk(json.loads(script.string or script.get_text()))
            except json.JSONDecodeError: continue
    else:
        def extract(row, key):
            selector = source.get(key, '')
            if not selector: return ''
            css, _, attr = selector.partition('@')
            element = row.select_one(css.strip())
            if element is None: return ''
            return element.get(attr.strip(), '') if attr else element.get_text(' ', strip=True)
        for row in soup.select(source['row']):
            records.append({key: extract(row, key) for key in ('title', 'start', 'stop', 'description')})
    result = []
    for record in records:
        record['start'] = date(record['start'], source.get('timezone', 'Europe/Paris'))
        record['stop'] = date(record['stop'], source.get('timezone', 'Europe/Paris'))
        if not record['title'] or datetime.fromisoformat(record['stop']) <= datetime.fromisoformat(record['start']):
            raise ValueError('Titre absent ou horaires invalides.')
        record['channel'] = source['id']
        result.append(record)
    if not result:
        raise ValueError('Aucun programme détecté. Vérifiez les sélecteurs ou les données JSON-LD ; les pages JavaScript nécessitent un connecteur dédié.')
    return list({(p['channel'], p['start'], p['title']): p for p in result}.values())

def export(state):
    tv = ET.Element('tv', {'generator-info-name': 'Onde'})
    for source in state['sources']:
        c = ET.SubElement(tv, 'channel', {'id': source['id']})
        ET.SubElement(c, 'display-name', {'lang': 'fr'}).text = source['name']
    for program in sorted(state['programs'], key=lambda p: p['start']):
        attrs = {'channel': program['channel']}
        for key in ('start', 'stop'):
            attrs[key] = datetime.fromisoformat(program[key]).strftime('%Y%m%d%H%M%S %z')
        p = ET.SubElement(tv, 'programme', attrs)
        ET.SubElement(p, 'title', {'lang': 'fr'}).text = program['title']
        if program.get('description'): ET.SubElement(p, 'desc', {'lang': 'fr'}).text = program['description']
    return ET.tostring(tv, encoding='utf-8', xml_declaration=True)

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs): super().__init__(*args, directory=str(ROOT / 'public'), **kwargs)
    def send(self, data, content='application/json', status=200):
        if not isinstance(data, bytes): data = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', content)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)
    def authorized(self):
        username, password = os.environ.get('ONDE_USER'), os.environ.get('ONDE_PASSWORD')
        if not username and not password: return True
        if not username or not password:
            self.send({'error': 'Configurer ONDE_USER et ONDE_PASSWORD ensemble.'}, status=503)
            return False
        expected = 'Basic ' + base64.b64encode((username + ':' + password).encode()).decode()
        if hmac.compare_digest(self.headers.get('Authorization', ''), expected): return True
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm="Onde", charset="UTF-8"')
        self.end_headers()
        return False
    def do_GET(self):
        if not self.authorized(): return
        path = urlparse(self.path).path
        if path == '/api/state': return self.send(load())
        if path in ('/guide.xml', '/guide.xml.gz'):
            xml = export(load())
            return self.send(gzip.compress(xml) if path.endswith('.gz') else xml, 'application/gzip' if path.endswith('.gz') else 'application/xml; charset=utf-8')
        if path.startswith('/api/'): return self.send({'error': 'Route inconnue'}, status=404)
        super().do_GET()
    def do_POST(self):
        if not self.authorized(): return
        origin = self.headers.get('Origin')
        if origin and urlparse(origin).netloc != self.headers.get('Host'):
            return self.send({'error': 'Origine de requête refusée.'}, status=403)
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 1_000_000: raise ValueError('Requête invalide ou trop volumineuse.')
            body = json.loads(self.rfile.read(size))
            with LOCK:
                state = load()
                if self.path == '/api/sources':
                    sources = body['sources']
                    if not isinstance(sources, list): raise ValueError('Liste de sources requise.')
                    ids = set()
                    for s in sources:
                        if not all(isinstance(s.get(k), str) and s[k].strip() for k in ('id', 'name', 'url')): raise ValueError('Nom, identifiant et URL requis.')
                        if s['id'] in ids: raise ValueError('Identifiant de chaîne déjà utilisé.')
                        ids.add(s['id'])
                        if urlparse(s['url']).scheme not in ('http', 'https'): raise ValueError('URL HTTP(S) requise.')
                        ZoneInfo(s.get('timezone', 'Europe/Paris'))
                        if s.get('mode', 'jsonld') not in ('jsonld', 'css'): raise ValueError('Mode inconnu.')
                        if s.get('mode') == 'css' and not all(s.get(k) for k in ('row','title','start','stop')): raise ValueError('Sélecteurs programme, titre, début et fin requis.')
                    state['sources'] = sources
                    state['programs'] = [p for p in state['programs'] if p['channel'] in ids]
                elif self.path == '/api/grab':
                    errors = []
                    for s in state['sources']:
                        try:
                            programs = collect(s)
                            state['programs'] = [p for p in state['programs'] if p['channel'] != s['id']] + programs
                        except Exception as e: errors.append({'source': s['name'], 'error': str(e)})
                    state['errors'] = errors
                    state['last_grab'] = datetime.now(ZoneInfo('Europe/Paris')).isoformat()
                else: return self.send({'error': 'Route inconnue'}, status=404)
                save(state)
            self.send(state)
        except (ValueError, KeyError, TypeError) as e: self.send({'error': str(e)}, status=400)

if __name__ == '__main__':
    ThreadingHTTPServer((os.environ.get('HOST', '127.0.0.1'), int(os.environ.get('PORT', '3000'))), Handler).serve_forever()
