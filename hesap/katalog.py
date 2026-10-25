# Geçmiş katalog indirme ve önbellek (csv.gz).
# Türkiye: EMSC seismicportal FDSN, Türkiye kutusu + 2° (src/kaynaklar/emsc.js ile aynı kutu), M ≥ 2,0.
# Dünya: USGS FDSN, M ≥ 4,5. Parçalar dolarsa (limit) aralık ikiye bölünür. Kaynak sunuculara saygı: ≤ 2 istek/s.
# Önbellek biçimi v2 (Actions cache anahtarı katalog-v2-): `yer` sütunu (EMSC flynn_region, USGS place). v1 önbelleği
# (yer sütunu yok) okunur, yer None kalır; yeniden kaydedilince v2 biçimine geçer.
import csv
import gzip
import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from hesap.mw import mw as mw_cevir, tur_duzelt

EMSC_URL = 'https://www.seismicportal.eu/fdsnws/event/1/query'
USGS_URL = 'https://earthquake.usgs.gov/fdsnws/event/1/query'
EMSC_KUTU = {'minlat': 33.5, 'maxlat': 44.5, 'minlon': 23.5, 'maxlon': 47}
AJAN = 'tertremo (github.com/senoldak/tertremo)'
LIMIT = 20000
ARALIK_S = 0.5
DENEME = 5
SUTUNLAR = ['id', 'zaman_ms', 'enlem', 'boylam', 'derinlik', 'buyukluk', 'tur', 'mw', 'yer']

_son_istek = [0.0]


class KaynakHatasi(Exception):
    """Kaynak 200 döndü ama gövde çözülemedi (HTML hata sayfası vb.): boş sonuç sayılmaz, önbellek korunur."""


def _coz(govde, kati):
    try:
        j = json.loads(govde)
        ozellikler = j.get('features')
        if not isinstance(ozellikler, list):
            raise ValueError('features yok')
        return ozellikler
    except (ValueError, TypeError, AttributeError):
        if kati:
            raise KaynakHatasi('kaynak yanıtı çözülemedi') from None
        return []


def _getir(adres):
    """GET → gövde (bytes) ya da None (204). Hata/429/5xx'te üstel bekleme ile yeniden dener."""
    for deneme in range(DENEME):
        bekle = _son_istek[0] + ARALIK_S - time.monotonic()
        if bekle > 0:
            time.sleep(bekle)
        _son_istek[0] = time.monotonic()
        try:
            istek = urllib.request.Request(adres, headers={'User-Agent': AJAN, 'Accept': 'application/json'})
            with urllib.request.urlopen(istek, timeout=90) as y:
                if y.status == 204:
                    return None
                return y.read()
        except urllib.error.HTTPError as h:
            if h.code == 204:
                return None
            if h.code not in (429, 500, 502, 503, 504) or deneme == DENEME - 1:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if deneme == DENEME - 1:
                raise
        time.sleep(2 ** (deneme + 1))
    return None


def _iso(dt):
    return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')


def _sayi(x):
    if x is None or x == '':
        return math.nan
    try:
        return float(x)
    except (TypeError, ValueError):
        return math.nan


def _gecerli(o):
    return (math.isfinite(o['zaman_ms']) and math.isfinite(o['enlem']) and abs(o['enlem']) <= 90
            and math.isfinite(o['boylam']) and abs(o['boylam']) <= 180 and math.isfinite(o['buyukluk']))


def _derinlik(x):
    d = _sayi(x)
    return max(0.0, d) if math.isfinite(d) else 0.0


def _yer(x):
    t = str(x).strip() if x is not None else ''
    return t[:120] or None


def _olay(kaynak, kimlik, zaman_ms, enlem, boylam, derinlik, buyukluk, tur_ham, yer=None):
    tur = tur_duzelt(tur_ham)
    o = {'id': f'{kaynak}:{kimlik}', 'zaman_ms': zaman_ms, 'enlem': _sayi(enlem), 'boylam': _sayi(boylam),
         'derinlik': _derinlik(derinlik), 'buyukluk': _sayi(buyukluk), 'tur': tur, 'yer': _yer(yer)}
    if not kimlik or not _gecerli(o):
        return None
    o['mw'] = mw_cevir(o['buyukluk'], tur)[0]
    return o


def _zaman_ms(metin):
    try:
        return datetime.fromisoformat(str(metin).replace('Z', '+00:00')).timestamp() * 1000
    except ValueError:
        return math.nan


def emsc_ayristir(govde, kati=False):
    sonuc = []
    for f in _coz(govde, kati):
        p = (f or {}).get('properties') or {}
        k = ((f or {}).get('geometry') or {}).get('coordinates') or [None, None, None]
        derinlik = p.get('depth')
        if derinlik is None and len(k) > 2 and k[2] is not None:
            derinlik = -k[2]
        enlem = p.get('lat') if p.get('lat') is not None else (k[1] if len(k) > 1 else None)
        boylam = p.get('lon') if p.get('lon') is not None else (k[0] if k else None)
        o = _olay('emsc', str(p.get('unid') or f.get('id') or ''), _zaman_ms(p.get('time')),
                  enlem, boylam, derinlik, p.get('mag'), p.get('magtype'), p.get('flynn_region'))
        if o:
            sonuc.append(o)
    return sonuc


def usgs_ayristir(govde, kati=False):
    sonuc = []
    for f in _coz(govde, kati):
        p = (f or {}).get('properties') or {}
        k = (f or {}).get('geometry', {}).get('coordinates')
        if not isinstance(k, list) or len(k) < 3:
            continue
        o = _olay('usgs', str(f.get('id') or ''), _sayi(p.get('time')), k[1], k[0], k[2], p.get('mag'),
                  p.get('magType'), p.get('place'))
        if o:
            sonuc.append(o)
    return sonuc


def _parcali(url, temel, ayristir, bas, bit):
    """[bas, bit) aralığını indirir; sonuç limiti doldurursa ikiye böler."""
    q = dict(temel, starttime=_iso(bas), endtime=_iso(bit), limit=LIMIT, format=temel.get('format', 'json'))
    govde = _getir(f'{url}?{urllib.parse.urlencode(q)}')
    # None = 204 (veri yok, geçerli boş); 200 gövdesi çözülemezse KaynakHatasi
    olaylar = ayristir(govde, kati=True) if govde is not None else []
    if len(olaylar) >= LIMIT and bit - bas > timedelta(minutes=10):
        orta = bas + (bit - bas) / 2
        return _parcali(url, temel, ayristir, bas, orta) + _parcali(url, temel, ayristir, orta, bit)
    b0, b1 = bas.timestamp() * 1000, bit.timestamp() * 1000
    return [o for o in olaylar if b0 <= o['zaman_ms'] < b1]


def emsc_indir(baslangic, bitis):
    temel = dict(EMSC_KUTU, minmag=2.0, format='json', orderby='time-asc')
    return _parcali(EMSC_URL, temel, emsc_ayristir, baslangic, bitis)


def usgs_indir(baslangic, bitis):
    temel = {'minmagnitude': 4.5, 'format': 'geojson', 'orderby': 'time-asc'}
    return _parcali(USGS_URL, temel, usgs_ayristir, baslangic, bitis)


def kaydet(yol, olaylar):
    os.makedirs(os.path.dirname(yol) or '.', exist_ok=True)
    gecici = yol + '.tmp'
    with gzip.open(gecici, 'wt', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(SUTUNLAR)
        for o in sorted(olaylar, key=lambda o: o['zaman_ms']):
            w.writerow([o['id'], round(o['zaman_ms']), o['enlem'], o['boylam'], o['derinlik'], o['buyukluk'], o['tur'],
                        repr(o['mw']), o.get('yer') or ''])
    os.replace(gecici, yol)


def yukle(yol):
    if not os.path.exists(yol):
        return []
    sonuc = []
    with gzip.open(yol, 'rt', newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            sonuc.append({'id': r['id'], 'zaman_ms': float(r['zaman_ms']), 'enlem': float(r['enlem']),
                          'boylam': float(r['boylam']), 'derinlik': float(r['derinlik']),
                          'buyukluk': float(r['buyukluk']), 'tur': r['tur'], 'mw': float(r['mw']),
                          'yer': r.get('yer') or None})  # v1 önbelleğinde sütun yok
    return sonuc
