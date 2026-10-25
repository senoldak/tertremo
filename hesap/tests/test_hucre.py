import numpy as np
import pytest

from hesap.hucre import b_aki_utsu, bh_duzelt, hucre_istatistik, mc_maxc

YIL_MS = 365.25 * 24 * 3600 * 1000


def gr_ornek(n, b, mc, dm=0.1, tohum=1):
    """Gutenberg–Richter, Mc'den tam, dm ile kutulanmış (kutu merkezi Mc)."""
    r = np.random.default_rng(tohum)
    m = (mc - dm / 2) + r.exponential(1 / (b * np.log(10)), n)
    return np.round(np.round(m / dm) * dm, 1)


def test_aki_utsu_b1():
    m = gr_ornek(10_000, 1.0, 2.0)
    b, sigma = b_aki_utsu(m, 2.0)
    assert b == pytest.approx(1.0, abs=0.03)
    assert 0 < sigma < 0.05


def test_mc_maxc():
    m = gr_ornek(10_000, 1.0, 2.0)
    assert 2.0 - 1e-9 <= mc_maxc(m) <= 2.2 + 1e-9


def test_mc_maxc_eksik_alt_kisim():
    # Mc altında eksik kayıt: tepe 2,0'da → Mc 2,2
    m = gr_ornek(10_000, 1.0, 2.0)
    r = np.random.default_rng(3)
    eksik = np.round(r.uniform(1.0, 1.95, 1500), 1)
    assert mc_maxc(np.concatenate([m, eksik])) == pytest.approx(2.2)


def test_bh_duzelt_scipy_ile_ayni():
    from scipy.stats import false_discovery_control
    p = np.array([0.01, 0.04, 0.03, 0.2, 0.001, 0.5])
    assert np.allclose(bh_duzelt(p), false_discovery_control(p, method='bh'))
    assert bh_duzelt(np.array([])).size == 0


def _katalog(n_hucre=3, tohum=5):
    r = np.random.default_rng(tohum)
    simdi = 1_700_000_000_000.0
    bas = simdi - 6 * YIL_MS
    parcalar = []
    for i in range(n_hucre):
        k = 400 if i == 0 else 20
        enlem = 38.2 + i + r.uniform(0, 0.6, k)
        boylam = 27.3 + r.uniform(0, 0.6, k)
        zaman = np.sort(r.uniform(bas, simdi - 10 * 86_400_000, k))
        m = gr_ornek(k, 1.0, 2.0, tohum=10 + i)
        parcalar.append((zaman, enlem, boylam, m))
    # 0. hücrede son 7 günde 30 bağımsız olay (olağan dışı)
    z7 = np.sort(r.uniform(simdi - 6 * 86_400_000, simdi, 30))
    parcalar.append((z7, np.full(30, 38.5), np.full(30, 27.5), np.full(30, 3.0)))
    zaman, enlem, boylam, m = (np.concatenate(x) for x in zip(*parcalar))
    return zaman, enlem, boylam, m, bas, simdi


def test_hucre_istatistik():
    zaman, enlem, boylam, m, bas, simdi = _katalog()
    bagimsiz = np.ones(zaman.size, bool)
    sat = {s['anahtar']: s for s in hucre_istatistik(zaman, enlem, boylam, m, bagimsiz, 'tr', bas, simdi)}
    assert set(sat) == {'38_27', '39_27', '40_27'}
    s0 = sat['38_27']
    assert s0['katalog'] == 'tr'
    assert s0['n'] >= 50 and s0['b'] == pytest.approx(1.0, abs=0.25) and s0['sigma_b'] > 0
    assert sat['39_27']['b'] is None and sat['39_27']['sigma_b'] is None
    # λ: bağımsız M≥mc / yıl
    yil = (simdi - bas) / YIL_MS
    secili = (np.floor(enlem) == 38) & (m >= s0['mc'] - 1e-9)
    assert s0['lambda'] == pytest.approx(secili.sum() / yil)
    # olağan dışı hücre BH sonrası anlamlı, ötekiler değil
    assert s0['k7'] >= 30 and s0['bh_p'] < 0.05
    assert sat['40_27']['bh_p'] > 0.05


def test_hucre_istatistik_bagimlilar_lambda_disi():
    zaman, enlem, boylam, m, bas, simdi = _katalog()
    hepsi = np.ones(zaman.size, bool)
    yari = hepsi.copy()
    yari[::2] = False
    a = {s['anahtar']: s for s in hucre_istatistik(zaman, enlem, boylam, m, hepsi, 'tr', bas, simdi)}
    c = {s['anahtar']: s for s in hucre_istatistik(zaman, enlem, boylam, m, yari, 'tr', bas, simdi)}
    assert c['38_27']['lambda'] < a['38_27']['lambda']
    assert c['38_27']['mc'] == a['38_27']['mc']  # Mc ve b bütün olaylarla


def test_dunya_5_derece():
    zaman, enlem, boylam, m, bas, simdi = _katalog()
    sat = hucre_istatistik(zaman, enlem - 50, boylam, m, np.ones(zaman.size, bool), 'dunya', bas, simdi)
    assert {s['anahtar'] for s in sat} == {'-15_25', '-10_25'}


def test_lambda_ve_k7_ham_mw_ile():
    # Worker olagandisi ham mw ≥ mc ile sayar: Mc − 0,03 (kutulanınca Mc) olay λ ve k7'ye girmez; Mc, b, n kutulu
    simdi = 1_700_000_000_000.0
    bas = simdi - 2 * YIL_MS
    m = np.concatenate([np.full(100, 2.0), np.full(60, 2.2), [2.17, 2.2]])
    zaman = np.concatenate([np.linspace(bas, simdi - 30 * 86_400_000, 160), [simdi - 86_400_000] * 2])
    n = m.size
    s = hucre_istatistik(zaman, np.full(n, 38.5), np.full(n, 27.5), m, np.ones(n, bool), 'tr', bas, simdi)[0]
    assert s['mc'] == pytest.approx(2.2)
    assert s['n'] == 62  # kutulu: 2,17 → 2,2 sayılır
    assert s['lambda'] == pytest.approx(61 / 2)
    assert s['k7'] == 1
