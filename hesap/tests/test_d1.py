import io
import json
import urllib.error

import pytest

from hesap import d1


@pytest.fixture
def ortam(monkeypatch):
    monkeypatch.setenv('CF_D1_TOKEN', 'GIZLI-DENEME-DEGERI')
    monkeypatch.setenv('CF_HESAP', 'h')
    monkeypatch.setenv('D1_ID', 'v')
    monkeypatch.setattr(d1.time, 'sleep', lambda s: None)


class Yanit(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_toplu_100_ifadelik_batch(ortam, monkeypatch):
    govdeler = []

    def sahte(istek, timeout):
        g = json.loads(istek.data)
        govdeler.append(g)
        assert istek.full_url == 'https://api.cloudflare.com/client/v4/accounts/h/d1/database/v/query'
        assert istek.get_header('Authorization') == 'Bearer GIZLI-DENEME-DEGERI'
        return Yanit(json.dumps({'success': True, 'errors': [], 'result': [
            {'results': [{'i': q['params'][0]}], 'success': True, 'meta': {'rows_read': 1, 'rows_written': 2}}
            for q in g['batch']]}).encode())
    monkeypatch.setattr(d1.urllib.request, 'urlopen', sahte)
    d1.sayac.update(okunan=0, yazilan=0, istek=0)
    s = d1.toplu([('SELECT ?', [i]) for i in range(250)])
    assert [len(g['batch']) for g in govdeler] == [100, 100, 50]
    assert s[249] == [{'i': 249}]
    assert d1.sayac['okunan'] == 250 and d1.sayac['yazilan'] == 500


def test_hata_iletisi_token_icermez(ortam, monkeypatch, capsys):
    def sahte(istek, timeout):
        raise urllib.error.HTTPError(istek.full_url, 403, 'Forbidden', {}, io.BytesIO(
            json.dumps({'success': False, 'errors': [{'code': 10000, 'message': 'Authentication error'}]}).encode()))
    monkeypatch.setattr(d1.urllib.request, 'urlopen', sahte)
    with pytest.raises(d1.D1Hatasi) as h:
        d1.sorgu('SELECT 1')
    assert str(h.value) == 'D1 HTTP 403: Authentication error'
    assert 'GIZLI' not in str(h.value) and 'GIZLI' not in capsys.readouterr().out
