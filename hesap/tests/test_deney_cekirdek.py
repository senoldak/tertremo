import math

import numpy as np

from hesap.deney import cekirdek as c


def test_wc_uzunluk_tablo_degerleri():
    # WC94 Tablo 2A, alt yüzey kırılma boyu: SS −2,57 + 0,62·M
    assert abs(c.wc_uzunluk(7.8, 0.0) - 10 ** (-2.57 + 0.62 * 7.8)) < 1e-9
    assert 180 < c.wc_uzunluk(7.8, -179.0) < 190          # rake ≈ ±180 → doğrultu atımlı
    assert abs(c.wc_uzunluk(6.0, 90.0) - 10 ** (-2.42 + 0.58 * 6.0)) < 1e-9   # ters
    assert abs(c.wc_uzunluk(6.0, -90.0) - 10 ** (-1.88 + 0.50 * 6.0)) < 1e-9  # normal


def test_kirilma_turu_sinirlari():
    assert c.kirilma_turu(10) == 'SS' and c.kirilma_turu(-170) == 'SS' and c.kirilma_turu(175) == 'SS'
    assert c.kirilma_turu(60) == 'R' and c.kirilma_turu(-60) == 'N'


def test_parca_uzaklik_geometri():
    # azimut 90° → doğu-batı parçası, 10 km, merkez orijin
    assert c.parca_uzaklik(0.0, 0.0, 0, 0, 90, 10) == 0.0
    assert abs(c.parca_uzaklik(3.0, 0.0, 0, 0, 90, 10)) < 1e-12            # parçanın içinde
    assert abs(c.parca_uzaklik(8.0, 0.0, 0, 0, 90, 10) - 3.0) < 1e-12       # uçtan 3 km
    assert abs(c.parca_uzaklik(2.0, 4.0, 0, 0, 90, 10) - 4.0) < 1e-12       # dik uzaklık
    assert abs(c.parca_uzaklik(8.0, 4.0, 0, 0, 90, 10) - 5.0) < 1e-12       # uç noktaya
    # uzunluk 0 → nokta uzaklığı; azimut 0° kuzey-güney
    assert abs(c.parca_uzaklik(3.0, 4.0, 0, 0, 33, 0) - 5.0) < 1e-12
    assert abs(c.parca_uzaklik(4.0, 3.0, 0, 0, 0, 20) - 4.0) < 1e-12


def test_pca_azimut_ve_duzlem_secimi():
    t = np.linspace(-20, 20, 50)
    az = math.radians(60)
    x, y = t * math.sin(az), t * math.cos(az)
    rng = np.random.default_rng(0)
    assert c.acisal_fark(c.pca_azimut(x + rng.normal(0, 0.3, 50), y + rng.normal(0, 0.3, 50)), 60) < 3
    assert c.acisal_fark(10, 170) == 20 and c.acisal_fark(0, 90) == 90
    sec, diger, fark = c.duzlem_sec([150.0, 240.0], 62.0)    # 240 ≡ 60 (mod 180)
    assert sec == 240.0 and diger == 150.0 and abs(fark - 2.0) < 1e-9


def _izotropik_bilesen(olay_r):
    gx, gy = c.izgara_xy()
    return c.Bilesen(np.hypot(gx, gy), np.asarray(olay_r, float))


def test_normalizasyon_analitik_ile_uyumlu():
    # ∫_disk (r²+d²)^−q dA = π/(q−1)·(d^{2(1−q)} − (R²+d²)^{1−q}); hücre alanı 1 km²
    q, d, R = 1.5, 3.0, c.R_ALAN
    b = _izotropik_bilesen([1.0])
    sayisal = float(np.sum(b.sayi * (b.r_bin ** 2 + d ** 2) ** (-q)))
    analitik = math.pi / (q - 1) * (d ** (2 * (1 - q)) - (R ** 2 + d ** 2) ** (1 - q))
    assert abs(sayisal / analitik - 1) < 0.01


def _ornekle(rng, n, q, d, yaricap=c.R_ALAN):
    """f ∝ (r²+d²)^−q, disk içinde: r için ters dağılım fonksiyonu; açı düzgün."""
    u = rng.uniform(size=n)
    a, b = d ** (2 * (1 - q)), (yaricap ** 2 + d ** 2) ** (1 - q)
    r = np.sqrt((a - u * (a - b)) ** (1 / (1 - q)) - d ** 2)
    th = rng.uniform(0, 2 * math.pi, n)
    return r * np.cos(th), r * np.sin(th)


def test_uydur_parametreleri_geri_bulur():
    rng = np.random.default_rng(1)
    diziler = []
    for _ in range(3):
        x, y = _ornekle(rng, 3000, 1.5, 5.0)
        diziler.append({'degisken': {'I': [_izotropik_bilesen(np.hypot(x, y))]}})
    q, d, _ = c.uydur(diziler, 'I', False)
    assert abs(q - 1.5) < 0.1 and abs(d / 5.0 - 1) < 0.15


def test_uzun_cekirdek_dogru_azimutta_kazanir():
    rng = np.random.default_rng(2)
    az, L = 60.0, 60.0
    n = 1500
    t = rng.uniform(-L / 2, L / 2, n)
    a = math.radians(az)
    x = t * math.sin(a) + rng.normal(0, 2.0, n) * math.cos(a)
    y = t * math.cos(a) - rng.normal(0, 2.0, n) * math.sin(a)
    gx, gy = c.izgara_xy()

    def bil(azimut):
        return [c.Bilesen(c.parca_uzaklik(gx, gy, 0, 0, azimut, L), c.parca_uzaklik(x, y, 0, 0, azimut, L), 1.0, L)]
    ll = lambda b: float(np.mean(c.log_yogunluk(b, 1.5, 3.0)))
    iso = [c.Bilesen(np.hypot(gx, gy), np.hypot(x, y))]
    assert ll(bil(60.0)) > ll(iso) > ll(bil(150.0))


def test_log_yogunluk_karisim_agirlik_toplami_bir():
    gx, gy = c.izgara_xy()
    r = np.hypot(gx, gy)
    b1 = c.Bilesen(r, np.array([2.0, 5.0]), 2.0)
    b2 = c.Bilesen(r, np.array([2.0, 5.0]), 1.0)
    # aynı r'ye sahip iki bileşenin karışımı tek bileşenle aynı olmalı (ağırlıklar normalize edilir)
    tek = c.log_yogunluk([b1], 1.2, 4.0)
    assert np.allclose(c.log_yogunluk([b1, b2], 1.2, 4.0), tek)


def _olay(i, gun, e, b, mw):
    return {'id': f'x:{i}', 'zaman_ms': gun * c.GUN_MS, 'enlem': e, 'boylam': b, 'derinlik': 10.0, 'buyukluk': mw,
            'tur': 'Mw', 'mw': mw, 'yer': 'T'}


def test_ana_sok_adaylari_bagimli_olaylari_atar():
    ol = [_olay(0, 100, 38.0, 30.0, 7.0), _olay(1, 110, 38.2, 30.1, 6.0),     # artçı büyüklüğünde ikinci: bağımlı
          _olay(2, 400, 38.0, 30.0, 6.2),                                     # 300 gün sonra: bağımsız
          _olay(3, 500, 34.0, 30.0, 6.5),                                     # kutu dışı (güney)
          _olay(4, 600, 38.0, 45.0, 6.5)]                                     # kutu dışı (doğu)
    assert c.ana_sok_adaylari(ol) == [0, 2]


def test_olay_kumesi_pencere_ve_yaricap():
    ol = [_olay(0, 0, 38.0, 30.0, 7.0),
          _olay(1, 0.1, 38.0, 30.0, 4.0),            # 2,4 saat: ilk 6 saat
          _olay(2, 1, 38.1, 30.0, 4.0),              # 1 gün, ~11 km
          _olay(3, 2, 38.0, 30.0, 2.0),              # Mc altı
          _olay(4, 3, 41.0, 30.0, 4.0),              # ~333 km: dışarıda
          _olay(5, 40, 38.0, 30.0, 4.0)]             # 30 günden sonra
    x, y, idx = c.olay_kumesi(ol, 0, 3.0, c.ILK_SAAT * c.SAAT_MS, 30 * c.GUN_MS)
    assert list(idx) == [2]
    _, _, idx6 = c.olay_kumesi(ol, 0, 3.0, 0.0, c.ILK_SAAT * c.SAAT_MS)
    assert list(idx6) == [1]


def test_mt_sec_mww_once():
    urunler = [{'source': 'us', 'code': 'us_1_mwc', 'properties': {'nodal-plane-1-strike': '1'}},
               {'source': 'us', 'code': 'us_1_mww', 'properties': {'nodal-plane-1-strike': '2'}},
               {'source': 'gcmt', 'code': 'gcmt_1', 'properties': {'nodal-plane-1-strike': '3'}}]
    assert c._mt_sec(urunler)['properties']['nodal-plane-1-strike'] == '2'
    assert c._mt_sec([]) is None


def test_isaret_testi_ve_bootstrap_ci_sade():
    rng = np.random.default_rng(3)
    assert c.isaret_testi([1, 2, 3, 4, 5, 6, 7, 8]) < 0.01
    ci_dizi, ci_birlesik, ci_agirlikli = c.bootstrap_ci([np.full(40, 0.5), np.full(20, -0.1)], rng, b=200)
    assert ci_dizi[0] == [0.5, 0.5] and abs(ci_birlesik[0] - 0.2) < 1e-9
