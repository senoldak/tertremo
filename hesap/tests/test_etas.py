import gzip
import json
import math
import time
from datetime import datetime, timezone

import numpy as np
import pytest

pytest.importorskip('etas')  # hesap/requirements-etas.txt
pytest.importorskip('geopandas')

from hesap import etas, katalog as kat  # noqa: E402

UTC = timezone.utc
GUN_MS = 86_400_000
# Paketin örnek yapılandırmasına yakın, dallanma ≈ 0,71 (kritik altı)
GERCEK = {'log10_mu': -5.3, 'log10_iota': None, 'log10_k0': -2.75, 'a': 1.8, 'log10_c': -2.5, 'omega': -0.02,
          'log10_tau': 3.5, 'log10_d': -0.85, 'gamma': 1.3, 'rho': 0.66}
SENTETIK_KUTU = {'minlat': 38.0, 'maxlat': 40.0, 'minlon': 30.0, 'maxlon': 32.0}
BETA = math.log(10)


def _olaylar(df):
    t = df['time'].astype('datetime64[ms]').astype('int64').to_numpy()
    return [{'id': f'sen:{i}', 'zaman_ms': float(t[i]), 'enlem': float(la), 'boylam': float(lo), 'derinlik': 10.0,
             'buyukluk': float(m), 'tur': 'Mw', 'mw': float(m), 'yer': None}
            for i, (la, lo, m) in enumerate(zip(df['latitude'], df['longitude'], df['magnitude']))]


@pytest.fixture(scope='module')
def sentetik():
    """Paketin kendi simülatörüyle bilinen parametrelerden üretilmiş ETAS katalogu (2000–2008, Mc 3,0)."""
    from datetime import datetime as dt
    from shapely.geometry import Polygon
    p = etas.paket()
    np.random.seed(1)
    kose = etas.kutu_koseleri(SENTETIK_KUTU)
    df = p.simulation.generate_catalog(Polygon(kose), dt(2000, 1, 1), dt(2008, 1, 1), GERCEK, mc=3.0 - 0.05,
                                       beta_main=BETA, delta_m=0.1, m_max=7.5)
    return _olaylar(df.sort_values('time').reset_index(drop=True))


def _uyum(olaylar, **k):
    return etas.uyum(olaylar, datetime(2008, 1, 1, tzinfo=UTC).timestamp() * 1000, 3.0, 1.0, kutu=SENTETIK_KUTU,
                     yardimci_bas=datetime(2000, 1, 1, tzinfo=UTC), birincil_bas=datetime(2001, 1, 1, tzinfo=UTC),
                     **k)


@pytest.fixture(scope='module')
def uyum_sonucu(sentetik):
    return _uyum(sentetik)


def test_parametre_geri_kazanimi(uyum_sonucu):
    p = uyum_sonucu['parametreler']
    assert p['log10_k0'] == pytest.approx(GERCEK['log10_k0'], abs=0.3)            # K
    assert p['a'] == pytest.approx(GERCEK['a'], abs=0.3)                          # α (paket a)
    assert 1 + p['omega'] == pytest.approx(1 + GERCEK['omega'], abs=0.1)          # p
    assert p['log10_c'] == pytest.approx(GERCEK['log10_c'], abs=0.5)              # c
    assert p['log10_mu'] == pytest.approx(GERCEK['log10_mu'], abs=0.2)
    assert p['log10_d'] == pytest.approx(GERCEK['log10_d'], abs=0.4)             # uzaysal çekirdek (gevşek)
    assert p['gamma'] == pytest.approx(GERCEK['gamma'], abs=0.5)
    assert p['rho'] == pytest.approx(GERCEK['rho'], abs=0.3)
    assert uyum_sonucu['dallanma'] == pytest.approx(0.705, abs=0.15)
    assert etas.makul(uyum_sonucu) == (True, '')
    assert len(uyum_sonucu['arka']) == uyum_sonucu['n']


def test_hizli_amac_paketle_ayni(sentetik):
    """HizliAmac değeri paketin neg_log_likelihood'uyla aynı; türevi sayısal türevle aynı."""
    p = etas.paket()
    h = p.inversion.ETASParameterCalculation({
        'catalog': __import__('pandas').DataFrame({
            'latitude': [o['enlem'] for o in sentetik], 'longitude': [o['boylam'] for o in sentetik],
            'time': __import__('pandas').to_datetime([o['zaman_ms'] for o in sentetik], unit='ms'),
            'magnitude': [o['mw'] for o in sentetik]}),
        'auxiliary_start': '2000-01-01', 'timewindow_start': '2001-01-01', 'timewindow_end': '2008-01-01',
        'mc': 3.0, 'delta_m': 0.1, 'coppersmith_multiplier': 100, 'shape_coords': etas.kutu_koseleri(SENTETIK_KUTU),
        'beta': BETA, 'theta_0': {k: v for k, v in GERCEK.items() if k != 'log10_iota'}})
    h.prepare()
    th0 = p.inversion.parameter_dict2array({**GERCEK})
    pij, _, kaynak, _, _ = h.expectation_step(th0, h.m_ref - h.delta_m / 2)
    amac = etas.HizliAmac(pij, kaynak, h.m_ref - h.delta_m / 2)
    for x in ([-2.75, 1.8, -2.5, -0.02, 3.5, -0.85, 1.3, 0.66], [-2.2, 1.2, -3.0, 0.15, 2.0, -0.2, 0.8, 1.1]):
        beklenen = p.inversion.neg_log_likelihood(np.array(x), pij.copy(), kaynak.copy(), h.m_ref - h.delta_m / 2)
        f, g = amac.deger_turev(np.array(x))
        assert f == pytest.approx(beklenen, rel=1e-9)
        for i in range(8):
            e = 1e-5
            x1, x2 = np.array(x, float), np.array(x, float)
            x1[i] += e
            x2[i] -= e
            sayisal = (amac.deger(x1) - amac.deger(x2)) / (2 * e)
            assert g[i] == pytest.approx(sayisal, rel=1e-4, abs=1e-3)


def test_makul_kurallari():
    iyi = {'parametreler': {k: 0.0 for k in etas.PARAMETRELER}, 'alfa': 1.0, 'p': 1.05, 'dallanma': 0.8}
    assert etas.makul(iyi) == (True, '')
    assert etas.makul({**iyi, 'alfa': 2.6})[0] is False
    assert etas.makul({**iyi, 'p': 0.89})[0] is False
    assert etas.makul({**iyi, 'dallanma': 1.0})[0] is False
    assert etas.makul({**iyi, 'dallanma': None})[0] is False
    assert etas.makul(None)[0] is False


def test_yedek_secimi():
    iyi = {'parametreler': {k: 0.0 for k in etas.PARAMETRELER}, 'alfa': 1.0, 'p': 1.05, 'dallanma': 0.8}
    kotu = {**iyi, 'alfa': 3.1}
    assert etas.uyum_sec(iyi, None) == (iyi, 'yeni')
    assert etas.uyum_sec(kotu, iyi) == (iyi, 'eski')
    assert etas.uyum_sec(kotu, None) == (None, 'poisson')
    assert etas.uyum_sec(None, None) == (None, 'poisson')


def test_olcutler_paketin_dallanma_oraniyla_ayni():
    p = etas.paket()
    o = etas.olcutler({k: v for k, v in GERCEK.items() if k != 'log10_iota'}, BETA)
    assert o['dallanma'] == pytest.approx(p.inversion.branching_ratio(p.inversion.parameter_dict2array(GERCEK), BETA))
    assert o['alfa'] == pytest.approx(1.8 - 0.66 * 1.3)
    assert o['p'] == pytest.approx(0.98)
    # α_etkin ≥ β: sonsuz dallanma → None (makul değil)
    assert etas.olcutler({**{k: v for k, v in GERCEK.items() if k != 'log10_iota'}, 'a': 4.0}, BETA)['dallanma'] is None


def _uyum_sozlugu(arka=None, kutu=SENTETIK_KUTU, mc=3.0):
    from shapely.geometry import Polygon
    p = etas.paket()
    th = {k: v for k, v in GERCEK.items() if k != 'log10_iota'}
    u = {'parametreler': th, 'beta': BETA, 'mc': mc, 'b': 1.0, 'kutu': kutu,
         'alan_km2': p.inversion.polygon_surface(Polygon(etas.kutu_koseleri(kutu))),
         'arka': [] if arka is None else arka, 'zaman': 0}
    u.update(etas.olcutler(th, BETA))
    return u


def test_simulasyon_paketin_surdurmesiyle_ayni():
    """Vektörleştirilmiş sürdürme, paketin simulate_catalog_continuation'ıyla aynı dağılımı verir (ortalamalar)."""
    import pandas as pd
    from datetime import datetime as dt, timedelta
    from shapely.geometry import Polygon
    p = etas.paket()
    u = _uyum_sozlugu()
    t0 = dt(2010, 1, 1)
    # gözlenen: 1 gün önce M6,2 + 20 gün önce M5,0 + rastgele küçükler
    r = np.random.default_rng(5)
    kay = pd.DataFrame({
        'latitude': np.r_[39.0, 38.6, r.uniform(38.2, 39.8, 30)], 'longitude': np.r_[31.0, 30.5, r.uniform(30.2, 31.8, 30)],
        'magnitude': np.r_[6.2, 5.0, np.round(3.0 + r.exponential(1 / BETA, 30), 1)],
        'time': [t0 - timedelta(days=1), t0 - timedelta(days=20)] + [t0 - timedelta(days=float(x)) for x in r.uniform(1, 300, 30)]})
    kay['xi_plus_1'] = 1.0
    kay.index = np.arange(1, len(kay) + 1)
    poly = Polygon(etas.kutu_koseleri(SENTETIK_KUTU))
    np.random.seed(11)
    n_paket = 300
    sayi_p, ilk_gun_p, buyuk_p, uzak_p = [], [], [], []
    for _ in range(n_paket):
        s = p.simulation.simulate_catalog_continuation(
            kay, auxiliary_start=t0 - timedelta(days=400), auxiliary_end=t0, polygon=poly,
            simulation_end=t0 + timedelta(days=7), parameters={**GERCEK}, mc=3.0 - 0.05, beta_main=BETA,
            m_max=etas.M_MAX + 0.05)
        s = s[s['time'] > t0]
        sayi_p.append(len(s))
        ilk_gun_p.append(int((s['time'] <= t0 + timedelta(days=1)).sum()))
        buyuk_p.append(bool((s['magnitude'] >= 4.0 - 0.05).any()))   # ≥ 1 olay ≥ Mc + 1
        if 'parent_latitude' in s:
            a = s.dropna(subset=['parent_latitude'])
            uzak_p.extend(p.inversion.haversine(np.radians(a['latitude']), np.radians(a['parent_latitude']),
                                                np.radians(a['longitude']), np.radians(a['parent_longitude'])))
    kaynak = {'t': np.array([(x - t0) / timedelta(days=1) for x in kay['time']]), 'enlem': kay['latitude'].to_numpy(),
              'boylam': kay['longitude'].to_numpy(), 'm': kay['magnitude'].to_numpy()}
    sim = etas.Simulator(u).calistir(kaynak, 20_000, np.random.default_rng(3), kayit_alt=0)
    ic = etas.kutuda(sim['enlem'], sim['boylam'], SENTETIK_KUTU)
    sayi_b = np.bincount(sim['kat'][ic], minlength=20_000)
    ilk_b = np.bincount(sim['kat'][ic & (sim['t'] <= 1)], minlength=20_000)
    for paket_dizi, biz in ((sayi_p, sayi_b), (ilk_gun_p, ilk_b)):
        se = np.std(paket_dizi) / math.sqrt(n_paket)
        assert abs(np.mean(paket_dizi) - biz.mean()) < 4 * se + 0.02 * biz.mean(), (np.mean(paket_dizi), biz.mean())
    # kutuda ≥ 1 olay ≥ Mc + 1 olan katalog kesri
    buyuk_b = np.zeros(20_000, bool)
    buyuk_b[sim['kat'][ic & (sim['m'] >= 4.0 - 0.05)]] = True
    pp = np.mean(buyuk_p)
    assert abs(pp - buyuk_b.mean()) < 4 * math.sqrt(pp * (1 - pp) / n_paket) + 0.01, (pp, buyuk_b.mean())
    # ebeveyn uzaklığı: ortanca ve %90 (km); arka plan olayları hariç
    v = ~np.isnan(sim['eb_enlem'])
    uzak_b = p.inversion.haversine(np.radians(sim['enlem'][v]), np.radians(sim['eb_enlem'][v]),
                                   np.radians(sim['boylam'][v]), np.radians(sim['eb_boylam'][v]))
    assert len(uzak_p) > 500
    for q in (50, 90):
        assert np.percentile(uzak_b, q) == pytest.approx(np.percentile(uzak_p, q), rel=0.12), q


def test_simulasyon_sure_butcesi():
    """10.000 katalog, ~20.000 gözlenen kaynak (8 yıl), Türkiye kutusu ölçeği: yerelde < 90 s (bütçe 6 dk)."""
    from shapely.geometry import Polygon
    p = etas.paket()
    r = np.random.default_rng(0)
    n_k = 20_000
    kaynak = {'t': -np.sort(r.uniform(0, 8 * 365.25, n_k)), 'enlem': r.uniform(34, 44, n_k),
              'boylam': r.uniform(24, 46, n_k), 'm': np.round(3.0 + r.exponential(1 / (0.86 * BETA), n_k), 1)}
    th = {'log10_mu': -7.6, 'log10_k0': -2.6, 'a': 1.7, 'log10_c': -2.6, 'omega': -0.05, 'log10_tau': 3.3,
          'log10_d': -0.6, 'gamma': 1.2, 'rho': 0.7}
    u = {'parametreler': th, 'beta': 0.86 * BETA, 'mc': 3.0, 'b': 0.86, 'kutu': etas.KUTU,
         'alan_km2': p.inversion.polygon_surface(Polygon(etas.kutu_koseleri())),
         'arka': np.column_stack([kaynak['enlem'][:5000], kaynak['boylam'][:5000], np.full(5000, 0.5)]).tolist()}
    u.update(etas.olcutler(th, u['beta']))
    assert u['dallanma'] < 1
    t = time.monotonic()
    sim = etas.Simulator(u).calistir(kaynak, 10_000, np.random.default_rng(1))
    sure = time.monotonic() - t
    assert sure < 90, sure
    assert sim['n'] == 10_000


@pytest.fixture(scope='module')
def bolgeler():
    return etas.Bolgeler()


def test_bolge_atama(bolgeler):
    a = bolgeler.ata([41.01, 40.80, 38.67, 38.42, 37.0, 35.2, 39.93], [28.98, 28.0, 39.22, 27.0, 35.32, 25.0, 32.85])
    assert list(a) == ['Marmara', 'Marmara', 'Doğu Anadolu', 'Ege', 'Akdeniz', None, 'İç Anadolu']
    # kıyıdan ~15 km açık deniz (İzmir Körfezi dışı) Ege'ye; Girit (35,2 K 25 D) hiçbir bölgeye sayılmaz
    assert bolgeler.ata([38.6], [26.45])[0] == 'Ege'
    assert len(bolgeler.adlar) == 7


def test_olasiliklar_katalog_kesri(bolgeler):
    sim = {'n': 4, 'kat': np.array([0, 0, 1, 2, 3]), 'enlem': np.array([41.0, 41.0, 38.4, 38.67, 20.0]),
           'boylam': np.array([29.0, 29.0, 27.1, 39.22, 20.0]), 'm': np.array([5.0, 6.1, 4.9, 4.96, 7.0]),
           't': np.zeros(5)}
    o = etas.olasiliklar(sim, bolgeler)
    # katalog 0: Marmara M5 ve M6; katalog 1: M4,9 (sayılmaz); katalog 2: Doğu Anadolu 4,96 → kutu 5,0; 3: kutu dışı
    assert o['turkiye']['p5'] == pytest.approx(2 / 4)
    assert o['turkiye']['p6'] == pytest.approx(1 / 4)
    assert o['bolgeler']['Marmara']['p5'] == pytest.approx(1 / 4)
    assert o['bolgeler']['Doğu Anadolu']['p5'] == pytest.approx(1 / 4)
    assert o['bolgeler']['Ege']['p5'] == 0


def test_poisson_olasilik():
    # λ(Mc=3) = 100/yıl, b = 1 → λ(5) = 1/yıl → 7 gün: 1 − exp(−7/365,25)
    assert etas.poisson_olasilik(100, 3.0, 1.0, 5.0) == pytest.approx(1 - math.exp(-7 / 365.25))
    assert etas.poisson_olasilik(100, 3.0, 1.0, 6.0) == pytest.approx(1 - math.exp(-0.1 * 7 / 365.25))


def test_poisson_taban_bagimsiz_olaylardan(bolgeler):
    yil = 365.25 * GUN_MS
    z = np.arange(10) * yil / 10
    e, bo = np.full(10, 41.0), np.full(10, 29.0)
    m = np.array([3.0] * 10)
    bag = np.array([True] * 5 + [False] * 5)
    t = etas.poisson_taban(z, e, bo, m, bag, 3.0, 1.0, bolgeler, 0, yil)
    assert t['turkiye']['lambda_mc'] == pytest.approx(5)
    assert t['bolgeler']['Marmara']['lambda_mc'] == pytest.approx(5)
    assert t['bolgeler']['Ege']['lambda_mc'] == 0
    assert t['turkiye']['p5'] == pytest.approx(etas.poisson_olasilik(5, 3.0, 1.0, 5.0))


def _olay(ms, m, e=39.0, b=35.0):
    return {'id': f'x:{ms}', 'zaman_ms': float(ms), 'enlem': e, 'boylam': b, 'mw': m}


def test_gizli_kayit_haftada_bir_ve_gozlem():
    pzt = datetime(2026, 10, 26, 3, tzinfo=UTC).timestamp() * 1000  # pazartesi
    tah = {'p5': 0.2, 'p6': 0.02, 'norm5': 0.15, 'norm6': 0.01, 'bolgeler': {}}
    k = etas.gizli_kayit_guncelle([], pzt, tah, [])
    k = etas.gizli_kayit_guncelle(k, pzt + GUN_MS, tah, [])  # aynı hafta: eklenmez
    assert len(k) == 1 and k[0]['hafta'] == '2026-10-26' and 'gozlenen5' not in k[0]
    olaylar = [_olay(pzt + 2 * GUN_MS, 5.3), _olay(pzt + 8 * GUN_MS, 6.5)]
    k = etas.gizli_kayit_guncelle(k, pzt + 7 * GUN_MS + 1000, tah, olaylar)
    assert len(k) == 2
    assert k[0]['gozlenen5'] is True and k[0]['gozlenen6'] is False and k[0]['enBuyuk'] == pytest.approx(5.3)
    assert k[1].get('gozlenen5') is None
    # Poisson modunda yeni kayıt yok
    assert len(etas.gizli_kayit_guncelle(k, pzt + 14 * GUN_MS, None, olaylar)) == 2


def test_kapi_gecti_ve_sekiz_hafta():
    d = {'gecti': True, 'ozet': 'x', 'tarih': 1000, 'surum': etas.MODEL_SURUM}
    kayit = [{'baslangic': 1000 + i, 'gozlenen5': False, 'model': etas.MODEL_SURUM} for i in range(8)]
    assert etas.kapi(d, kayit)['yayin'] is True
    assert etas.kapi(d, kayit[:7])['yayin'] is False
    assert etas.kapi({**d, 'gecti': False}, kayit)['yayin'] is False
    # doğrulamadan önceki ya da başka model sürümündeki haftalar sayılmaz
    eski = [{**k, 'baslangic': 10} for k in kayit]
    assert etas.kapi(d, eski)['gizliHafta'] == 0
    assert etas.kapi(d, [{**k, 'model': 'etas-0'} for k in kayit])['gizliHafta'] == 0
    # başka model sürümünün doğrulaması sayılmaz
    eski_surum = etas.kapi({**d, 'surum': 'etas-1'}, kayit)
    assert eski_surum['gecti'] is None and eski_surum['yayin'] is False and 'eski model' in eski_surum['ozet']
    assert etas.kapi({k: v for k, v in d.items() if k != 'surum'}, kayit)['yayin'] is False
    bos = etas.kapi(None, kayit)
    assert bos['gecti'] is None and bos['yayin'] is False


def test_uyum_gerekli():
    son = {'zaman': datetime(2026, 10, 20, 3, tzinfo=UTC).timestamp() * 1000, 'surum': etas.MODEL_SURUM}
    cars = datetime(2026, 10, 21, 3, tzinfo=UTC).timestamp() * 1000
    paz = datetime(2026, 10, 25, 3, tzinfo=UTC).timestamp() * 1000
    assert etas.uyum_gerekli({}, [], cars)[0] is True
    assert etas.uyum_gerekli({'son': son}, [], cars)[0] is False
    assert etas.uyum_gerekli({'son': {**son, 'surum': 'etas-1'}}, [], cars)[0] is True   # sürüm değişti
    assert etas.uyum_gerekli({'son': son}, [], paz)[0] is True
    assert etas.uyum_gerekli({'son': son}, [_olay(son['zaman'] + GUN_MS, 5.5)], cars)[0] is True
    assert etas.uyum_gerekli({'son': son}, [_olay(son['zaman'] + GUN_MS, 5.4)], cars)[0] is False
    assert etas.uyum_gerekli({'son': son}, [_olay(son['zaman'] + GUN_MS, 6.0, e=20.0)], cars)[0] is False


def _onbellek(tmp_path, durum=None):
    r = np.random.default_rng(2)
    bas = datetime(2018, 1, 1, tzinfo=UTC).timestamp() * 1000
    n = 3000
    t = np.sort(r.uniform(bas, bas + 8.7 * 365.25 * GUN_MS, n))
    m = np.round(2.0 + r.exponential(1 / BETA, n), 1)
    olaylar = [{'id': f'emsc:{i}', 'zaman_ms': float(t[i]), 'enlem': float(r.uniform(36, 42)),
                'boylam': float(r.uniform(26, 44)), 'derinlik': 10.0, 'buyukluk': float(m[i]), 'tur': 'Mw',
                'mw': float(m[i]), 'yer': None} for i in range(n)]
    kat.kaydet(str(tmp_path / 'tr.csv.gz'), olaylar)
    if durum is not None:
        with gzip.open(tmp_path / 'etas-durum.json.gz', 'wt', encoding='utf-8') as f:
            json.dump(durum, f)


def test_ana_simulasyon_kart_veri_blogu(tmp_path):
    u = _uyum_sozlugu(kutu=etas.KUTU, mc=2.5)
    u['arka'] = [[39.0, 35.0, 0.5], [38.5, 27.0, 0.5]]
    u['zaman'] = datetime(2026, 9, 1, tzinfo=UTC).timestamp() * 1000
    u['n'], u['sure_s'], u['surum'] = 100, 1.0, etas.MODEL_SURUM
    _onbellek(tmp_path, {'son': u, 'son_iyi': u})
    (tmp_path / 'kart-veri.json').write_text(json.dumps({'gr': {'b': 1}}), encoding='utf-8')
    assert etas.ana(['--onbellek', str(tmp_path), '--uyum', 'yok', '--n', '2000', '--simdi', '2026-09-28T03:00:00',
                     '--tohum', '1']) == 0
    kv = json.loads((tmp_path / 'kart-veri.json').read_text(encoding='utf-8'))
    assert kv['gr'] == {'b': 1}
    e = kv['etas']
    assert e['mod'] == 'etas' and e['simulasyon'] == 2000
    assert 0 <= e['turkiye']['p5'] <= 1 and 0 <= e['turkiye']['norm5'] <= 1
    assert e['turkiye']['p6'] <= e['turkiye']['p5']
    assert [b['ad'] for b in e['bolgeler']] == ['Marmara', 'Ege', 'Akdeniz', 'İç Anadolu', 'Karadeniz',
                                                 'Doğu Anadolu', 'Güneydoğu Anadolu']
    assert e['uyum']['durum'] == 'son' and e['uyum']['mc'] == 2.5
    assert e['kapi'] == {'gecti': None, 'ozet': 'doğrulama yapılmadı', 'gizliHafta': 0, 'yayin': False}
    assert e['bitis'] - e['baslangic'] == 7 * GUN_MS
    assert len(kv['etasGizliKayit']) == 1 and kv['etasGizliKayit'][0]['hafta'] == '2026-09-28'
    assert 'simulasyon_s' in e['sure']


def test_ana_uyum_yoksa_poisson(tmp_path):
    _onbellek(tmp_path)
    assert etas.ana(['--onbellek', str(tmp_path), '--uyum', 'yok', '--simdi', '2026-09-28T03:00:00']) == 0
    kv = json.loads((tmp_path / 'kart-veri.json').read_text(encoding='utf-8'))
    e = kv['etas']
    assert e['mod'] == 'poisson' and e['neden'] == 'bu hafta model güncellenemedi'
    assert e['turkiye']['p5'] is None and e['turkiye']['norm5'] > 0
    assert e['uyum'] is None
    assert kv['etasGizliKayit'] == []


def _parcali_gr(n, kirilma, b1, b2, alt=1.95, tohum=7):
    """N(≥m) ∝ 10^(−b1(m−alt)) kırılmaya kadar, sonra 10^(−b2(m−kırılma)) (kutulu 0,1)."""
    r = np.random.default_rng(tohum)
    u = r.uniform(size=n)
    p_k = 10 ** (-b1 * (kirilma - alt))
    m = np.where(u > p_k, alt - np.log10(u) / b1, kirilma - np.log10(u / p_k) / b2)
    return np.round(m, 1)


def test_mc_mbs_tam_gr():
    m = np.round(1.95 + np.random.default_rng(7).exponential(1 / BETA, 20_000), 1)
    assert 2.0 <= etas.mc_mbs(m) <= 2.3


def test_mc_mbs_kalici_plato_sahte_alt_platoyu_atlar():
    # ML/mb karışımı gibi: alt magnitüdlerde düz (b 0,8), 3,5'ten sonra dik (b 1,2)
    m = _parcali_gr(200_000, 3.5, 0.8, 1.2)
    assert 3.4 <= etas.mc_mbs(m) <= 4.0


def test_mc_egitim_yalniz_egitim_donemi_ve_yedek():
    yil = 365.25 * GUN_MS
    bas = datetime(2018, 1, 1, tzinfo=UTC).timestamp() * 1000
    egitim = _parcali_gr(100_000, 3.5, 0.8, 1.2)
    sonra = np.round(1.95 + np.random.default_rng(1).exponential(1 / BETA, 100_000), 1)  # 2022 sonrası: Mc 2,0
    z = np.r_[np.linspace(bas, bas + 3.9 * yil, egitim.size), np.linspace(bas + 4.1 * yil, bas + 8 * yil, sonra.size)]
    mc, ham = etas.mc_egitim(z, np.r_[egitim, sonra])
    assert mc == ham and 3.4 <= mc <= 4.0
    assert etas.mc_egitim(np.array([bas + 5 * yil]), np.array([3.0])) == (etas.MC_YEDEK, pytest.approx(math.nan, nan_ok=True))


def test_ana_eski_surum_uyumunu_kullanmaz(tmp_path):
    u = _uyum_sozlugu(kutu=etas.KUTU, mc=2.5)
    u.update(arka=[[39.0, 35.0, 0.5]], zaman=datetime(2026, 9, 1, tzinfo=UTC).timestamp() * 1000, n=100, sure_s=1.0,
             surum='etas-1')
    _onbellek(tmp_path, {'son': u, 'son_iyi': u})
    assert etas.ana(['--onbellek', str(tmp_path), '--uyum', 'yok', '--simdi', '2026-09-28T03:00:00']) == 0
    e = json.loads((tmp_path / 'kart-veri.json').read_text(encoding='utf-8'))['etas']
    assert e['mod'] == 'poisson' and e['uyum'] is None
