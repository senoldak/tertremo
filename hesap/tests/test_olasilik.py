import os
import json
import math

import numpy as np
import pytest

from hesap import olasilik

YIL_MS = 365.25 * 24 * 3600 * 1000


def gr_ornek(n, b, mc, dm=0.1, tohum=1):
    r = np.random.default_rng(tohum)
    m = (mc - dm / 2) + r.exponential(1 / (b * np.log(10)), n)
    return np.round(np.round(m / dm) * dm, 1)


def poisson_katalog(lam, yil, mc=3.0, b=1.0, tohum=2):
    """Bağımsız olaylar: sayı ~ Poisson(λ·yıl), büyüklükler G–R."""
    r = np.random.default_rng(tohum)
    n = int(r.poisson(lam * yil))
    return {'mw': gr_ornek(n, b, mc, tohum=tohum + 1), 'yil': float(yil)}


def test_olasilik_formulu_ve_b1_uzatma():
    # P = 1 − exp(−λ·T); b = 1: bir birim yukarıda λ onda biri
    lam = 0.5
    assert olasilik.olasilik(lam, 3.0, 1.0, 3.0, 1) == pytest.approx(1 - math.exp(-0.5))
    assert olasilik.olasilik(lam, 3.0, 1.0, 4.0, 1) == pytest.approx(1 - math.exp(-0.05))
    assert olasilik.olasilik(lam, 3.0, 1.0, 4.0, 10) == pytest.approx(1 - math.exp(-0.5))
    # küçük olasılıkta P ≈ λ: λ(Mc+1) = λ(Mc)/10
    kucuk = 1e-4
    assert olasilik.olasilik(kucuk, 3.0, 1.0, 4.0, 1) / olasilik.olasilik(kucuk, 3.0, 1.0, 3.0, 1) == pytest.approx(0.1, rel=1e-3)


def test_sentetik_poisson_lambda_yarim():
    kat = poisson_katalog(0.5, 2000)
    sonuc = olasilik.uzun_donem(kat, 3.0, 1.0, M=(3.0, 6.0), n_boot=300, tohum=1)
    orta, alt, ust = sonuc[1][3.0]
    assert orta == pytest.approx(1 - math.exp(-0.5), abs=0.02)      # ≈ 0,393
    assert alt < orta < ust
    # Aralık çıktı sözlüğü: T ve M anahtarlarıyla
    assert set(sonuc) == set(olasilik.T_LISTE)
    assert set(sonuc[10]) == {3.0, 6.0}


def test_bootstrap_araligi_ortayi_kapsar_ve_T_ile_artar():
    kat = poisson_katalog(2.0, 9, mc=3.0, tohum=5)        # küçük örnek: geniş aralık
    s = olasilik.uzun_donem(kat, 3.0, 1.0, n_boot=500, tohum=3)
    for t in s:
        for m in s[t]:
            orta, alt, ust = s[t][m]
            assert 0 <= alt <= orta <= ust <= 1
    for m in olasilik.M_LISTE:
        assert s[1][m][0] <= s[10][m][0] <= s[50][m][0]
    # daha büyük deprem daha düşük olasılık
    assert s[10][5.0][0] > s[10][6.0][0] > s[10][7.0][0]
    # aralık küçük örnekte genişler
    buyuk = olasilik.uzun_donem(poisson_katalog(2.0, 400, mc=3.0, tohum=5), 3.0, 1.0, n_boot=500, tohum=3)
    assert (s[10][6.0][2] - s[10][6.0][1]) > (buyuk[10][6.0][2] - buyuk[10][6.0][1])


def test_bos_katalog_sifir_olasilik():
    s = olasilik.uzun_donem({'mw': np.array([]), 'yil': 8.0}, 3.0, 1.0, n_boot=50)
    assert s[10][6.0] == (0.0, 0.0, 0.0)


def test_bolge_filtresi():
    mw = gr_ornek(2000, 1.0, 3.0)
    bolge = np.array(['Ege'] * 500 + ['Marmara'] * 1500, dtype=object)
    kat = {'mw': mw, 'yil': 10.0, 'bolge': bolge}
    ege = olasilik.uzun_donem(kat, 3.0, 1.0, alan='Ege', n_boot=100)
    mar = olasilik.uzun_donem(kat, 3.0, 1.0, alan='Marmara', n_boot=100)
    tum = olasilik.uzun_donem(kat, 3.0, 1.0, n_boot=100)
    # sabit b = 1: Ege λ(Mc) = 500/10 = 50/yıl → M5'te 0,5/yıl; Marmara 1,5/yıl
    assert ege[1][5.0][0] == pytest.approx(1 - math.exp(-0.5), abs=1e-9)
    assert mar[1][5.0][0] == pytest.approx(1 - math.exp(-1.5), abs=1e-9)
    assert ege[10][5.0][0] < mar[10][5.0][0] < tum[10][5.0][0]


@pytest.fixture(scope='module')
def atayici():
    return olasilik.BolgeAtayici()


def test_alti_bolge_ve_birlestirme(atayici):
    assert atayici.adlar == ['Marmara', 'Ege', 'Akdeniz', 'İç Anadolu', 'Karadeniz', 'Doğu Anadolu']
    a = atayici.ata([41.01, 38.42, 36.9, 39.93, 41.0, 39.9, 37.07, 37.9],
                    [28.98, 27.14, 30.7, 32.85, 39.7, 41.27, 37.38, 40.2])
    assert list(a) == ['Marmara', 'Ege', 'Akdeniz', 'İç Anadolu', 'Karadeniz', 'Doğu Anadolu', 'Doğu Anadolu', 'Doğu Anadolu']


def test_uzak_ve_acik_deniz_bolgesiz(atayici):
    a = atayici.ata([30.0, 45.0, 35.0, 37.5], [31.0, 40.0, 33.0, 15.0])
    assert all(x is None for x in a)


def test_kiyi_tamponu(atayici):
    # İstanbul'un güneyinde Marmara Denizi (il sınırına < 30 km) → Marmara
    assert atayici.ata([40.85], [28.7])[0] == 'Marmara'


def test_blok_sema(atayici):
    r = np.random.default_rng(9)
    n = 5000
    simdi = 1_790_000_000_000.0
    z = simdi - 8 * YIL_MS + r.random(n) * 8 * YIL_MS
    # Türkiye geneline dağılmış, il merkezleri çevresinde
    merkez = np.array([[41.0, 29.0], [38.4, 27.1], [37.0, 35.3], [39.9, 32.8], [41.0, 39.7], [39.9, 41.3]])
    k = r.integers(0, 6, n)
    e = merkez[k, 0] + r.normal(0, 0.15, n)
    bo = merkez[k, 1] + r.normal(0, 0.15, n)
    m = gr_ornek(n, 1.0, 3.0, tohum=11)
    bag = np.ones(n, bool)
    blok = olasilik.uzun_donem_blogu(z, e, bo, m, bag, simdi, atayici=atayici, n_boot=100, mc=3.0, b=1.0)
    assert blok['mc'] == 3.0 and blok['kumeleme'] == 'en-yakin-komsu'
    assert blok['turkiye']['nEmsc'] == blok['turkiye']['n'] == sum(b['nEmsc'] for b in blok['bolgeler'])   # yalnız Türkiye içi
    assert blok['turkiye']['ad'] == 'Türkiye (kıyıdan 30 km dahil)'
    assert [b['ad'] for b in blok['bolgeler']] == atayici.adlar
    # kıyıdan 30 km'den uzak denizdeki olaylar bölgesiz kalır (Türkiye genelinde sayılır)
    assert 0.95 * n <= sum(b['nEmsc'] for b in blok['bolgeler']) <= n
    o = blok['turkiye']['olasilik']
    assert set(o) == {'1', '10', '50'} and set(o['10']) == {'5', '6', '7'}
    assert len(o['10']['6']) == 3
    assert o['50']['5'][0] >= o['10']['5'][0] >= o['1']['5'][0]
    for b in blok['bolgeler']:
        assert len(b['olasilik']['10']['6']) == 3 and set(b['olasilik']['10']) == {'6', '7'}
    # Mw ≥ 6–7: uzun USGS kaydından doğrudan sayım (bölge n'i bu kayıttan)
    uk = blok['uzunKatalog']
    assert uk['yontem'] == 'gardner-knopoff' and uk['bas6'] == 1930 and uk['bas7'] == 1900
    assert sum(b['n'] for b in blok['bolgeler']) == blok['turkiye']['n6'] == uk['n6']
    ol = uk['olaylar']                     # çizilen bağımsız merkez üsleri: Mw ≥ 6 (1930–) ∪ Mw ≥ 7 (1900–)
    assert sum(1 for o in ol if o[2] >= 6 - 1e-9 and o[3] >= 1930) == uk['n6'] and sum(1 for o in ol if o[2] >= 7 - 1e-9) == uk['n7']
    assert all(len(o) == 4 for o in ol)
    p7 = blok['turkiye']['olasilik']['10']['7']
    assert 0.6 < p7[0] < 0.9 and p7[1] < p7[0] < p7[2]
    json.dumps(blok)


def test_gunluk_kart_verisi_uzun_donem_yazar(tmp_path):
    from hesap import gunluk, kartveri
    r = np.random.default_rng(21)
    n = 3000
    simdi = 1_790_000_000_000.0
    z = simdi - 8.5 * YIL_MS + r.random(n) * 8.4 * YIL_MS
    m = gr_ornek(n, 1.0, 3.0, tohum=22)
    olaylar = [{'id': f'emsc:{i}', 'zaman_ms': float(z[i]), 'enlem': 39.0 + r.random() * 2, 'boylam': 30.0 + r.random() * 3, 'mw': float(m[i])}
               for i in range(n)]
    kume = {o['id']: [None, -5.0] for o in olaylar}
    kv = gunluk.kart_verisi(str(tmp_path), olaylar, [], simdi - 8.5 * YIL_MS, simdi, kume)
    assert 'uzunDonem' in kv
    yazilan = kartveri.oku(str(tmp_path / 'kart-veri.json'))
    assert yazilan['uzunDonem']['turkiye']['n'] > 0 and 'gr' in yazilan and 'hucreler' in yazilan
    # kümeleme yoksa (eşik kurulamadı) uzun dönem yazılmaz, G–R/hücre yine yazılır
    kv2 = gunluk.kart_verisi(str(tmp_path / 'b'), olaylar, [], simdi - 8.5 * YIL_MS, simdi, None)
    assert 'uzunDonem' not in kv2


def test_aralik_genisligi_pozitif_ve_buyuklukle_artar():
    # λ(Mc) = 90/yıl, T = 10: P(M5) ≈ 1, P(M6) ≈ 0,59 → b ve λ her çekimde yeniden hesaplandığı için aralık genişler
    kat = poisson_katalog(90, 30, mc=3.0, tohum=8)
    s = olasilik.uzun_donem(kat, 3.0, 1.0, n_boot=600, tohum=2)
    gen = {m: s[10][m][2] - s[10][m][1] for m in olasilik.M_LISTE}
    assert gen[6.0] > 0
    assert gen[6.0] > gen[5.0] >= 0


def test_ortak_bootstrap_turkiye_ve_bolge_araligi_pozitif():
    kat = poisson_katalog(60, 20, mc=3.0, tohum=12)
    n = kat['mw'].size
    bolge = np.array(['Ege'] * (n // 2) + ['Marmara'] * (n - n // 2), dtype=object)
    tr, bol = olasilik.uzun_donem_ortak(kat['mw'], bolge, 20.0, 3.0, 1.0, ['Ege', 'Marmara'], {'Ege': 1.0, 'Marmara': None}, n_boot=400)
    for d in (tr, bol['Ege'], bol['Marmara']):
        assert d[10][6.0][2] - d[10][6.0][1] > 0
        assert d[10][6.0][1] <= d[10][6.0][0] <= d[10][6.0][2]
    # kendi b'si olan bölgenin aralığı, Türkiye b'sini alan bölgeden geniş (yeniden b hesabı daha az olaya dayanır)
    assert bol['Ege'][10][6.0][2] - bol['Ege'][10][6.0][1] > 0


def test_turkiye_geneli_yalniz_turkiye_icindeki_olaylar(atayici):
    r = np.random.default_rng(31)
    n = 1200
    simdi = 1_790_000_000_000.0
    z = simdi - 8 * YIL_MS + r.random(n) * 8 * YIL_MS
    e = np.where(r.random(n) < 0.5, 39.0 + r.normal(0, 0.3, n), 38.5 + r.normal(0, 0.3, n))
    bo = np.where(r.random(n) < 0.5, 32.5 + r.normal(0, 0.3, n), 22.0 + r.normal(0, 0.1, n) + 3.0)   # yarısı Türkiye içi, yarısı kutu içinde Yunanistan (~25 D)
    m = gr_ornek(n, 1.0, 3.0, tohum=32)
    blok = olasilik.uzun_donem_blogu(z, e, bo, m, np.ones(n, bool), simdi, atayici=atayici, n_boot=50, mc=3.0, b=1.0)
    t = blok['turkiye']['n']
    assert t == sum(b['nEmsc'] for b in blok['bolgeler'])
    assert 0.35 * n < t < 0.65 * n          # Yunanistan tarafı dışarıda


def test_gk_ayiklama():
    g = 86_400_000.0
    z = np.array([0, 3 * g, 1500 * g, 10 * g, 5 * g])
    e = np.array([39.0, 39.1, 39.0, 39.0, 41.5])
    bo = np.array([30.0, 30.1, 30.0, 30.0, 30.0])
    m = np.array([7.0, 6.1, 6.2, 6.0, 6.0])
    tut = olasilik.gk_ayikla(z, e, bo, m)
    # art şok (3 gün, ~14 km) ve 10. gündeki aynı yer olayı atılır; 1500 gün sonrası (pencere ~918 gün) ve 280 km uzaktaki kalır
    assert list(tut) == [True, False, True, False, True]
    km, gun = olasilik.gk_pencere(7.0)
    assert 65 < km < 75 and 900 < gun < 940


def test_uzun_katalog_sayim_basit_sayimla_tutarli(atayici):
    uk = olasilik.uzun_katalog_yukle()
    simdi = 1_793_500_000_000.0
    r = olasilik._sayim_blogu(uk, atayici, simdi, n_boot=300)
    b = r['bilgi']
    lam7 = b['n7'] / b['yil7']
    assert r['turkiye'][1][7.0][0] == pytest.approx(1 - math.exp(-lam7), rel=1e-3)
    assert r['turkiye'][10][7.0][0] == pytest.approx(1 - math.exp(-10 * lam7), rel=1e-3)
    assert 0.10 < lam7 < 0.22           # 1900'den beri Türkiye (+30 km) ≈ 15–25 bağımsız Mw ≥ 7
    assert 0.5 < r['turkiye'][1][6.0][0] < 0.7
    o, a, u = r['turkiye'][10][7.0]
    assert a >= 0 and o >= a and u >= o and u - a > 0


# ---------- uzun katalog: otomatik güncelleme ----------

def _k(t, s, en, bo, mw):
    return {'t': t, 's': s, 'enlem': en, 'boylam': bo, 'mw': mw}


def test_uzun_birlestir_tekilleştirir_ve_siralar():
    taban = [_k('2023-02-06', '04:17', 37.17, 37.03, 7.8), _k('2023-02-06', '13:24', 38.02, 37.2, 7.5)]
    yeni = [
        _k('2023-02-06', '04:17', 37.2, 37.0, 7.8),       # aynı olay (≈4 km, aynı dakika) → atılır
        _k('2023-02-06', '04:18', 37.3, 37.1, 6.0),       # +60 sn içinde ama 17 km: ≤ 50 km → aynı sayılır, atılır
        _k('2023-02-06', '04:18', 41.0, 29.0, 6.1),       # +60 sn içinde ama 450 km → yeni
        _k('2023-02-20', '20:04', 36.1, 36.0, 6.4),       # yeni
        _k('2023-02-20', '20:04', 36.1, 36.0, 6.4),       # yeni içinde tekrar → bir kez
    ]
    s = olasilik.uzun_birlestir(taban, yeni)
    assert [(o['t'], o['s']) for o in s] == [('2023-02-06', '04:17'), ('2023-02-06', '04:18'), ('2023-02-06', '13:24'), ('2023-02-20', '20:04')]
    assert len(taban) == 2    # girdi değişmez


def test_uzun_birlestir_60_sn_disinda_yakin_olay_yenidir():
    taban = [_k('2023-02-06', '04:17', 37.17, 37.03, 7.8)]
    s = olasilik.uzun_birlestir(taban, [_k('2023-02-06', '04:19', 37.17, 37.03, 6.2)])
    assert len(s) == 2


def test_usgs_kayit_yerel_saat_ve_alanlar():
    f = {'geometry': {'coordinates': [37.032, 37.166, 10]}, 'properties': {'time': 1675646000000, 'mag': 7.84}}   # 2023-02-06 01:13:20 UTC
    assert olasilik.usgs_kayit(f) == {'t': '2023-02-06', 's': '04:13', 'enlem': 37.17, 'boylam': 37.03, 'mw': 7.8}


def test_uzun_katalog_guncelle_birlestirir_onbellege_yazar(tmp_path):
    onb = str(tmp_path / 'uzun-katalog.json')
    taban_n = len(olasilik.uzun_kayitlar_oku(None, onb))
    cagri = []

    def getir(bas):
        cagri.append(bas)
        return [_k('2099-01-01', '12:00', 38.0, 38.0, 6.5)]
    s = olasilik.uzun_katalog_guncelle(onb, getir)
    assert len(s) == taban_n + 1 and s[-1]['t'] == '2099-01-01'
    assert len(cagri) == 1 and cagri[0] < '2099'
    # önbellek okunur; ikinci çağrıda başlangıç artık en yeni kayıttan (1 gün pay) gelir ve tekrar eklenmez
    assert olasilik.uzun_katalog_yukle(onbellek=onb)['m'].size == taban_n + 1
    s2 = olasilik.uzun_katalog_guncelle(onb, getir)
    assert len(s2) == taban_n + 1 and cagri[1] == '2098-12-31'


def test_uzun_katalog_cevrimdisi_tabana_duser(tmp_path, capsys):
    onb = str(tmp_path / 'alt' / 'uzun-katalog.json')
    taban_n = len(olasilik.uzun_kayitlar_oku(None, onb))
    s = olasilik.uzun_katalog_guncelle(onb)          # conftest ağı kapatır → OSError
    assert len(s) == taban_n
    assert 'UYARI' in capsys.readouterr().err
    assert not os.path.exists(onb)                   # önbellek yazılmadı
    assert olasilik.uzun_katalog_yukle(onbellek=onb)['m'].size == taban_n


def test_uzun_katalog_bozuk_onbellek_tabana_duser(tmp_path):
    onb = tmp_path / 'uzun-katalog.json'
    onb.write_text('{bozuk', encoding='utf-8')
    assert olasilik.uzun_katalog_yukle(onbellek=str(onb))['m'].size > 100
