# Cloudflare D1 REST istemcisi. Sırlar yalnız ortam değişkeninden (Actions secrets): CF_D1_TOKEN, CF_HESAP, D1_ID.
# Token hiçbir zaman yazdırılmaz; HTTP hatasında yalnız durum kodu ve Cloudflare hata iletisi.
import json
import os
import time
import urllib.error
import urllib.request

PARCA = 100
DENEME = 3
sayac = {'okunan': 0, 'yazilan': 0, 'istek': 0}


class D1Hatasi(Exception):
    pass


def hazir():
    return all(os.environ.get(k) for k in ('CF_D1_TOKEN', 'CF_HESAP', 'D1_ID'))


def _adres():
    return (f"https://api.cloudflare.com/client/v4/accounts/{os.environ['CF_HESAP']}"
            f"/d1/database/{os.environ['D1_ID']}/query")


def _hata_iletisi(govde):
    try:
        j = json.loads(govde)
        return '; '.join(str(e.get('message', '')) for e in j.get('errors') or []) or 'bilinmeyen hata'
    except (ValueError, TypeError, AttributeError):
        return 'yanıt çözülemedi'


def _istek(govde):
    veri = json.dumps(govde).encode('utf-8')
    for deneme in range(DENEME):
        istek = urllib.request.Request(_adres(), data=veri, method='POST', headers={
            'Authorization': f"Bearer {os.environ['CF_D1_TOKEN']}",
            'Content-Type': 'application/json',
            'User-Agent': 'tertremo-gunluk',
        })
        try:
            sayac['istek'] += 1
            with urllib.request.urlopen(istek, timeout=60) as y:
                j = json.loads(y.read())
        except urllib.error.HTTPError as h:
            ileti = _hata_iletisi(h.read())
            if h.code in (429, 500, 502, 503, 504) and deneme < DENEME - 1:
                time.sleep(2 ** (deneme + 1))
                continue
            raise D1Hatasi(f'D1 HTTP {h.code}: {ileti}') from None
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if deneme < DENEME - 1:
                time.sleep(2 ** (deneme + 1))
                continue
            raise D1Hatasi(f'D1 bağlantı hatası: {type(e).__name__}') from None
        if not j.get('success', False):
            raise D1Hatasi(f"D1 hata: {_hata_iletisi(json.dumps(j))}")
        sonuclar = j.get('result') or []
        for s in sonuclar:
            m = s.get('meta') or {}
            sayac['okunan'] += int(m.get('rows_read') or 0)
            sayac['yazilan'] += int(m.get('rows_written') or 0)
        return sonuclar
    raise D1Hatasi('D1: deneme bitti')


def sorgu(sql, params=()):
    """Tek ifade → satırlar (list[dict])."""
    s = _istek({'sql': sql, 'params': list(params)})
    return (s[0].get('results') if s else None) or []


def toplu(ifadeler):
    """[(sql, params), ...] → her ifadenin satırları; 100 ifadelik REST çağrıları (batch)."""
    sonuc = []
    for i in range(0, len(ifadeler), PARCA):
        parca = ifadeler[i:i + PARCA]
        s = _istek({'batch': [{'sql': q, 'params': list(p)} for q, p in parca]})
        sonuc.extend((r.get('results') or []) for r in s)
    return sonuc
