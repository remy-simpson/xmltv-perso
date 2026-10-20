import unittest, threading, tempfile, json, sys, gzip
from unittest.mock import patch
from urllib.error import HTTPError
import base64
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.request import urlopen, Request
import xml.etree.ElementTree as ET
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server

class Fixture(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers()
        if self.path == '/jsonld':
            self.wfile.write(b'<script type="application/ld+json">{"@type":"BroadcastEvent","name":"Journal & culture","startDate":"2026-10-20T20:00:00+02:00","endDate":"2026-10-20T21:00:00+02:00"}</script>')
        elif self.path == '/html':
            self.wfile.write(b'<article><h3>Film du soir</h3><time class="start" datetime="2026-10-20T21:00:00+02:00"></time><time class="end" datetime="2026-10-20T23:00:00+02:00"></time></article>')
    def log_message(self, *args): pass

class Workflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        server.DATA = Path(cls.tmp.name)
        cls.fixture = ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
        cls.app = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        for s in (cls.fixture, cls.app): threading.Thread(target=s.serve_forever, daemon=True).start()
        cls.base = 'http://127.0.0.1:'+str(cls.app.server_port)
    @classmethod
    def tearDownClass(cls):
        for s in (cls.fixture, cls.app): s.shutdown(); s.server_close()
        cls.tmp.cleanup()
    def post(self, path, data):
        with urlopen(Request(self.base+path, data=json.dumps(data).encode(), headers={'Content-Type':'application/json'})) as r: return json.load(r)
    def test_authentication_and_origin(self):
        with patch.dict(server.os.environ, {'ONDE_USER': 'test-user', 'ONDE_PASSWORD': 'test-password'}):
            with self.assertRaises(HTTPError) as error:
                urlopen(self.base + '/api/state')
            self.assertEqual(error.exception.code, 401)
            token = base64.b64encode(b'test-user:test-password').decode()
            request = Request(self.base + '/api/state', headers={'Authorization': 'Basic ' + token})
            with urlopen(request) as response:
                self.assertEqual(response.status, 200)
        request = Request(self.base + '/api/grab', data=b'{}', headers={'Origin': 'https://other.example'})
        with self.assertRaises(HTTPError) as error: urlopen(request)
        self.assertEqual(error.exception.code, 403)

    def test_multi_source_export_and_failure_retention(self):
        base='http://127.0.0.1:'+str(self.fixture.server_port)
        sources=[{'id':'A.fr','name':'Chaîne A','url':base+'/jsonld','mode':'jsonld'}, {'id':'B.fr','name':'Chaîne B','url':base+'/html','mode':'css','row':'article','title':'h3','start':'.start@datetime','stop':'.end@datetime'}]
        self.post('/api/sources', {'sources':sources})
        state=self.post('/api/grab', {})
        self.assertEqual(len(state['programs']),2); self.assertEqual(state['errors'],[])
        with urlopen(self.base+'/guide.xml') as r: xml=r.read()
        root=ET.fromstring(xml)
        self.assertEqual(len(root.findall('channel')),2)
        self.assertEqual(len(root.findall('programme')),2)
        self.assertEqual(root.find('programme/title').text,'Journal & culture')
        self.assertTrue(root.find('programme').get('start').endswith('+0200'))
        with urlopen(self.base+'/guide.xml.gz') as r: self.assertEqual(gzip.decompress(r.read()),xml)
        sources[0]['url']=base+'/empty'
        self.post('/api/sources', {'sources':sources})
        failed=self.post('/api/grab',{})
        self.assertEqual(len(failed['errors']),1)
        self.assertEqual(len(failed['programs']),2)
        self.assertEqual(len(server.load()['programs']),2)
        self.post('/api/sources', {'sources':sources[1:]})
        self.assertEqual(len(server.load()['programs']),1)

if __name__ == '__main__': unittest.main()
