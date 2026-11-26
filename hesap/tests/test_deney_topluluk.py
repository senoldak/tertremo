import numpy as np

from hesap.deney import topluluk as tp


def _seri(T=120, tohum=0):
    rng = np.random.default_rng(tohum)
    gercek = rng.uniform(0.05, 0.6, T)
    o = (rng.random(T) < gercek).astype(int)
    iyi = np.clip(gercek + rng.normal(0, 0.03, T), 0.01, 0.99)
    kotu = np.full(T, 0.3)
    return np.column_stack([iyi, kotu, kotu]), o


def test_esit_ortalama():
    P, o = _seri()
    assert np.allclose(tp.esit(P, o), P.mean(axis=1))


def test_ll_agirlik_yalniz_gecmis():
    """Hafta t'nin ağırlığı gelecekteki gözleme bağlı olmamalı: sonraki gözlemi değiştirmek t'yi değiştirmez."""
    P, o = _seri()
    a = tp.ll_agirlik(P, o, 12)
    o2 = o.copy()
    o2[60:] = 1 - o2[60:]
    b = tp.ll_agirlik(P, o2, 12)
    assert np.allclose(a[:61], b[:61])
    assert np.all((a >= 0) & (a <= 1))


def test_lojistik_yalniz_gecmis_ve_aralik():
    P, o = _seri()
    a = tp.lojistik(P, o)
    o2 = o.copy()
    o2[80:] = 1 - o2[80:]
    b = tp.lojistik(P, o2)
    assert np.allclose(a[:81], b[:81])
    assert np.all((a > 0) & (a < 1))


def test_ll_agirlik_iyi_modele_kayar():
    P, o = _seri(T=300, tohum=3)
    p = tp.ll_agirlik(P, o, 26)
    assert tp.brier(p[100:], o[100:]) <= tp.brier(P[100:, 1], o[100:])


def test_en_iyi_tek_gecmisten_secer():
    P, o = _seri(T=200, tohum=4)
    p = tp.en_iyi_tek(P, o)
    assert np.allclose(p[150], P[150, 0])  # iyi model (sütun 0) seçilir


def test_degerlendir_bss_ve_aralik():
    P, o = _seri(T=200, tohum=5)
    s = tp.degerlendir({'taban': P[:, 1], 'etas': P[:, 0]}, o)
    assert s['taban']['bss'] == 0
    assert s['etas']['bss'] > 0
    lo, hi = s['etas']['bss_95']
    assert lo <= s['etas']['bss'] <= hi


def test_kmaras_maske():
    bas = 1640995200000  # 2022-01-01
    seri = {'hafta_bas_ms': [bas + i * 7 * 86400000 for i in range(80)]}
    m = tp.kmaras_maske(seri)
    assert m.sum() == 5
    # 2023-02-06 haftası: 2022-01-01'den 401 gün sonra → hafta 57
    assert m[57] and not m[56]


def test_guvenirlik_sayilari():
    g = tp.guvenirlik([0.02, 0.5, 0.52], [0, 1, 0])
    assert sum(x['n'] for x in g) == 3
