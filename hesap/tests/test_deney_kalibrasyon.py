# hesap/deney/kalibrasyon.py testleri: artci.js eşdeğerliği (sayılar node ile JS'ten üretildi), dizi kurma, ölçütler.
# JS değerleri: vesaire/tertremo'da import('./src/artci.js') ile aynı girdilerle üretildi (dosya değiştirilmedi).
import math

import numpy as np
import pytest

from hesap.deney import kalibrasyon as k

OLAYLAR = [(0, 6.1), (0.005, 4.2), (0.02, 5.0), (0.05, 4.1), (0.1, 3.9), (0.3, 4.4), (0.7, 3.6), (1.2, 3.2), (1.4, 4.0), (2.5, 3.0)]
GOREL = 1e-9


def test_mc_zaman_js_esdeger():
    assert k.mc_zaman(7.8, 0.5, 2.0) == pytest.approx(3.951029995663981, rel=GOREL)
    assert k.mc_zaman(6.1, 1 / 24, 3.0) == pytest.approx(4.180211241711606, rel=GOREL)
    assert k.mc_zaman(4.0, 10, 2.0) == 2.0
    assert k.mc_zaman(5.2, 23, 2.4) == 2.4
    assert k.mc_zaman(5, 0, 2) == math.inf


def test_beklenen_js_esdeger():
    assert float(k.beklenen(-2.42, 0.98, 0.018, 1.0, 6.1, 4, 1.5, 8.5)) == pytest.approx(0.846980324595626, rel=GOREL)
    assert float(k.beklenen(-2.0, 1.0, 0.018, 1.0, 5, 5, 0.01, 7.01)) == pytest.approx(0.055254529391317836, rel=GOREL)


def test_izgara_js_esdeger():
    iz = k.izgara(k.PARAM['tr'])
    assert len(iz['a']) == 201
    assert iz['a'][0] == pytest.approx(-4.9399999999999995, rel=GOREL)
    assert iz['a'][200] == pytest.approx(0.10000000000000009, rel=GOREL)
    assert iz['w'][0] == pytest.approx(5.353520241313118e-06, rel=GOREL)
    assert iz['w'][50] == pytest.approx(0.0021597642118918875, rel=GOREL)
    assert iz['w'][100] == pytest.approx(0.0159586189221319, rel=GOREL)
    assert iz['w'].sum() == pytest.approx(1.0)


# (Mana, t, mc, sonsal a ort., w[100], P4 orta/alt/ust, P5 orta/alt/ust, P>=Mana orta, önsel P4 orta)
JS_GUNCELLE = [
    (6.1, 1.5, 2.5, -2.6821002717312608, 0.019030565097300584, (0.38235412733196494, 0.24515100794033667, 0.5296024384283319),
     (0.04853879093706894, 0.0277319646722337, 0.07264395733770786), 0.003957851303926151, 0.5687050123383571),
    (7.8, 0.2, 3.0, -3.41647139254771, 7.910468810103471e-05, (0.9754569350189812, 0.9360610685573718, 0.9999999999398704),
     (0.5849379811062766, 0.24041472446981, 0.9049594859755139), 0.001849913510369524, 0.9977635645100983),
    (4.3, 1 / 24, 2.0, -1.6738413720803043, 0.006992650742970588, (0.2653579163571874, 0.037342058205851965, 0.6250361075086538),
     (0.038399338366481114, 0.00379848054302661, 0.09343500673875677), 0.15919304613211063, 0.08075274257609813),
    (5.4, 7, 2.5, -2.4931319707953286, 0.06343283799059182, (0.05993259335086166, 0.03587922346017358, 0.08831417990432343),
     (0.006181317143651356, 0.003647203273194871, 0.009203371696552807), 0.0024659567847162356, 0.13574784182077937),
]


@pytest.mark.parametrize('mana,t,mc,a_ort,w100,p4,p5,pm,onsel4', JS_GUNCELLE)
def test_guncelle_olasilik_js_esdeger(mana, t, mc, a_ort, w100, p4, p5, pm, onsel4):
    p = k.PARAM['tr']
    iz = k.izgara(p)
    ol = [(0, mana)] + [o for o in OLAYLAR[1:] if o[0] <= t]
    g = k.guncelle(iz, ol, p, mana, t, mc)
    assert float((g['a'] * g['w']).sum()) == pytest.approx(a_ort, rel=GOREL)
    assert g['w'][100] == pytest.approx(w100, rel=1e-8)
    for hedef, beklenen_ in ((4, p4), (5, p5)):
        r = k.olasilik(g, p, mana, hedef, t, t + 7)
        assert (r['orta'], r['alt'], r['ust']) == pytest.approx(beklenen_, rel=1e-8)
    assert k.olasilik(g, p, mana, mana, t, t + 7)['orta'] == pytest.approx(pm, rel=1e-8)
    assert k.olasilik(iz, p, mana, 4, t, t + 7)['orta'] == pytest.approx(onsel4, rel=1e-8)


def test_dizi_b_js_esdeger():
    mws = [2.5 + ((i * 37) % 100) / 50 for i in range(120)]
    assert k.dizi_b(mws, 2.5, 3) == pytest.approx(0.42164512806140964, rel=GOREL)
    assert k.dizi_b(mws[:40], 2.5, 3) == 1.0      # N < 50
    assert k.dizi_b(mws, 2.5, 0.5) == 1.0         # t < 1 gün


def test_diziler_kur_kurallari():
    # 0: Mw 4,5 ana şok (dizisiz, eşik üstü) -> dizi 0; 1: bağlı Mw 3 -> dizi 0; 2: bağlı Mw 5,0 -> dizinin ana şokundan büyük, yeni dizi 2;
    # 3: ebeveyni 1 (dizi 0), Mw 3 -> dizi 0 (eski dizi sürer); 4: ebeveyni 2, Mw 3 -> dizi 2; 5: bağımsız Mw 3,9 -> dizisiz;
    # 6: bağımsız Mw 4,0 -> yeni dizi
    z = np.arange(7) * 1e6 + 1e9
    mw = np.array([4.5, 3.0, 5.0, 3.0, 3.0, 3.9, 4.0])
    eb = np.array([-1, 0, 0, 1, 2, -1, -1])
    bagli = np.array([False, True, True, True, True, False, False])
    dizi_id, diziler, soy = k.diziler_kur(z, mw, eb, bagli)
    assert dizi_id.tolist() == [0, 0, 2, 0, 2, -1, 6]
    assert set(diziler) == {0, 2, 6}
    assert diziler[0]['ust'] == z[2] and diziler[2]['ust'] == math.inf
    assert soy[2] == (0, 2) and soy[4] == (0, 2) and soy[3] == (0,) and soy[5] == ()
    tur = k.soy_olaylari(soy, diziler)
    assert tur[0].tolist() == [1, 2, 3, 4]    # büyük olay yeni dizi açsa da zincirle eski diziden türer
    assert tur[2].tolist() == [4]
    assert k.kok_bul(soy)(2) == 0 and k.kok_bul(soy)(6) == 6


def test_tahmin_uret_sentetik():
    z = 1e9 + np.array([0, 0.5, 2.0, 40.0]) * k.GUN_MS
    mw = np.array([5.0, 4.2, 3.0, 3.0])
    eb = np.array([-1, 0, 0, 0])
    bagli = np.array([False, True, True, True])
    dizi_id, diziler, soy = k.diziler_kur(z, mw, eb, bagli)
    kok = k.kok_bul(soy)
    s = k.tahmin_uret(z, mw, dizi_id, diziler, soy, 2.0, {0: 2.0}, float(z.max()) + 30 * k.GUN_MS, kok)
    tl = {r['t']: r for r in s if r['dizi'] == 0}
    # 1 sa: pencere (1 sa, 7 g 1 sa] -> Mw 4,2 (0,5 g) ve Mw 3 (2 g) var; M4 gerçekleşti, M5 ve Mana değil
    assert tl['1 sa']['y']['M4'] == 1 and tl['1 sa']['y']['M5'] == 0 and tl['1 sa']['y']['Mana'] == 0
    # ilk saatte hiç artçı görülmedi -> sonsal önselin altına iner
    assert tl['1 sa']['n_olay'] == 1 and tl['1 sa']['gunc']['M4']['orta'] < tl['1 sa']['onsel']['M4']['orta']
    assert tl['3 g']['y']['M4'] == 0               # (3 g, 10 g] içinde olay yok
    assert '23 g' in tl
    for r in s:
        for h in k.HEDEFLER:
            assert 0 <= r['gunc'][h]['orta'] <= 1 and r['gunc'][h]['alt'] <= r['gunc'][h]['ust']


def test_olcutler_ve_bootstrap():
    rng = np.random.default_rng(1)
    n = 400
    kok = np.repeat(np.arange(100), 4)
    p = rng.uniform(0.02, 0.9, n)
    y = (rng.uniform(size=n) < p).astype(float)       # kalibre tahmin: iklimden daha iyi
    nokta, aralik, nk = k.blok_bootstrap(kok, p, np.full(n, y.mean()), y, b=300)
    assert nk == 100
    assert nokta['bss_g_c'] > 0
    assert nokta['bss_g_o'] == pytest.approx(nokta['bss_g_c'], abs=1e-6)   # önsel = sabit iklim iken eşit
    lo, hi = aralik['bss_g_c']
    assert lo < nokta['bss_g_c'] < hi
    nokta2, _, _ = k.blok_bootstrap(kok, 1 - p, np.full(n, y.mean()), y, b=50)   # ters tahmin: beceri negatif
    assert nokta2['bss_g_c'] < 0


def test_guvenilirlik_ve_kapsama():
    satirlar = [{'gunc': {'M4': {'orta': 0.5, 'alt': 0.3, 'ust': 0.7}}, 'onsel': {'M4': {'orta': 0.5, 'alt': 0.3, 'ust': 0.7}},
                 'y': {'M4': int(i % 2 == 0)}} for i in range(20)]
    g = k.guvenilirlik(satirlar, 'M4')
    assert len(g) == 1 and g[0]['n'] == 20 and g[0]['gozlenen'] == 0.5 and g[0]['bantta']
    assert k.kapsama(satirlar, 'M4')['kutu_payi'] == 1.0
    lo, hi = k.wilson(10, 20)
    assert lo < 0.5 < hi
