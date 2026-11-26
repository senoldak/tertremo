import math

import numpy as np
import pytest

pytest.importorskip('etas')
pytest.importorskip('csep')

from hesap import dogrulama as dg  # noqa: E402
from hesap.deney import uzun_vade as uv  # noqa: E402


def _olaylar(n=60, tohum=0):
    r = np.random.default_rng(tohum)
    e = np.r_[r.normal(39.5, 0.3, n // 2), r.normal(37.0, 0.3, n - n // 2)]
    bo = np.r_[r.normal(30.0, 0.3, n // 2), r.normal(40.0, 0.3, n - n // 2)]
    return e, bo


def test_cekirdek_agirliklari_toplam_bir_ve_olay_yakininda_yogun():
    e, bo = _olaylar()
    ck = uv.Cekirdekler(e, bo)
    for w in (ck.sabit(20), ck.uyarlanir(3, 10, 'guc'), ck.uyarlanir(3, 10, 'gauss')):
        assert w.shape == (dg.izgara()[0] * dg.izgara()[1],)
        assert w.sum() == pytest.approx(1.0)
        assert (w >= 0).all()
        # yoğunluk olay kümesinin hücresinde, ıssız hücreden çok yüksek
        assert w[dg.hucre(39.5, 30.0)] > 50 * w[dg.hucre(34.0, 46.0)]


def test_uyarlanir_bant_k_ve_dmin():
    e, bo = _olaylar()
    ck = uv.Cekirdekler(e, bo)
    b3, b10 = ck.bant(3, 1), ck.bant(10, 1)
    assert (b10 >= b3).all()
    assert (ck.bant(3, 500) == 500).all()          # en küçük bant tabanı
    assert ck.komsu.shape == (60, 59)


def test_olay_ll_duzgun_modelin_alt_siniri():
    h = np.array([3, 3, 7])
    n = 10
    assert uv.olay_ll(np.full(n, 1 / n), h) == pytest.approx(math.log(dg.su_seviyesi(np.full(n, 1 / n))[0]))
    w = np.zeros(n)
    w[3] = 1.0
    assert uv.olay_ll(w, np.array([3])) > uv.olay_ll(np.full(n, 1 / n), np.array([3]))


def test_nb_alfa_asiri_yayilim_ve_poisson():
    r = np.random.default_rng(1)
    mu, alfa = 10.0, 0.3
    rr = 1 / alfa
    nb = r.negative_binomial(rr, rr / (rr + mu), 4000)
    assert uv.nb_alfa(nb) == pytest.approx(alfa, rel=0.25)
    assert uv.nb_alfa(r.poisson(10, 4000)) < 0.03
    assert uv.nb_alfa([10, 10, 10, 10, 10, 10]) == 0.0     # eksik yayılım → Poisson


def test_nb_dagilim_toplam_ortalama_ve_varyans():
    d = uv.nb_dagilim(10.0, 0.2, 5.0)
    assert d.mean() == pytest.approx(50.0)
    assert d.var() == pytest.approx(5 * (10 + 0.2 * 100))
    assert uv.nb_dagilim(10.0, 0.0, 2.0).var() == pytest.approx(20.0)


def test_n_kuantil_iki_yonlu():
    d = uv.nb_dagilim(10.0, 0.0)
    assert uv.n_kuantil(d, 10)['reddedildi'] is False
    assert uv.n_kuantil(d, 25)['reddedildi'] is True
    assert uv.poisson_n(10.0, 25)['reddedildi'] is True


def test_blok_bootstrap_aralik_ortalamayi_kapsar():
    r = np.random.default_rng(2)
    fark = r.normal(0.2, 0.5, 300)
    yil = np.repeat(np.arange(10), 30)
    b = uv.blok_bootstrap(fark, yil)
    assert b['alt'] < fark.mean() < b['ust']
    assert b['blok'] == 10


def test_tapered_survivor_kesilmemis_gr_ile_uyumlu():
    # τ = 0: log S = −β ln x; Mw 1 birim = x'te 10^1,5
    assert float(uv.log_surv(6.95, 0.67, 0.0)) == pytest.approx(-0.67 * 1.5 * math.log(10))
    assert float(uv.log_surv(6.95, 0.67, 0.05)) < float(uv.log_surv(6.95, 0.67, 0.0))
    assert uv.tau_of(None) == 0.0


def _gr_orneklem(n, beta, tohum=0):
    """Mw ≥ 5,95 kenarından kesilmemiş GR (kutulu 0,1)."""
    r = np.random.default_rng(tohum)
    x = (1 - r.random(n)) ** (-1 / beta)                # Pareto, x = M/Mt
    mw = uv.MT + np.log10(x) / 1.5
    return uv.kutula(mw[mw < 9.0])


def test_beta_en_cok_olabilirlik_gr_orneklemini_bulur():
    mag = _gr_orneklem(3000, 0.7)
    pen = np.zeros(mag.size, int)
    w = np.ones(mag.size)
    pencereler = [(60.0, uv.MT)]                        # örneklem tek pencerede (kenar 5,95)
    bt, ll = uv.beta_uydur(0.0, mag, pen, w, pencereler)
    assert bt == pytest.approx(0.7, abs=0.06)
    assert math.isfinite(ll)
    # tapered ≥ kesilmemiş (iç içe model): ızgara üst ucu ≈ kesilmemiş, olabilirlik aşağı inmez
    a = uv.uydur_tum(mag, pen, w, pencereler, izgara=np.array([7.0, 9.0, 12.0]))
    assert a['tapered']['ll'] >= a['gr']['ll'] - 1e-3
    # kesilmemiş örneklemde tapered'ın köşesi üst uca yakın kalır, AIC kesilmemişi tercih eder
    assert a['tapered']['mc_mag'] >= 9.0
    assert 2 * a['gr']['k'] - 2 * a['gr']['ll'] <= 2 * a['tapered']['k'] - 2 * a['tapered']['ll'] + 0.5


def test_olasilik10_artan_beta_azaltir_ve_aralik_profil():
    w = np.ones(10)
    pencereler = [(60.0, uv.MT), (40.0, uv.KENAR7)]
    assert uv.olasilik10(0.5, 0.0, w, pencereler) > uv.olasilik10(0.9, 0.0, w, pencereler)
    prof = {7.0: -10.0, 8.0: -5.0, 9.0: -5.5, 12.0: -5.6}
    alt, ust, acik = uv.aralik_profil(prof, 3.84)        # ll ≥ −5 − 1,92
    assert (alt, ust, acik) == (8.0, 12.0, True)


def test_maske_nn_sentetik_kume_ayirir():
    from hesap import etas
    r = np.random.default_rng(3)
    gun = 86_400_000
    t0 = 1.5e12
    # 80 bağımsız ana şok (uzak, dağınık) + büyük ana şokun 40 yakın artçısı
    z = list(t0 + np.sort(r.random(80)) * 3000 * gun)
    e = list(r.uniform(34, 44, 80))
    bo = list(r.uniform(24, 46, 80))
    m = list(4.5 + r.exponential(0.4, 80))
    z0 = t0 + 100 * gun
    z += list(z0 + r.random(40) * 5 * gun + gun)
    e += list(39 + r.normal(0, 0.05, 40))
    bo += list(35 + r.normal(0, 0.05, 40))
    m += [4.5] * 40
    z.append(z0); e.append(39.0); bo.append(35.0); m.append(7.0)
    v = {k: np.array(x) for k, x in (('z', z), ('e', e), ('bo', bo), ('m', m))}
    bag, bilgi = uv.maske_nn(v, t0 + 2000 * gun)
    assert bag.shape == v['z'].shape
    assert bag[-1]                                        # ana şok bağımsız
    assert bag[80:120].mean() < 0.5                       # artçılar çoğunlukla ayrılır
    assert bilgi['yontem'] == 'en-yakin-komsu'
    gk, _ = uv.maske_gk(v, t0 + 2000 * gun)
    assert gk[-1] and gk[80:120].mean() < 0.2
    assert etas.KUTU['minlat'] <= 39.0
