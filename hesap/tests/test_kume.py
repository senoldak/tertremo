import math

import numpy as np
import pytest

from hesap.kume import en_yakin_komsu, esik, korelasyon_boyutu, log_eta_cift

GUN_MS = 86_400_000.0
YIL_MS = 365.25 * GUN_MS
KM = 1 / 111.195


def test_esik_iki_tepe():
    r = np.random.default_rng(0)
    x = np.concatenate([r.normal(-7, 1, 5000), r.normal(-3, 1, 5000)])
    assert esik(x) == pytest.approx(-5, abs=0.3)


def test_esik_sonsuzlari_atar():
    r = np.random.default_rng(1)
    x = np.concatenate([r.normal(-7, 1, 3000), r.normal(-3, 1, 3000), [np.inf] * 50])
    assert esik(x) == pytest.approx(-5, abs=0.3)


def test_log_eta_js_ile_ayni():
    # test/kume.test.js: 1 saat sonra 5 km, ana Mw 6, d_f 1,6, b 1
    t0 = 1_780_272_000_000.0
    beklenen = math.log10(3600_000 / YIL_MS) + 1.6 * math.log10(5) - 6
    v = log_eta_cift(t0, 38, 38, 6, t0 + 3600_000, 38 + 5 * KM, 38, 1.6, 1)
    assert v == pytest.approx(beklenen, abs=1e-3)
    # r alt sınırı 0,1 km; τ ≤ 0 → inf
    v = log_eta_cift(t0, 38, 38, 6, t0 + GUN_MS, 38, 38, 1.6, 1)
    assert v == pytest.approx(math.log10(1 / 365.25) + 1.6 * math.log10(0.1) - 6, abs=1e-9)
    assert log_eta_cift(t0, 38, 38, 6, t0, 38, 38, 1.6, 1) == math.inf


def _sentetik(tohum=7):
    """Poisson arka plan (2 yıl, 5°×5°) + 3 Omori dizisi."""
    r = np.random.default_rng(tohum)
    t0 = 1_600_000_000_000.0
    sure = 2 * YIL_MS
    n_ap = 1500
    zaman = list(r.uniform(t0, t0 + sure, n_ap))
    enlem = list(r.uniform(36, 41, n_ap))
    boylam = list(r.uniform(28, 33, n_ap))
    mw = list(2.0 + r.exponential(1 / np.log(10), n_ap))
    dizi = [False] * n_ap
    for (ta, ea, ba, ma) in [(0.3, 37.2, 29.1, 6.2), (0.9, 39.6, 31.4, 5.8), (1.5, 38.4, 30.2, 6.5)]:
        ta = t0 + ta * YIL_MS
        zaman.append(ta); enlem.append(ea); boylam.append(ba); mw.append(ma); dizi.append(False)
        n = 300
        # Omori p≈1,1, c 0,01 gün: ters dönüşümle gecikmeler (≤ 60 gün)
        u = r.uniform(0, 1, n)
        c, p, T = 0.01, 1.1, 60.0
        A = (c ** (1 - p) - (T + c) ** (1 - p))
        gecikme = (c ** (1 - p) - u * A) ** (1 / (1 - p)) - c
        uzak = r.exponential(5.0, n)  # km
        aci = r.uniform(0, 2 * np.pi, n)
        zaman += list(ta + gecikme * GUN_MS + 1)
        enlem += list(ea + uzak * np.cos(aci) * KM)
        boylam += list(ba + uzak * np.sin(aci) * KM / np.cos(np.radians(ea)))
        mw += list(2.0 + r.exponential(1 / np.log(10), n))
        dizi += [True] * n
    s = np.argsort(zaman, kind='stable')
    return tuple(np.asarray(v)[s] for v in (zaman, enlem, boylam, mw, dizi))


def test_en_yakin_komsu_omori_dizileri():
    zaman, enlem, boylam, mw, dizi = _sentetik()
    ebeveyn, log_eta = en_yakin_komsu(zaman, enlem, boylam, mw, 1.6, 1.0)
    assert ebeveyn.shape == zaman.shape and log_eta.shape == zaman.shape
    assert ebeveyn[0] == -1 and math.isinf(log_eta[0])
    e = esik(log_eta)
    assert (log_eta[dizi] < e).mean() >= 0.9
    assert (log_eta[~dizi] < e).mean() < 0.3
    # ebeveyn her zaman daha önce
    var = ebeveyn >= 0
    assert np.all(zaman[ebeveyn[var]] < zaman[var])


def test_en_yakin_komsu_kaba_kuvvetle_ayni():
    # Küçük örnekte bütün adaylar Worker kurallarına uyar (3×3 hücre bloğu + büyük olaylar); kaba kuvvetle aynı sonuç
    r = np.random.default_rng(11)
    n = 300
    zaman = np.sort(r.uniform(0, 300 * GUN_MS, n)) + 1_600_000_000_000.0
    enlem = r.uniform(38, 39.5, n)
    boylam = r.uniform(30, 31.5, n)
    mw = 2.0 + r.exponential(0.43, n)
    eb, le = en_yakin_komsu(zaman, enlem, boylam, mw, 1.6, 1.0)
    for j in range(1, n):
        v = [log_eta_cift(zaman[i], enlem[i], boylam[i], mw[i], zaman[j], enlem[j], boylam[j], 1.6, 1.0)
             for i in range(j)]
        i = int(np.argmin(v))
        assert le[j] == pytest.approx(v[i], abs=1e-9)


def test_pencere_10_yil():
    t0 = 1_600_000_000_000.0
    # 1 yıldan sonraki olay hâlâ ebeveyn bulur (2023 Kahramanmaraş kuyruğu); 3652 günden sonrası bulamaz
    zaman = np.array([t0, t0 + 400 * GUN_MS])
    eb, le = en_yakin_komsu(zaman, np.array([38.0, 38.0]), np.array([30.0, 30.0]), np.array([5.0, 3.0]), 1.6, 1.0)
    assert list(eb) == [-1, 0]
    zaman = np.array([t0, t0 + 3653 * GUN_MS])
    eb, le = en_yakin_komsu(zaman, np.array([38.0, 38.0]), np.array([30.0, 30.0]), np.array([5.0, 3.0]), 1.6, 1.0)
    assert list(eb) == [-1, -1]


def test_korelasyon_boyutu():
    r = np.random.default_rng(2)
    # düzlemde düzgün → ≈ 2; doğru üzerinde → ≈ 1
    d2 = korelasyon_boyutu(r.uniform(36, 41, 4000), r.uniform(28, 34, 4000))
    t = r.uniform(0, 1, 4000)
    d1 = korelasyon_boyutu(36 + 5 * t, 28 + 6 * t)
    assert d2 == pytest.approx(2.0, abs=0.15)
    assert d1 == pytest.approx(1.0, abs=0.15)


def test_esik_az_veri_nan_dondurur():
    assert math.isnan(esik(np.array([-5.0, -4.0, np.inf] + [-3.0] * 10)))
    assert math.isnan(esik(np.array([])))
