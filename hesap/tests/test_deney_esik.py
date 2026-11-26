import numpy as np
import pytest

pytest.importorskip('etas')
pytest.importorskip('csep')

from hesap import etas  # noqa: E402
from hesap.deney import esik  # noqa: E402


def test_uyum_esikli_mc_den_kucuk_esigi_kullanir(monkeypatch):
    cagrilar = []
    monkeypatch.setattr(etas, 'uyum', lambda ol, t, mc, b, **k: cagrilar.append(mc) or {'mc': mc})
    assert esik.uyum_esikli(3.0)([], 0, 4.0, 1.0) == {'mc': 3.0}
    assert esik.uyum_esikli(3.0)([], 0, 2.5, 1.0) == {'mc': 2.5}   # Mc zaten düşükse yükseltilmez
    assert cagrilar == [3.0, 2.5]


def test_esli_brier_daha_iyi_model_pozitif_beceri():
    r = np.random.default_rng(1)
    o = r.random(300) < 0.2
    iyi = np.where(o, 0.6, 0.1)           # gözlemi bilen model
    kotu = np.full(300, 0.2)
    s = esik.esli_brier(kotu, iyi, o)
    assert s['beceri'] > 0 and s['alt'] > 0
    ters = esik.esli_brier(iyi, kotu, o)
    assert ters['beceri'] < 0 and ters['ust'] < 0


def test_esli_brier_sifir_taban():
    assert esik.esli_brier([0, 0], [0.1, 0.1], [0, 0])['beceri'] is None


def test_json_hazirla():
    s = esik._json_hazirla({1: np.float64(2.5), 'a': [np.int64(3), np.bool_(True)]})
    assert s == {'1': 2.5, 'a': [3, True]}
