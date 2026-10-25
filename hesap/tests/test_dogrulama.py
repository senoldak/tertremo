import math
from datetime import datetime, timezone

import numpy as np
import pytest

pytest.importorskip('etas')
pytest.importorskip('csep')

from hesap import dogrulama as dg, etas  # noqa: E402

UTC = timezone.utc
GUN_MS = 86_400_000


def test_karar_uc_kosul_birden():
    iyi_t = {'ig': 0.2, 'alt': 0.05, 'ust': 0.35}
    assert dg.karar(iyi_t, 0.1, 0.93) is True
    assert dg.karar(iyi_t, 0.1, 0.90) is True                            # eşik dahil
    assert dg.karar({**iyi_t, 'alt': -0.01}, 0.1, 0.93) is False         # aralık 0'ı kapsıyor
    assert dg.karar({**iyi_t, 'ig': -0.1, 'alt': -0.2}, 0.1, 0.93) is False
    assert dg.karar(iyi_t, 0.0, 0.93) is False                           # Brier beceri > 0 değil
    assert dg.karar(iyi_t, None, 0.93) is False
    assert dg.karar(iyi_t, 0.1, 0.89) is False                           # haftalık N-testi < %90
    assert dg.karar(iyi_t, 0.1, None) is False
    assert dg.karar({'ig': None}, 0.1, 0.93) is False


def test_t_testi_dogru_model_kazanir():
    # 100 hücre; gerçek hızlar yoğunlaşmış, Poisson düz; gözlem gerçek hızlardan
    r = np.random.default_rng(0)
    gercek = np.r_[np.full(10, 2.0), np.full(90, 0.02)]
    duz = np.full(100, gercek.sum() / 100)
    say = r.poisson(gercek)
    hucre = np.repeat(np.arange(100), say)
    t = dg.t_testi(gercek[hucre], duz[hucre], say.sum(), gercek.sum(), duz.sum())
    assert t['ig'] > 0 and t['alt'] > 0
    ters = dg.t_testi(duz[hucre], gercek[hucre], say.sum(), duz.sum(), gercek.sum())
    assert ters['ig'] < 0
    assert dg.t_testi([1.0], [1.0], 1, 1, 1)['ig'] is None


def test_n_testi_nicelikleri():
    sim = np.arange(100)  # 0..99
    n = dg.n_testi(sim, 50)
    assert n['d1'] == pytest.approx(0.5) and n['d2'] == pytest.approx(0.51)
    assert n['reddedildi'] is False
    assert dg.n_testi(sim, 150)['reddedildi'] is True   # gözlem dağılımın üstünde
    assert dg.n_testi(sim + 100, 50)['reddedildi'] is True


def test_brier_beceri():
    o = [1, 0, 0, 1]
    assert dg.brier([1, 0, 0, 1], o) == 0
    assert dg.brier_beceri([0.9, 0.1, 0.1, 0.9], [0.5] * 4, o) == pytest.approx(1 - 0.01 / 0.25)
    assert dg.brier_beceri([0.1, 0.9, 0.9, 0.1], [0.5] * 4, o) < 0


def test_hucre_ve_su_seviyesi():
    ne, nb = dg.izgara()
    assert (ne, nb) == (22, 47)
    assert dg.hucre([33.5, 44.5, 39.0, 20.0], [23.5, 47.0, 35.0, 35.0]).tolist() == [0, ne * nb - 1,
                                                                                  11 * nb + 23, -1]
    h = dg.su_seviyesi(np.r_[np.zeros(9), 10.0])
    assert h.sum() == pytest.approx(10.0) and h.min() > 0


def test_pencereler_ust_uste_binmez():
    bas = datetime(2022, 1, 1, tzinfo=UTC).timestamp() * 1000
    p = dg.pencereler(bas, bas + 22 * GUN_MS)
    assert len(p) == 3 and p[1] - p[0] == 7 * GUN_MS


def test_calistir_sahte_uyumla_ozet_ve_kapi():
    """Uçtan uca (sahte uyum: bilinen parametreler, arka plan tekdüze): sözlük şeması, gelecek veri kullanılmaz."""
    r = np.random.default_rng(4)
    bas = datetime(2018, 1, 1, tzinfo=UTC).timestamp() * 1000
    n = 4000
    t = np.sort(r.uniform(bas, bas + 4.3 * 365.25 * GUN_MS, n))
    m = np.round(2.0 + r.exponential(1 / math.log(10), n), 1)
    olaylar = [{'id': f'emsc:{i}', 'zaman_ms': float(t[i]), 'enlem': float(r.uniform(36, 42)),
                'boylam': float(r.uniform(26, 44)), 'mw': float(m[i])} for i in range(n)]
    gorulen = []

    def sahte_uyum(gecmis, bitis_ms, mc, b):
        gorulen.append((max(o['zaman_ms'] for o in gecmis), bitis_ms))
        from shapely.geometry import Polygon
        th = {'log10_mu': -7.0, 'log10_k0': -2.75, 'a': 1.8, 'log10_c': -2.5, 'omega': -0.02, 'log10_tau': 3.5,
              'log10_d': -0.85, 'gamma': 1.3, 'rho': 0.66}
        u = {'parametreler': th, 'beta': b * math.log(10), 'mc': mc, 'b': b, 'kutu': etas.KUTU, 'arka': [],
             'alan_km2': etas.paket().inversion.polygon_surface(Polygon(etas.kutu_koseleri())), 'zaman': bitis_ms}
        u.update(etas.olcutler(th, u['beta']))
        return u

    bit = datetime(2022, 3, 1, tzinfo=UTC).timestamp() * 1000
    s = dg.calistir(olaylar, bit, n=500, uyum_fn=sahte_uyum)
    assert s['kapsam']['pencere'] == 8
    assert all(son < bitis for son, bitis in gorulen)   # uyum yalnız geçmiş veriyi görür
    assert len(s['modeller']) == 1 and s['modeller'][0]['tarih'] == '2022-01-01'
    assert set(s) >= {'gecti', 't_testi', 'brier_beceri', 'n_testi', 'ek', 'haftalar', 'sure'}
    assert set(s['n_testi']) == {'haftalik_gecme', 'esik', 'toplam'} and s['n_testi']['esik'] == 0.9
    assert 0 <= s['n_testi']['haftalik_gecme'] <= 1 and 'reddedildi' in s['n_testi']['toplam']
    mc = s['modeller'][0]['mc']                       # eğitim (2018–2021) MBS Mc'si; saf G-R → ~2,0
    assert 2.0 <= mc <= 2.3 and s['kapsam']['mc'] == mc and s['kapsam']['hedef_m'] == max(4.0, mc)
    assert isinstance(s['gecti'], bool)
    assert len(s['haftalar']['p5']) == 8
    s['tarih'] = 0
    o = dg.ozet(s)
    assert 'hafta' in o and 'haftalık N-testi geçme %' in o and '(eşik %90)' in o
