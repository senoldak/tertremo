import json
from datetime import datetime, timezone

import numpy as np
import pytest

from hesap import kartblok
from hesap.hucre import hucre_istatistik

UTC = timezone.utc
YIL_MS = 365.25 * 24 * 3600 * 1000


def gr_ornek(n, b, mc, dm=0.1, tohum=1):
    r = np.random.default_rng(tohum)
    m = (mc - dm / 2) + r.exponential(1 / (b * np.log(10)), n)
    return np.round(np.round(m / dm) * dm, 1)


def ms(*a):
    return datetime(*a, tzinfo=UTC).timestamp() * 1000


def test_ay_araligi_onceki_takvim_ayi_tsi():
    # 1 Ekim 2026 03:00 UTC = 06:00 TSİ → önceki ay Eylül
    bas, bit, ad = kartblok.ay_araligi(ms(2026, 10, 1, 3))
    assert ad == '2026-09'
    assert bas == ms(2026, 8, 31, 21)   # 1 Eylül 00:00 TSİ
    assert bit == ms(2026, 9, 30, 21)   # 1 Ekim 00:00 TSİ
    # ayın son günü 22:00 UTC = 1'i 01:00 TSİ: TSİ'ye göre yeni ay başlamış
    assert kartblok.ay_araligi(ms(2026, 9, 30, 22))[2] == '2026-09'
    # yıl devri
    assert kartblok.ay_araligi(ms(2027, 1, 5, 12))[2] == '2026-12'


def test_gr_blogu_sema_ve_b():
    m = gr_ornek(6000, 1.0, 2.0)
    blok = kartblok.gr_blogu(m, '2026-09', 2.0)
    assert blok['pencere'] == 'son 12 ay'
    assert set(blok) >= {'ay', 'n', 'toplam', 'mc', 'b', 'sigma', 'dm', 'histogram'}
    assert blok['ay'] == '2026-09'
    assert blok['mc'] == 2.0
    assert blok['b'] == pytest.approx(1.0, abs=0.08)
    assert 0 < blok['sigma'] < 0.1
    assert blok['dm'] == 0.1
    assert sum(n for _, n in blok['histogram']) == blok['toplam'] == 6000
    assert blok['n'] == sum(n for mm, n in blok['histogram'] if mm >= blok['mc'] - 1e-9)
    json.dumps(blok)


def test_gr_blogu_az_veri_none():
    assert kartblok.gr_blogu(gr_ornek(30, 1.0, 2.0), '2026-09', 2.0) is None
    assert kartblok.gr_blogu(np.array([]), '2026-09', 2.0) is None
    assert kartblok.gr_blogu(gr_ornek(6000, 1.0, 2.0), '2026-09', float('nan')) is None


def test_gr_blogu_katalog_mc_tabani():
    # Mc verilen katalog tamlığı: altındaki eksik kayıt b'yi çekmez (MAXC 2,2 b'yi aşağı çekerdi)
    r = np.random.default_rng(2)
    ust = gr_ornek(2500, 1.1, 4.0, tohum=4)
    alt = np.round(np.round(r.uniform(2.0, 3.9, 4000) / 0.1) * 0.1, 1)
    blok = kartblok.gr_blogu(np.concatenate([alt, ust]), '2026-09', 4.0)
    assert blok['mc'] == 4.0 and blok['n'] == 2500
    assert blok['b'] == pytest.approx(1.1, abs=0.1)


def test_hucre_blogu_hucre_tablosuyla_ayni():
    r = np.random.default_rng(3)
    n = 4000
    simdi = ms(2026, 10, 1)
    bas = simdi - 3 * YIL_MS
    z = bas + r.random(n) * (simdi - bas)
    e = 38.0 + r.random(n) * 0.9        # tek hücre 38_27 + az olaylı 40_30
    bo = 27.0 + r.random(n) * 0.9
    m = gr_ornek(n, 1.0, 2.0, tohum=4)
    e[:20], bo[:20] = 40.5, 30.5
    hs = hucre_istatistik(z, e, bo, m, np.ones(n, bool), 'tr', bas, simdi)
    liste = kartblok.hucre_blogu(hs, simdi, bas)
    assert liste['baslangic'] == bas and liste['hesap'] == simdi
    sat = {s['anahtar']: s for s in liste['hucreler']}
    assert set(sat) == {'38_27', '40_30'}
    ana = sat['38_27']
    ref = next(h for h in hs if h['anahtar'] == '38_27')
    assert ana['b'] == pytest.approx(ref['b'], abs=1e-4) and ana['lambda'] == pytest.approx(ref['lambda'], abs=1e-4)
    assert ana['n'] == ref['n'] and ana['mc'] == ref['mc'] and ana['sigma_b'] == pytest.approx(ref['sigma_b'], abs=1e-4)
    assert ana['n'] >= 50 and ana['b'] is not None
    assert sat['40_30']['b'] is None       # n < 50: b yok
    json.dumps(liste)


def test_hucre_blogu_dunya_hucreleri_yok():
    h = [{'katalog': 'dunya', 'anahtar': '10_20', 'mc': 4.5, 'b': 1.0, 'sigma_b': 0.1, 'n': 80, 'lambda': 3.0}]
    assert kartblok.hucre_blogu(h, 1.0, 0.0)['hucreler'] == []
