# Artçı olasılığı kalibrasyon ölçümü (gölge deney; canlı koda ve ETAS ön kaydına dokunmaz).
#
# Soru: kanala giden "7 günde en az bir M ≥ 4 / M ≥ 5 artçı" olasılıkları geçmişte ne kadar tuttu?
# Gerekçe: docs/literatur-taramasi-4-2026-11-26.md §2 (kanala giden sayının doğruluğu).
#
# Yöntem (hepsi nedensel; her tahmin yalnız yayın anına kadarki veriyi görür):
# 1. vesaire/tertremo/src/artci.js birebir Python'a taşınır (Reasenberg–Jones + Page ve ark. 2016 Bayes güncellemesi).
# 2. Diziler canlı sistemdeki kuralla kurulur (tur.js diziBelirle): en yakın komşu (kume.en_yakin_komsu, gunluk.py'deki
#    d_f/b/η0 seçimi) bağlı ebeveynin dizisine katılır; dizisiz Mw ≥ 4,0 olay yeni dizi açar; dizideki en büyükten
#    büyük olay yeni dizi açar (Mana güncellenir).
# 3. Her dizi için yayın anları 1 sa … 23 g; o ana kadarki dizi olaylarıyla sonsal; (t, t+7 g] için tahmin.
#    Gerçekleşme: pencerede ebeveyn zinciriyle diziden türeyen (büyük olay yeni dizi açsa da zincir sürer) Mw ≥ M olay var mı.
# 4. Ölçütler: Brier, log skoru, güvenilirlik, %10–%90 bandı; karşılaştırma önsel / güncel / sabit iklim oranı;
#    beceri aralıkları kök dizi (ebeveyn zinciri) bazlı blok bootstrap.
import argparse
import json
import math
import os
import sys
import time

import numpy as np

from hesap import etas, katalog as kat
from hesap.hucre import b_aki_utsu, hucre_anahtari, mc_maxc
from hesap.kume import en_yakin_komsu, esik, korelasyon_boyutu, mesafe_km

KOK = os.path.join(os.path.dirname(__file__), '..', '..')
ONBELLEK = os.path.join(KOK, 'hesap', '.onbellek')
CIKTI_JSON = os.path.join(ONBELLEK, 'deney', 'kalibrasyon.json')
NN_ONBELLEK = os.path.join(ONBELLEK, 'deney', 'kalibrasyon-nn.json')
RAPOR = os.path.join(KOK, 'docs', 'olcum-deney-kalibrasyon-2026-11.md')

GUN_MS = 86_400_000
LN10 = math.log(10)
LOG10E = 1 / LN10

# ---------- artci.js birebir taşıma ----------
PARAM = {
    'tr': {'a_ort': -2.42, 'a_sapma': 0.63, 'p': 0.98, 'c': 0.018, 'b': 1.0},
    'dunya': {'a_ort': -2.54, 'a_sapma': 0.71, 'p': 0.92, 'c': 0.018, 'b': 1.0},
}
G = 0.25
T_BAS = 0.01
IZGARA_N = 201
INTEGRAL_N = 200
B_GENEL = 1.0


def beklenen(a, p, c, b, mana, m, t1, t2):
    """[t1, t2] gün aralığında M ≥ m beklenen artçı sayısı; a sayı ya da dizi olabilir."""
    k = 10.0 ** (np.asarray(a, float) + b * (mana - m))
    if abs(p - 1) < 1e-12:
        return k * math.log((t2 + c) / (t1 + c))
    return k * ((t2 + c) ** (1 - p) - (t1 + c) ** (1 - p)) / (1 - p)


def mc_zaman(mana, t_gun, mc_katalog):
    """Page 2016 denklem 4: max(Mana/2 − G − log10 t, Mc_katalog); t ≤ 0 → sonsuz."""
    if not t_gun > 0:
        return math.inf
    return max(mana / 2 - G - math.log10(t_gun), mc_katalog)


def izgara(param):
    """a_ort ± 4σ, 201 nokta, normalize Gauss ağırlıklar."""
    z = -4 + 8 * np.arange(IZGARA_N) / (IZGARA_N - 1)
    a = param['a_ort'] + z * param['a_sapma']
    w = np.exp(-0.5 * z * z)
    w = w / w.sum()
    return {'a': a, 'w': w}


def _integral_i0(param, mana, t_simdi, mc_katalog):
    """∫_{T_BAS}^{tSimdi} 10^(b(Mana − Mc(t))) (t + c)^(−p) dt; u = ln t üzerinde yamuk (200 aralık)."""
    if not t_simdi > T_BAS:
        return 0.0
    p, c, b = param['p'], param['c'], param['b']
    u0 = math.log(T_BAS)
    h = (math.log(t_simdi) - u0) / INTEGRAL_N
    t = np.exp(u0 + np.arange(INTEGRAL_N + 1) * h)
    mc = np.maximum(mana / 2 - G - np.log10(t), mc_katalog)
    f = 10.0 ** (b * (mana - mc)) * (t + c) ** -p * t
    f[0] /= 2
    f[-1] /= 2
    return float(f.sum() * h)


def guncelle(iz, olaylar, param, mana, t_simdi, mc_katalog):
    """Ogata olabilirliğiyle a ızgarasının Bayesçi güncellemesi. olaylar: [(t gün, mw)]."""
    p, c, b = param['p'], param['c'], param['b']
    n = 0
    s = 0.0
    for t, mw in olaylar:
        if not (t >= T_BAS and t <= t_simdi):
            continue
        mc = mc_zaman(mana, t, mc_katalog)
        if not mw >= mc:
            continue
        n += 1
        s += b * (mana - mc) * LN10 - p * math.log(t + c)
    i0 = _integral_i0(param, mana, t_simdi, mc_katalog)
    a = iz['a']
    log_l = n * a * LN10 + s - 10.0 ** a * i0
    w = iz['w'] * np.exp(log_l - log_l.max())
    return {'a': a.copy(), 'w': w / w.sum()}


def olasilik(iz, param, mana, m, t1, t2):
    """En az bir M ≥ m artçı olasılığı: Poisson karışımı (orta), a'nın %10/%90 yüzdeliğinde tek-a (alt, ust)."""
    p, c, b = param['p'], param['c'], param['b']
    P = -np.expm1(-beklenen(iz['a'], p, c, b, mana, m, t1, t2))
    orta = 0.0
    birikim = 0.0
    i_alt = i_ust = None
    for i in range(len(iz['a'])):  # JS ile aynı sıralı toplama
        orta += iz['w'][i] * P[i]
        birikim += iz['w'][i]
        if i_alt is None and birikim >= 0.1:
            i_alt = i
        if i_ust is None and birikim >= 0.9:
            i_ust = i
    son = len(iz['a']) - 1
    return {'orta': float(orta), 'alt': float(P[son if i_alt is None else i_alt]),
            'ust': float(P[son if i_ust is None else i_ust])}


def dizi_b(mws, mc, t_simdi):
    """artci.js diziB: önsel baskınken b = 1; t ≥ 1 g, N ≥ 50, σ_b ≤ 0,1 iken dizinin kendi b'si."""
    n = len(mws)
    if not t_simdi >= 1 or n < 50:
        return B_GENEL
    ort = sum(mws) / n
    b = LOG10E / (ort - (mc - 0.05))
    if not b > 0 or not math.isfinite(b):
        return B_GENEL
    return b if b / math.sqrt(n) <= 0.1 else B_GENEL


# ---------- dizi kurma (tur.js diziBelirle) ----------
DIZI_ESIK = 4.0
MC_YEDEK = 2.0
HUCRE_GUN = 400          # canlı hücre tablosunun saklama penceresi (gunluk.SAKLA_GUN)
HUCRE_EN_AZ = 50         # hücre MAXC'si için en az olay; azsa yalnız katalog Mc'si


def diziler_kur(z, mw, ebeveyn, bagli):
    """Zaman sıralı olaylardan diziler. ebeveyn: indeks (-1 yok); bagli: bool.
    Dönüş: dizi_id (olay başına dizi ana şokunun indeksi ya da -1), diziler (ana şok indeksi → sözlük),
    soy (olay başına ebeveyn zincirinin dizi ana şoku indeksleri; kendi dizisi dahil)."""
    n = len(z)
    dizi_id = np.full(n, -1, dtype=np.int64)
    soy = [()] * n
    diziler = {}
    for j in range(n):
        p = int(ebeveyn[j]) if bagli[j] and ebeveyn[j] >= 0 else -1
        d = int(dizi_id[p]) if p >= 0 else -1
        soy_j = soy[p] if p >= 0 else ()
        if d >= 0 and not mw[j] > diziler[d]['mw']:
            dizi_id[j] = d
        elif d >= 0 or mw[j] >= DIZI_ESIK:   # dizideki en büyükten büyük, ya da dizisiz eşik üstü
            if d >= 0:
                diziler[d]['ust'] = min(diziler[d]['ust'], z[j])   # üst: eski dizi aşıldı
            dizi_id[j] = j
            diziler[j] = {'mw': float(mw[j]), 't0': float(z[j]), 'ust': math.inf, 'uyeler': []}
        if dizi_id[j] >= 0:
            diziler[int(dizi_id[j])]['uyeler'].append(j)
            if dizi_id[j] not in soy_j:
                soy_j = soy_j + (int(dizi_id[j]),)
        soy[j] = soy_j
    return dizi_id, diziler, soy


def soy_olaylari(soy, diziler):
    """Dizi başına türeyen olaylar (kendisi hariç), zaman sıralı indeks dizisi."""
    tur = {d: [] for d in diziler}
    for k, s in enumerate(soy):
        for d in s:
            if d != k:
                tur[d].append(k)
    return {d: np.array(v, dtype=np.int64) for d, v in tur.items()}


def mc_dizi(d, z, mw, hucre_idx, mc_katalog):
    """Dizi Mc'si: katalog tamlığı (MBS, 2018–2021) ile ana şok hücresinin önceki 400 günlük MAXC + 0,2 değerinden büyük olanı."""
    idx = hucre_idx.get(d)
    if idx is None or len(idx) < HUCRE_EN_AZ:
        return mc_katalog
    return max(mc_katalog, mc_maxc(mw[idx]))


# ---------- tahminler ----------
T_LISTE = [(1 / 24, '1 sa'), (0.25, '6 sa'), (1.0, '1 g'), (3.0, '3 g'), (7.0, '7 g'), (14.0, '14 g'), (23.0, '23 g')]
PENCERE = 7.0
HEDEFLER = ('M4', 'M5', 'Mana')
BANTLAR = [('4–4,9', 4.0, 5.0), ('5–5,9', 5.0, 6.0), ('≥ 6', 6.0, 99.0)]


def bant_adi(mana):
    for ad, a, u in BANTLAR:
        if a <= mana < u:
            return ad
    return BANTLAR[0][0]


def mekan_yaricapi(mana):
    """Mekânsal gerçekleşme (duyarlılık) yarıçapı, km: 20 + 2 × yüzey kırığı uzunluğu (Wells ve Coppersmith 1994, log L = −2,44 + 0,59 M)."""
    return 20 + 2 * 10 ** (-2.44 + 0.59 * mana)


def tahmin_uret(z, mw, dizi_id, diziler, soy, mc_kat, mc_d, bitis_ms, kok_fn, da=0.0, konum=None, secilen=None):
    """Her (dizi, yayın anı) için tahmin satırı; yalnız o ana kadarki dizi olayları kullanılır.
    da: önsel a ortalamasına eklenen kaydırma (önsel duyarlılık analizi; 0 = canlı model).
    konum: (enlem, boylam) verilirse ayrıca mekânsal gerçekleşme (y_mekan, sayi_mekan) hesaplanır.
    secilen: yalnız bu dizi indeksleri (varsayılan hepsi)."""
    tur = soy_olaylari(soy, diziler)
    satirlar = []
    if konum is not None:
        bu = np.flatnonzero(mw >= 4.0)
        bz, bm, be, bb = z[bu], mw[bu], konum[0][bu], konum[1][bu]
    for d, bilgi in diziler.items():
        if secilen is not None and d not in secilen:
            continue
        mana = bilgi['mw']
        t0 = bilgi['t0']
        uyeler = np.array(bilgi['uyeler'], dtype=np.int64)
        tur_z = z[tur[d]]
        tur_m = mw[tur[d]]
        mc = mc_d[d]
        param0 = dict(PARAM['tr'])
        param0['a_ort'] += da
        onsel = izgara(param0)
        if konum is not None:
            yak = mesafe_km(konum[0][d], konum[1][d], be, bb) <= mekan_yaricapi(mana)
            yak &= (bz > t0) & (bz <= t0 + (T_LISTE[-1][0] + PENCERE) * GUN_MS)
            yz, ym = bz[yak], bm[yak]
        for t, ad in T_LISTE:
            mutlak = t0 + t * GUN_MS
            if not mutlak < bilgi['ust']:    # dizi bu ana dek aşıldı: yayın dizisi artık başka
                continue
            if mutlak + PENCERE * GUN_MS > bitis_ms:
                continue
            ust_sinir = uyeler[z[uyeler] <= mutlak]
            olaylar = [((z[k] - t0) / GUN_MS, mw[k]) for k in ust_sinir if mw[k] >= mc]
            b = dizi_b([m for tt, m in olaylar if tt > 0], mc, t)
            param = {**param0, 'b': b}
            iz = guncelle(izgara(param), olaylar, param, mana, t, mc)
            pencere = (tur_z > mutlak) & (tur_z <= mutlak + PENCERE * GUN_MS)
            pm = tur_m[pencere]
            satir = {'dizi': int(d), 'kok': int(kok_fn(d)), 'mana': mana, 'bant': bant_adi(mana), 't': ad, 't_gun': t,
                     'n_olay': len(olaylar), 'b': b, 'mc': mc, 'sayi': {}, 'y': {}, 'gunc': {}, 'onsel': {}}
            for hedef, m in (('M4', 4.0), ('M5', 5.0), ('Mana', mana)):
                satir['gunc'][hedef] = olasilik(iz, param, mana, m, t, t + PENCERE)
                satir['onsel'][hedef] = olasilik(onsel, param0, mana, m, t, t + PENCERE)
                k = int((pm >= m).sum())
                satir['sayi'][hedef] = k
                satir['y'][hedef] = int(k > 0)
                if konum is not None:
                    km = int(((yz > mutlak) & (yz <= mutlak + PENCERE * GUN_MS) & (ym >= m)).sum())
                    satir.setdefault('sayi_mekan', {})[hedef] = km
                    satir.setdefault('y_mekan', {})[hedef] = int(km > 0)
            satirlar.append(satir)
    return satirlar


# ---------- ölçütler ----------
EPS = 1e-6


def _ls(p, y):
    p = np.clip(p, EPS, 1 - EPS)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def toplamlar(p_g, p_o, y):
    """Dizi (küme) bazlı toplanabilir büyüklükler: [n, Σy, ΣBS_g, ΣBS_o, ΣLS_g, ΣLS_o]."""
    return np.array([len(y), y.sum(), ((p_g - y) ** 2).sum(), ((p_o - y) ** 2).sum(), _ls(p_g, y).sum(), _ls(p_o, y).sum()])


def olcutler(s):
    """s: [..., 6] toplamlar → sözlük (n, oran, Brier'ler, beceri skorları, log skoru kazançları)."""
    s = np.atleast_2d(s)
    n, sy = s[:, 0], s[:, 1]
    with np.errstate(divide='ignore', invalid='ignore'):
        pb = sy / n
        bs_g, bs_o = s[:, 2] / n, s[:, 3] / n
        bs_c = pb * (1 - pb)
        ls_g, ls_o = s[:, 4] / n, s[:, 5] / n
        ls_c = -(pb * np.log(pb) + (1 - pb) * np.log(1 - pb))
        ls_c = np.where((pb > 0) & (pb < 1), ls_c, 0.0)
        gecerli = bs_c > 0
        return {
            'n': n, 'oran': pb, 'bs_g': bs_g, 'bs_o': bs_o, 'bs_c': bs_c,
            'bss_g_c': np.where(gecerli, 1 - bs_g / bs_c, np.nan),
            'bss_o_c': np.where(gecerli, 1 - bs_o / bs_c, np.nan),
            'bss_g_o': np.where(bs_o > 0, 1 - bs_g / bs_o, np.nan),
            'ls_g': ls_g, 'ls_o': ls_o, 'ls_c': ls_c,
            'lsk_g_c': np.where(gecerli, ls_c - ls_g, np.nan),
            'lsk_o_c': np.where(gecerli, ls_c - ls_o, np.nan),
            'lsk_g_o': ls_o - ls_g,
        }


ANAHTARLAR = ('bss_g_c', 'bss_o_c', 'bss_g_o', 'lsk_g_c', 'lsk_o_c', 'lsk_g_o')


def blok_bootstrap(kok, p_g, p_o, y, b=2000, tohum=0):
    """Kök dizi bazlı blok bootstrap: beceri skorları için %95 yüzdelik aralığı. (nokta, {anahtar: (alt, ust)})."""
    kok = np.asarray(kok)
    kokler, ters = np.unique(kok, return_inverse=True)
    k = len(kokler)
    agg = np.zeros((k, 6))
    for i in range(k):
        m = ters == i
        agg[i] = toplamlar(p_g[m], p_o[m], y[m])
    nokta = {a: float(v[0]) for a, v in olcutler(agg.sum(axis=0)).items()}
    aralik = {}
    if k < 2:
        return nokta, {a: (math.nan, math.nan) for a in ANAHTARLAR}, k
    rng = np.random.default_rng(tohum)
    sayim = rng.multinomial(k, np.full(k, 1 / k), size=b)
    o = olcutler(sayim @ agg)
    for a in ANAHTARLAR:
        v = o[a][np.isfinite(o[a])]
        aralik[a] = (float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))) if v.size >= 20 else (math.nan, math.nan)
    return nokta, aralik, k


def _vektor(satirlar, hedef):
    p_g = np.array([s['gunc'][hedef]['orta'] for s in satirlar])
    p_o = np.array([s['onsel'][hedef]['orta'] for s in satirlar])
    y = np.array([s['y'][hedef] for s in satirlar], float)
    kok = [s['kok'] for s in satirlar]
    return kok, p_g, p_o, y


def tablo_satiri(satirlar, hedef, tohum=0, b=2000):
    kok, p_g, p_o, y = _vektor(satirlar, hedef)
    nokta, aralik, k = blok_bootstrap(kok, p_g, p_o, y, b=b, tohum=tohum)
    nokta['n_kok'] = k
    nokta['n_olay_pozitif'] = int(y.sum())
    nokta['ort_g'] = float(p_g.mean())
    nokta['ort_o'] = float(p_o.mean())
    nokta['aralik'] = aralik
    return nokta


KUTULAR = [0, 0.01, 0.03, 0.10, 0.25, 0.50, 0.75, 1.0001]


def wilson(k, n, z=1.96):
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    d = 1 + z * z / n
    m = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (m - h, m + h)


def guvenilirlik(satirlar, hedef, model='gunc'):
    """Olasılık kutuları: n, tahmin ortalaması, gözlenen oran (Wilson %95), %10–%90 bandının ortalaması."""
    p = np.array([s[model][hedef]['orta'] for s in satirlar])
    alt = np.array([s[model][hedef]['alt'] for s in satirlar])
    ust = np.array([s[model][hedef]['ust'] for s in satirlar])
    y = np.array([s['y'][hedef] for s in satirlar], float)
    sonuc = []
    for lo, hi in zip(KUTULAR[:-1], KUTULAR[1:]):
        m = (p >= lo) & (p < hi)
        n = int(m.sum())
        if n == 0:
            continue
        k = int(y[m].sum())
        w = wilson(k, n)
        sonuc.append({'kutu': (lo, min(hi, 1.0)), 'n': n, 'tahmin': float(p[m].mean()), 'gozlenen': k / n, 'k': k,
                      'wilson': w, 'alt': float(alt[m].mean()), 'ust': float(ust[m].mean()),
                      'bantta': bool(alt[m].mean() <= k / n <= ust[m].mean())})
    return sonuc


def kapsama(satirlar, hedef):
    """Bant kapsaması: (a) kutu başına gözlenen oran %10–%90 bandının ortalaması içinde mi (n ağırlıklı pay);
    (b) bütün satırlarda gözlenen oran vs bant ortalamaları."""
    g = guvenilirlik(satirlar, hedef)
    n_top = sum(k['n'] for k in g)
    pay = sum(k['n'] for k in g if k['bantta']) / n_top if n_top else math.nan
    alt = float(np.mean([s['gunc'][hedef]['alt'] for s in satirlar]))
    ust = float(np.mean([s['gunc'][hedef]['ust'] for s in satirlar]))
    gozl = float(np.mean([s['y'][hedef] for s in satirlar]))
    return {'kutu_payi': pay, 'ort_alt': alt, 'ort_ust': ust, 'gozlenen': gozl, 'ort_tahmin': float(np.mean([s['gunc'][hedef]['orta'] for s in satirlar]))}


def usgs_tabani(satirlar, tohum=0, b=2000):
    """M ≥ Mana hedefi: güncel, önsel, USGS sabit %5, sabit iklim oranı (Brier, log skoru)."""
    kok, p_g, p_o, y = _vektor(satirlar, 'Mana')
    p5 = np.full_like(p_g, 0.05)
    nokta, aralik, k = blok_bootstrap(kok, p_g, p_o, y, b=b, tohum=tohum)
    # USGS %5 'önsel' yerine konur: beceri skoru = 1 − BS_model/BS_usgs
    n5, a5, _ = blok_bootstrap(kok, p_g, p5, y, b=b, tohum=tohum)
    n5o, a5o, _ = blok_bootstrap(kok, p_o, p5, y, b=b, tohum=tohum)
    return {'n': len(y), 'n_kok': k, 'pozitif': int(y.sum()), 'oran': float(y.mean()),
            'bs_gunc': nokta['bs_g'], 'bs_onsel': nokta['bs_o'], 'bs_usgs': n5['bs_o'], 'bs_iklim': nokta['bs_c'],
            'ls_gunc': nokta['ls_g'], 'ls_onsel': nokta['ls_o'], 'ls_usgs': n5['ls_o'], 'ls_iklim': nokta['ls_c'],
            'bss_gunc_usgs': (n5['bss_g_o'], a5['bss_g_o']), 'bss_onsel_usgs': (n5o['bss_g_o'], a5o['bss_g_o']),
            'bss_gunc_iklim': (nokta['bss_g_c'], aralik['bss_g_c']), 'ort_gunc': float(p_g.mean()), 'ort_onsel': float(p_o.mean())}



DA_IZGARA = [-0.6, -0.4, -0.3, -0.2, -0.1, 0.0, 0.1, 0.2]


def kaydirma_analizi(satirlar_da, hedef, bant=None, b=2000, tohum=0):
    """Önsel a ortalamasını da kadar kaydırınca (log10 hız ölçeği) ölçütler. satirlar_da: {da: satırlar}, satır sırası aynı.
    Dönüş: her da için n, BS/LS (güncel, önsel); log skoru en düşük da (güncel, önsel) ve kök bazlı bootstrap %95 aralığı."""
    das = sorted(satirlar_da)
    ref = satirlar_da[das[0]]
    sec = [i for i, r in enumerate(ref) if bant is None or r['bant'] == bant]
    kok = np.array([ref[i]['kok'] for i in sec])
    kokler, ters = np.unique(kok, return_inverse=True)
    kk = len(kokler)
    agg = {}
    sonuc = {'da': {}, 'n_kok': kk}
    for da in das:
        rs = satirlar_da[da]
        p_g = np.array([rs[i]['gunc'][hedef]['orta'] for i in sec])
        p_o = np.array([rs[i]['onsel'][hedef]['orta'] for i in sec])
        y = np.array([rs[i]['y'][hedef] for i in sec], float)
        a = np.zeros((kk, 6))
        for j in range(kk):
            mk = ters == j
            a[j] = toplamlar(p_g[mk], p_o[mk], y[mk])
        agg[da] = a
        t = a.sum(axis=0)
        sonuc['da'][da] = {'n': int(t[0]), 'bs_g': t[2] / t[0], 'bs_o': t[3] / t[0], 'ls_g': t[4] / t[0], 'ls_o': t[5] / t[0],
                           'ort_g': float(p_g.mean()), 'ort_o': float(p_o.mean()), 'oran': float(y.mean())}
    rng = np.random.default_rng(tohum)
    sayim = rng.multinomial(kk, np.full(kk, 1 / kk), size=b)
    for ad, kol in (('en_iyi_g', 4), ('en_iyi_o', 5)):
        ls = np.stack([(sayim @ agg[da])[:, kol] for da in das], axis=1)       # b × |da|
        en = np.array(das)[ls.argmin(axis=1)]
        nokta = das[int(np.argmin([sonuc['da'][da]['ls_g' if kol == 4 else 'ls_o'] for da in das]))]
        sonuc[ad] = {'nokta': nokta, 'alt': float(np.percentile(en, 2.5)), 'ust': float(np.percentile(en, 97.5))}
    return sonuc


def varsayimsal_dizi(z, mw, ebeveyn, bagli, idx):
    """İndeksi idx olan olayı ana şok sayan varsayımsal dizi (canlı kural onu ayrı dizi saymasa bile): ebeveyn zinciriyle
    türeyen olaylar üye; ana şoktan büyük ilk türev diziyi aşar. Dönüş: (diziler, soy) tahmin_uret biçiminde."""
    soy = [()] * len(z)
    soy[idx] = (idx,)
    tur = {idx}
    uyeler = [idx]
    ust = math.inf
    for k in range(idx + 1, len(z)):
        if bagli[k] and ebeveyn[k] in tur:
            tur.add(k)
            soy[k] = (idx,)
            if mw[k] > mw[idx]:
                ust = min(ust, z[k])
            else:
                uyeler.append(k)
    return {idx: {'mw': float(mw[idx]), 't0': float(z[idx]), 'ust': ust, 'uyeler': uyeler}}, soy


# ---------- katalog, kümeleme ----------
def katalog_yukle():
    o = sorted(kat.yukle(os.path.join(ONBELLEK, 'tr.csv.gz')), key=lambda r: r['zaman_ms'])
    z = np.array([r['zaman_ms'] for r in o])
    e = np.array([r['enlem'] for r in o])
    bo = np.array([r['boylam'] for r in o])
    m = np.array([r['mw'] for r in o])
    return o, z, e, bo, m


def kume_parametreleri(z, e, bo, m):
    """gunluk.hesapla ile aynı seçim (patlatma ayıklaması hariç): Mc = MBS (2018–2021), b = Aki–Utsu, d_f = korelasyon boyutu."""
    mbs = etas.mc_egitim(z, m)[1]
    mc = mbs if math.isfinite(mbs) else mc_maxc(m)
    d_f = korelasyon_boyutu(e, bo)
    if not 1.0 <= d_f <= 2.0:
        d_f = 1.6
    b, _ = b_aki_utsu(m, mc)
    if not (math.isfinite(b) and 0.6 <= b <= 1.5):
        b = 1.0
    return float(mc), round(float(d_f), 3), round(float(b), 3)


def nn_hesapla(z, e, bo, m, yeniden=False):
    mc, d_f, b = kume_parametreleri(z, e, bo, m)
    if os.path.exists(NN_ONBELLEK) and not yeniden:
        with open(NN_ONBELLEK, encoding='utf-8') as f:
            c = json.load(f)
        if c.get('n') == len(z) and c.get('d_f') == d_f and c.get('b') == b:
            return mc, d_f, b, c['log_eta0'], np.array(c['ebeveyn']), np.array([math.inf if x is None else x for x in c['log_eta']])
    eb, le = en_yakin_komsu(z, e, bo, m, d_f, b, 'tr')
    le0 = round(float(esik(le)), 3)
    os.makedirs(os.path.dirname(NN_ONBELLEK), exist_ok=True)
    with open(NN_ONBELLEK, 'w', encoding='utf-8') as f:
        json.dump({'n': len(z), 'd_f': d_f, 'b': b, 'log_eta0': le0, 'ebeveyn': eb.tolist(),
                   'log_eta': [None if not math.isfinite(x) else float(x) for x in le]}, f)
    return mc, d_f, b, le0, eb, le


def hucre_endeksi(z, e, bo, m, diziler):
    """Dizi ana şokunun 1° hücresinde önceki 400 günlük olayların indeksi (nedensel)."""
    anahtar = np.array([hucre_anahtari(a, b, 'tr') for a, b in zip(e, bo)], dtype=object)
    gruplar = {}
    for i, k in enumerate(anahtar):
        gruplar.setdefault(k, []).append(i)
    gruplar = {k: np.array(v) for k, v in gruplar.items()}
    sonuc = {}
    for d in diziler:
        g = gruplar[anahtar[d]]
        zg = z[g]
        sonuc[d] = g[(zg >= z[d] - HUCRE_GUN * GUN_MS) & (zg < z[d])]
    return sonuc


def kok_bul(soy):
    def f(d):
        return soy[d][0] if soy[d] else d
    return f


# ---------- tek tek diziler ----------
OZEL = {
    'Kahramanmaraş 2023': ('2023-02-06', '2023-02-07', 7.5, None),
    'Sındırgı 10 Ağustos 2025': ('2025-08-10', '2025-08-11', 5.8, (39.0, 39.5, 27.9, 28.6)),
    'Sındırgı 27 Ekim 2025': ('2025-10-27', '2025-10-28', 5.8, (39.0, 39.5, 27.9, 28.6)),
    'Marmara 23 Nisan 2025': ('2025-04-23', '2025-04-24', 5.8, (40.5, 41.1, 27.5, 29.0)),
}


def ozel_olay_bul(z, e, bo, m, ad):
    """Tarih penceresi ve kutudaki en büyük olayın indeksi (yoksa None)."""
    bas, son, mw_alt, kutu = OZEL[ad]
    ms = lambda x: np.datetime64(x).astype('datetime64[ms]').astype(np.int64)
    ok = (z >= ms(bas)) & (z < ms(son)) & (m >= mw_alt)
    if kutu is not None:
        ok &= (e >= kutu[0]) & (e <= kutu[1]) & (bo >= kutu[2]) & (bo <= kutu[3])
    idx = np.flatnonzero(ok)
    return int(idx[np.argmax(m[idx])]) if idx.size else None


# ---------- rapor ----------
def _yz(x, n=3):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return '—'
    return f'{x:.{n}f}'.replace('.', ',')


def _yuzde(x, n=1):
    return '—' if x is None or not math.isfinite(x) else f'{100 * x:.{n}f}'.replace('.', ',') + ' %'


def _aralik(v, a, n=3):
    return f'{_yz(v, n)} [{_yz(a[0], n)}; {_yz(a[1], n)}]'


HEDEF_AD = {'M4': '7 günde ≥ 1 M ≥ 4', 'M5': '7 günde ≥ 1 M ≥ 5', 'Mana': '7 günde ≥ 1 M ≥ Mana (ana şok kadar ya da büyük)'}


def rapor_yaz(s):
    L = []
    w = L.append
    w('# Ölçüm deneyi: artçı olasılığı kalibrasyonu (Türkiye)')
    w('')
    w(f'Tarih: {s["tarih"]}. Betik: `hesap/deney/kalibrasyon.py`; ham sonuç `hesap/.onbellek/deney/kalibrasyon.json`. Canlı koda dokunulmadı.')
    w('')
    w('## Soru ve gerekçe')
    w('')
    w('Kanala giden Türkiye artçı satırları ("7 günde en az bir M ≥ 4" ve "M ≥ 5") geçmişte ne kadar tuttu? Gerekçe: `docs/literatur-taramasi-4-2026-11-26.md` §2.')
    w('')
    w('## Yöntem')
    w('')
    w(f'- Model: `vesaire/tertremo/src/artci.js` birebir Python\'a taşındı (Reasenberg–Jones, Page ve ark. 2016; PARAM.tr, G 0,25, T_BAS 0,01 g, ızgara 201, integral 200). Eşdeğerlik `hesap/tests/test_deney_kalibrasyon.py` içinde JS\'ten üretilmiş sayılarla gösterilir.')
    w(f'- Veri: EMSC Türkiye kutusu `tr.csv.gz` (M ≥ 2, {s["veri"]["bas"]} → {s["veri"]["bit"]}, {s["veri"]["n"]} olay).')
    w(f'- Kümeleme: gunluk.py\'deki seçimle d_f = {_yz(s["kume"]["d_f"])}, b = {_yz(s["kume"]["b"])}, η0 = {_yz(s["kume"]["log_eta0"])}, katalog Mc (MBS, 2018–2021) = {_yz(s["kume"]["mc"], 2)}. Parametreler bütün katalogdan bir kez kestirilir (gece işi de kararlı değerleri korur). d_f ham korelasyon boyutu {_yz(s["kume"]["d_f_ham"])}, bant [1, 2] dışı olduğundan gunluk.py gibi 1,6 kullanıldı. {s["kume"]["dogrulama"]} Ebeveyn adayı kume.py\'nin 10 yıllık penceresiyle bulunur; canlı kume.js 365 gündür.')
    w(f'- Dizi kuralı (tur.js diziBelirle): bağlı olay ebeveyninin dizisine katılır; dizisiz Mw ≥ 4,0 olay yeni dizi açar; dizideki ana şoktan büyük olay yeni dizi açar (Mana güncellenir). Toplam {s["veri"]["n_dizi"]} dizi, {s["veri"]["n_kok"]} kök dizi.')
    w('- Dizi Mc: katalog Mc\'si ile ana şok hücresinin (1°) önceki 400 günlük MAXC + 0,2 değerinden büyük olanı; hücrede 50\'den az olay varsa yalnız katalog Mc\'si. Canlı hücre Mc\'sinin sade bir yaklaşımıdır; yedek 2,0.')
    w('- Yayın anları dizi açılışından 1 sa, 6 sa, 1 g, 3 g, 7 g, 14 g, 23 g. Her tahmin yalnız o ana kadarki dizi olaylarıyla yapılır (b dahil: diziB kuralı). Yayın anında dizi başka bir ana şokla aşılmışsa o dizi için tahmin yok (canlı sistemde yayın yeni diziye geçer). Pencere (t, t+7 g] katalog sonuna sığmıyorsa tahmin atılır.')
    w('- Gerçekleşme: pencerede dizinin ebeveyn zinciriyle türeyen (büyük olay yeni dizi açsa da zincir sürer) Mw ≥ M olay var mı.')
    w('- Karşılaştırma: (a) önsel: Bayes güncellemesi yok, aynı pencere; (b) güncel: canlı model; (c) sabit iklim oranı: ilgili alt kümedeki gözlenen oran (örnek içi, bu yüzden iklim için hafif cömert).')
    w('- Beceri aralıkları: kök dizi (ebeveyn zinciriyle aynı kökten çıkan diziler tek blok) bazlı blok bootstrap, 2000 yeniden örnekleme, %95 yüzdelik aralığı.')
    w('- Bant kapsaması: modelin %10–%90 bandı a\'nın %10 ve %90 yüzdeliğindeki olasılıktır. İkili sonuç için satır bazlı kapsama tanımsızdır; bu yüzden olasılık kutusu başına gözlenen oranın kutudaki bant ortalamaları arasında kalıp kalmadığı verilir (kutu n ağırlıklı pay).')
    w('')
    w('## Örneklem')
    w('')
    w('| Hedef | Tahmin satırı | Kök dizi | Gerçekleşen (y=1) | Oran |')
    w('|---|---:|---:|---:|---:|')
    for h in HEDEFLER:
        g = s['genel'][h]
        w(f'| {HEDEF_AD[h]} | {g["n"]:.0f} | {g["n_kok"]} | {g["n_olay_pozitif"]} | {_yuzde(g["oran"])} |')
    w('')
    w('Aynı dizinin farklı yayın anlarındaki satırları ilişkilidir; bu yüzden bütün aralıklar kök dizi bazlı bootstrap ile verilir ve etkin örneklem satır sayısından çok daha küçüktür.')
    w('')
    for h in HEDEFLER:
        w(f'## Genel sonuç: {HEDEF_AD[h]}')
        w('')
        g = s['genel'][h]
        w(f'Brier: güncel {_yz(g["bs_g"], 4)}, önsel {_yz(g["bs_o"], 4)}, sabit iklim {_yz(g["bs_c"], 4)}. Log skoru (düşük iyi): güncel {_yz(g["ls_g"], 4)}, önsel {_yz(g["ls_o"], 4)}, iklim {_yz(g["ls_c"], 4)}.')
        w('')
        w('| Beceri (Brier, 1 − BS/BS_ref) | Değer [%95 aralık] |')
        w('|---|---|')
        w(f'| güncel vs iklim | {_aralik(g["bss_g_c"], g["aralik"]["bss_g_c"])} |')
        w(f'| önsel vs iklim | {_aralik(g["bss_o_c"], g["aralik"]["bss_o_c"])} |')
        w(f'| güncel vs önsel | {_aralik(g["bss_g_o"], g["aralik"]["bss_g_o"])} |')
        w(f'| log skoru kazancı güncel vs iklim (nat/tahmin) | {_aralik(g["lsk_g_c"], g["aralik"]["lsk_g_c"])} |')
        w(f'| log skoru kazancı güncel vs önsel (nat/tahmin) | {_aralik(g["lsk_g_o"], g["aralik"]["lsk_g_o"])} |')
        w('')
    for h in HEDEFLER:
        for ad, anahtar in (('yayın anına göre', 'alt_t'), ('Mana bandına göre', 'alt_bant')):
            w(f'## Alt tablo: {HEDEF_AD[h]}, {ad}')
            w('')
            w('| Dilim | n | kök | y=1 | gözlenen oran | ort. P güncel | ort. P önsel | BS güncel | BS önsel | BS iklim | BSS güncel/iklim | BSS önsel/iklim | BSS güncel/önsel |')
            w('|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|')
            for dilim, g in s[anahtar][h].items():
                w(f'| {dilim} | {g["n"]:.0f} | {g["n_kok"]} | {g["n_olay_pozitif"]} | {_yuzde(g["oran"])} | {_yuzde(g["ort_g"])} | {_yuzde(g["ort_o"])} | {_yz(g["bs_g"], 4)} | {_yz(g["bs_o"], 4)} | {_yz(g["bs_c"], 4)} | '
                  f'{_aralik(g["bss_g_c"], g["aralik"]["bss_g_c"], 2)} | {_aralik(g["bss_o_c"], g["aralik"]["bss_o_c"], 2)} | {_aralik(g["bss_g_o"], g["aralik"]["bss_g_o"], 2)} |')
            w('')
    w('## Güvenilirlik tabloları (bütün yayın anları birlikte)')
    w('')
    for h in HEDEFLER:
        for model, mad in (('gunc', 'güncel'), ('onsel', 'önsel')):
            w(f'### {HEDEF_AD[h]} — {mad}')
            w('')
            w('| Olasılık kutusu | n | tahmin ort. | gözlenen oran [Wilson %95] | bant ort. (%10–%90) | gözlenen bantta mı |')
            w('|---|---:|---:|---|---|---|')
            for k in s['guvenilirlik'][h][model]:
                w(f'| {_yuzde(k["kutu"][0], 0)}–{_yuzde(k["kutu"][1], 0)} | {k["n"]} | {_yuzde(k["tahmin"])} | {_yuzde(k["gozlenen"])} ({k["k"]}/{k["n"]}) [{_yuzde(k["wilson"][0])}; {_yuzde(k["wilson"][1])}] | '
                  f'{_yuzde(k["alt"])} – {_yuzde(k["ust"])} | {"evet" if k["bantta"] else "hayır"} |')
            w('')
    w('### Bant kapsaması özeti (güncel model)')
    w('')
    w('| Hedef | tahmin ort. | gözlenen oran | bant ort. (%10–%90) | gözlenen oran bantta olan kutuların payı |')
    w('|---|---:|---:|---|---:|')
    for h in HEDEFLER:
        k = s['kapsama'][h]
        w(f'| {HEDEF_AD[h]} | {_yuzde(k["ort_tahmin"])} | {_yuzde(k["gozlenen"])} | {_yuzde(k["ort_alt"])} – {_yuzde(k["ort_ust"])} | {_yuzde(k["kutu_payi"], 0)} |')
    w('')
    w('### Güvenilirlik, Mana bandına göre (güncel model)')
    w('')
    for h in ('M4', 'M5'):
        for bant, gv in s['guvenilirlik_bant'][h].items():
            w(f'**{HEDEF_AD[h]}, Mana {bant}**')
            w('')
            w('| Olasılık kutusu | n | tahmin ort. | gözlenen oran (k/n) [Wilson %95] |')
            w('|---|---:|---:|---|')
            for k in gv:
                w(f'| {_yuzde(k["kutu"][0], 0)}–{_yuzde(k["kutu"][1], 0)} | {k["n"]} | {_yuzde(k["tahmin"])} | {_yuzde(k["gozlenen"])} ({k["k"]}/{k["n"]}) [{_yuzde(k["wilson"][0])}; {_yuzde(k["wilson"][1])}] |')
            w('')
    w('## Duyarlılık 1: mekânsal gerçekleşme tanımı')
    w('')
    w('Zincir tanımı (ana metin) komşu bir diziye atanan ya da kümeleme zincirini kıran olayı saymaz (ör. 20 Şubat 2023 Hatay Mw 6,3 Kahramanmaraş dizisine bağlanmıyor). Burada gerçekleşme: ana şoktan en çok R km uzakta (R = 20 + 2 × yüzey kırığı uzunluğu, Wells ve Coppersmith 1994), pencerede herhangi bir Mw ≥ M olay, dizi üyeliğinden bağımsız. Tahminler aynıdır.')
    w('')
    w('| Hedef | y=1 (zincir) | y=1 (mekânsal) | ort. P güncel | gözlenen oran (mekânsal) | BS güncel | BS iklim | BSS güncel/iklim | BSS güncel/önsel |')
    w('|---|---:|---:|---:|---:|---:|---:|---|---|')
    for h in HEDEFLER:
        g = s['mekan'][h]
        w(f'| {HEDEF_AD[h]} | {s["genel"][h]["n_olay_pozitif"]} | {g["n_olay_pozitif"]} | {_yuzde(g["ort_g"])} | {_yuzde(g["oran"])} | {_yz(g["bs_g"], 4)} | {_yz(g["bs_c"], 4)} | '
          f'{_aralik(g["bss_g_c"], g["aralik"]["bss_g_c"], 2)} | {_aralik(g["bss_g_o"], g["aralik"]["bss_g_o"], 2)} |')
    w('')
    w('## Duyarlılık 2: önsel a kaydırması')
    w('')
    w('Önsel a ortalaması (−2,42) log10 ölçeğinde da kadar kaydırılır (güncel modelin önseli de aynı kadar), σ ve diğer parametreler sabit. da < 0 hızı düşürür (10^da çarpanı). En iyi da: log skoru en düşük kaydırma, kök bazlı bootstrap %95 aralığıyla. Kayıp zincir tanımıyla.')
    w('')
    for ad, h, bant in s['kaydirma_sirasi']:
        k = s['kaydirma'][ad]
        w(f'**{HEDEF_AD[h]}{"" if bant is None else ", Mana " + bant}** (n kök {k["n_kok"]}): en iyi da güncel {_yz(k["en_iyi_g"]["nokta"], 1)} [{_yz(k["en_iyi_g"]["alt"], 1)}; {_yz(k["en_iyi_g"]["ust"], 1)}], önsel {_yz(k["en_iyi_o"]["nokta"], 1)} [{_yz(k["en_iyi_o"]["alt"], 1)}; {_yz(k["en_iyi_o"]["ust"], 1)}]')
        w('')
        w('| da | ort. P güncel | gözlenen oran | BS güncel | LS güncel | BS önsel | LS önsel |')
        w('|---:|---:|---:|---:|---:|---:|---:|')
        for da, v in sorted(k['da'].items()):
            w(f'| {_yz(float(da), 1)} | {_yuzde(v["ort_g"])} | {_yuzde(v["oran"])} | {_yz(v["bs_g"], 5)} | {_yz(v["ls_g"], 5)} | {_yz(v["bs_o"], 5)} | {_yz(v["ls_o"], 5)} |')
        w('')
    w('## Dizi Mc dağılımı')
    w('')
    w(f'Dizi başına kullanılan Mc: en küçük {_yz(s["mc_ozet"]["min"], 2)}, medyan {_yz(s["mc_ozet"]["medyan"], 2)}, en büyük {_yz(s["mc_ozet"]["max"], 2)}; dizilerin {_yuzde(s["mc_ozet"]["katalog_payi"], 0)} kadarında hücre MAXC + 0,2 katalog Mc değerini aşmıyor (yani katalog Mc geçerli).')
    w('')
    u = s['usgs']
    w('## "Ana şoktan büyük ya da eşit" olay: USGS sabit %5 tabanıyla')
    w('')
    for ad, g in (('1 sa (t = 1 saat, (1 sa, 1 sa + 7 g])', u['t1sa']), ('Bütün yayın anları', u['hepsi'])):
        w(f'**{ad}**: n {g["n"]}, kök {g["n_kok"]}, gerçekleşen {g["pozitif"]} (oran {_yuzde(g["oran"])}). Tahmin ortalaması: güncel {_yuzde(g["ort_gunc"])}, önsel {_yuzde(g["ort_onsel"])}, USGS %5.')
        w('')
        w('| Model | Brier | Log skoru |')
        w('|---|---:|---:|')
        w(f'| güncel | {_yz(g["bs_gunc"], 4)} | {_yz(g["ls_gunc"], 4)} |')
        w(f'| önsel (RJ genel) | {_yz(g["bs_onsel"], 4)} | {_yz(g["ls_onsel"], 4)} |')
        w(f'| USGS sabit %5 | {_yz(g["bs_usgs"], 4)} | {_yz(g["ls_usgs"], 4)} |')
        w(f'| sabit iklim oranı | {_yz(g["bs_iklim"], 4)} | {_yz(g["ls_iklim"], 4)} |')
        w('')
        w(f'Brier becerisi güncel vs USGS %5: {_aralik(*g["bss_gunc_usgs"])}; önsel vs USGS %5: {_aralik(*g["bss_onsel_usgs"])}; güncel vs iklim: {_aralik(*g["bss_gunc_iklim"])}.')
        w('')
    w('## Tek tek diziler')
    w('')
    for ad, o in s['ozel'].items():
        w(f'### {ad}')
        w('')
        if o is None:
            w('Katalogda eşleşen dizi bulunamadı.')
            w('')
            continue
        if 'katildi' in o:
            kt = o['katildi']
            w(f'Olay: {kt["zaman"]}, Mw {_yz(kt["mw"], 1)}. Canlı kurala göre bu olay ayrı dizi açmaz: Mw ≤ Mana olduğundan {kt["dizi_zaman"]} tarihli Mw {_yz(kt["dizi_mana"], 1)} dizisine katılır ({_yz(kt["gun"], 1)} gün sonra; dizi 30 günlük ömrünü doldurmuş), yani ayrı bir artçı olasılığı yayımlanmazdı. Aşağıdaki tablo varsayımsaldır: olay ana şok sayılır, yalnız ondan zincirle türeyen olaylar üye ve gerçekleşme sayılır.')
            w('')
            o = {**o, **o['varsayim']}
        w(f'Ana şok: {o["zaman"]}, Mw {_yz(o["mana"], 1)}, ({_yz(o["enlem"], 2)}, {_yz(o["boylam"], 2)}); dizi Mc {_yz(o["mc"], 2)}; kök dizi Mana {_yz(o["kok_mana"], 1)}.')
        w('')
        w('| t | dizi olayı (Mc üstü) | b | önsel P(M≥4) | güncel P(M≥4) [%10–%90] | gözlenen M≥4 sayısı (zincir / mekânsal) | önsel P(M≥5) | güncel P(M≥5) [%10–%90] | gözlenen M≥5 sayısı (zincir / mekânsal) | güncel P(≥Mana) | gözlenen ≥Mana (zincir / mekânsal) |')
        w('|---|---:|---:|---:|---|---:|---:|---|---:|---:|---:|')
        for r in o['satirlar']:
            g4, g5, gm = r['gunc']['M4'], r['gunc']['M5'], r['gunc']['Mana']
            w(f'| {r["t"]} | {r["n_olay"]} | {_yz(r["b"], 2)} | {_yuzde(r["onsel"]["M4"]["orta"])} | {_yuzde(g4["orta"])} [{_yuzde(g4["alt"])}; {_yuzde(g4["ust"])}] | {r["sayi"]["M4"]} / {r.get("sayi_mekan", {}).get("M4", "—")} | '
              f'{_yuzde(r["onsel"]["M5"]["orta"])} | {_yuzde(g5["orta"])} [{_yuzde(g5["alt"])}; {_yuzde(g5["ust"])}] | {r["sayi"]["M5"]} / {r.get("sayi_mekan", {}).get("M5", "—")} | {_yuzde(gm["orta"])} | {r["sayi"]["Mana"]} / {r.get("sayi_mekan", {}).get("Mana", "—")} |')
        w('')
    w('## Sınırlar')
    w('')
    for x in s['sinirlar']:
        w(f'- {x}')
    w('')
    w(f'Süre: {s["sure_s"]:.0f} sn (küçük indirgeme yok; tam koşu).')
    w('')
    w('## Sonuç ve karar önerisi')
    w('')
    for x in SONUC:
        w(x)
    return '\n'.join(L) + '\n'


SINIRLAR = [
    'Türkiye kutusu Yunanistan, Ege, İran/Kafkas kenarlarını da içerir; EMSC tamlığı bölgeye göre değişir. Canlı "tr" kataloğu da aynı kutuyu kullanır, ama bu ölçüm yalnız Türkiye sınırına süzülmedi.',
    'Veri 2018–2026 (yaklaşık 8,8 yıl): M ≥ 5 dizi sayısı az; M ≥ 5 ve M ≥ Mana hedeflerinde gerçekleşen sayısı küçük, aralıklar geniştir.',
    'Küme parametreleri (d_f, b, η0, katalog Mc) bütün katalogdan bir kez kestirildi; canlı sistemde bu değerler gece güncellenir ama sabitlenir (toleranslı). Küçük bir bakış-ileri sızıntısı var; dizi kuralının kendisi nedenseldir.',
    'Katalog nihai EMSC sürümüdür; canlıdaki gerçek zamanlı erken eksik kayıt (ilk dakika/saatlerde AFAD/EMSC gecikmesi) burada yok. Canlı sonuç erken yayın anlarında daha kötü olabilir.',
    'Dizi Mc\'si sade yaklaşımdır (katalog MBS ve hücre MAXC + 0,2); canlıdaki hücre tablosu birebir yinelenmedi (bu veride hücre MAXC + 0,2 hiçbir dizide katalog Mc değerini aşmadığından sonuca etkisi yok).',
    'Gerçekleşme tanımı ebeveyn zincirine dayanır; kümeleme yanlışları (komşu dizilere yanlış atama) hem gerçekleşmeyi hem canlı dizi üyeliğini etkiler.',
    'Sabit iklim oranı örnek içidir (bütün satırlardan hesaplanır); iklime karşı beceri bu yüzden hafif düşük görünebilir.',
    'Zincir tanımlı gerçekleşme, kümeleme zincirinin kırıldığı olayları (ör. Hatay 20 Şubat 2023) sayamaz; mekânsal duyarlılık tablosu bunu gösterir.',
    'Aynı dizinin farklı yayın anları ve iç içe diziler bağımsız değildir; blok bootstrap yalnız kök dizi bağımlılığını sayar, uzay-zaman komşuluğundaki ayrı köklerin bağımlılığını saymaz.',
]


# Betik çıktısından yorum (sayılar yukarıdaki tablolardan; betik yeniden koşunca tablolar yenilenir, bu metin elle yazılıdır).
SONUC = [
    '**Karar önerisi: önseli değiştirme; modeli olduğu gibi bırak. M ≥ 5 ve Mana ≥ 6 bandı için daha çok veri gerek.** Bu yalnız öneridir; canlı koda dokunulmadı.',
    '',
    '- **M ≥ 4 satırı tutuyor.** Sabit iklim oranına karşı Brier becerisi 0,273 [0,206; 0,331]; yalnız önsele karşı 0,079 [0,040; 0,116], yani Bayes güncellemesi anlamlı katkı veriyor. Ortalamada hafif aşırı tahmin var: ortalama P %5,9, gözlenen %5,1 (551/10710). Aşırılık düşük olasılıklarda belirgin: %1–3 kutusunda tahmin %1,8, gözlenen %0,9 (25/2871); Mana 4–4,9 bandında %3,8 karşı %3,0. Orta ve yüksek kutular (%10 üstü) tutuyor.',
    '- **M ≥ 5 satırı zayıf ve aşırı güvenli yüksek uçta, ama örneklem çok küçük.** Yalnızca 79 pozitif, beceri 0,104 [−0,005; 0,175] (sıfırı içeriyor); güncel vs önsel 0,021 [−0,077; 0,087], fark yok. %50 üstü tahminlerde gözlenen oran düşük (%58,5 karşı %37,5, 6/16; %93,3 karşı %60,0, 6/10). Mana ≥ 6 bandında (18 kök dizi) %10–75 arası kutular gözlenenden yüksek (ör. %35,0 karşı %12,5, 3/24); tek tek anlamlılık yok.',
    '- **Önsel kaydırma testi önseli değiştirmeyi desteklemiyor.** Log skorunu en aza indiren da: M ≥ 4 için −0,1 [−0,2; 0,0], M ≥ 5 için −0,1 [−0,6; 0,1]. Nokta tahmin hızın yaklaşık %20 düşmesini ister (ortalama P %5,3, gözlenen %5,1), ama aralık sıfıra değiyor ya da sıfırı içeriyor.',
    '- **"Ana şoktan büyük ya da eşit" (1 sa, 7 gün):** güncel tahmin ortalaması %4,4, gözlenen %3,8 (59/1569). Brier becerisi USGS sabit %5’ine karşı 0,022 [−0,007; 0,048]: anlamlı değil. Bütün yayın anlarında %5’e karşı 0,137 [0,101; 0,184] görünür, ama sabit %5 zamanla sönmediği için bu karşılaştırma adil değildir; sabit iklim oranına karşı 0,043 [−0,002; 0,084].',
    '- **Bant kapsaması bu veriyle zayıf bir sınav.** %10–%90 bandı geniş olduğundan gözlenen oran neredeyse her kutuda bandın içinde kalıyor (tek istisna M ≥ 5, %75–100 kutusu); bandın darlığı hakkında bilgi vermez.',
    '- **Dizi tanımı sonucu etkiliyor.** (i) 27 Ekim 2025 Sındırgı (Mw 6,0, EMSC) ayrı dizi açmaz: Mw 6,1 olan 10 Ağustos dizisine 78 gün sonra katılır, dolayısıyla canlı kuralla bu olay için ayrı artçı olasılığı yayımlanmazdı (olay 10 Ağustos ana şokundan büyük olmadıkça, eşit dahil, ayrı dizi açılmaz). (ii) 20 Şubat 2023 Hatay (Mw 6,3) Kahramanmaraş dizisine bağlanmıyor; zincir tanımıyla Kahramanmaraş’ta 14 günlük pencerede M ≥ 4 gözlenen 6, mekânsal tanımla 40. Mekânsal tanımda M ≥ 4 gözlenen oran %10,9 (zincirde %5,1) olduğundan modelin "bağlı artçı" tahmini kümeleme zincirine bağlıdır; beceri iki tanımda da pozitif (0,10 [0,06; 0,14]).',
    '- **b geçişi tek dizide sıçrama üretti.** Canlı diziB kuralı (t ≥ 1 g, N ≥ 50) bu veride yalnız Kahramanmaraş’ın 5 satırında devreye girdi (b 0,69–0,84); P(≥ Mana) 1 günde %1,8 → %26,8 (6 saatte %1,8), gözlenen 0. Tek vakadır ve kanala giden M ≥ 4 / M ≥ 5 satırlarını değil Mana-eşit olasılığı etkiler; ancak büyük bir dizide b geçişi izlenmeli.',
    '- **Bu ölçümle ayırt edilemeyenler:** erken (1 sa–6 sa) yayın anlarında canlıdaki eksik kayıt, M ≥ 5 için yayın anı farkları (pozitif sayısı 8, 3, 3, 1, 1), Türkiye sınırına süzülmüş sonuç.',
    '',
    'Öneri özeti: (1) önsel (a = −2,42 ± 0,63) kalsın; (2) veri arttıkça (en az 2 yıl daha, mümkünse 2000+ Türkiye kutusu USGS katalogu ek olarak) M ≥ 5 / Mana ≥ 6 kalibrasyonunu yinele; (3) kümeleme zinciri kırıklarını (Hatay, Sındırgı Ekim) ayrı bir inceleme konusu olarak ele al.',
]



def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--bootstrap', type=int, default=2000)
    ap.add_argument('--yeniden-nn', action='store_true')
    ap.add_argument('--dogrula', action='store_true', help='gunluk.hesapla ile parametre eşitliğini denetler (yaklaşık 2 dk)')
    a = ap.parse_args(argv)
    t_bas = time.time()
    o, z, e, bo, m = katalog_yukle()
    print(f'{len(z)} olay; kümeleme...', flush=True)
    mc_kat, d_f, b, le0, eb, le = nn_hesapla(z, e, bo, m, a.yeniden_nn)
    bagli = le < le0
    print(f'mc {mc_kat} d_f {d_f} b {b} η0 {le0}; bağlı {int(bagli.sum())}', flush=True)
    dizi_id, diziler, soy = diziler_kur(z, m, eb, bagli)
    kok_fn = kok_bul(soy)
    hidx = hucre_endeksi(z, e, bo, m, diziler)
    mc_d = {d: mc_dizi(d, z, m, hidx, mc_kat) for d in diziler}
    bitis = float(z.max())
    print(f'{len(diziler)} dizi; tahminler...', flush=True)
    satirlar = tahmin_uret(z, m, dizi_id, diziler, soy, mc_kat, mc_d, bitis, kok_fn, konum=(e, bo))
    print(f'{len(satirlar)} tahmin satırı', flush=True)
    da_satirlar = {0.0: satirlar}
    for da in DA_IZGARA:
        if da != 0.0:
            da_satirlar[da] = tahmin_uret(z, m, dizi_id, diziler, soy, mc_kat, mc_d, bitis, kok_fn, da=da)
            print(f'da {da} tamam', flush=True)

    s = {'tarih': time.strftime('%Y-%m-%d'),
         'veri': {'n': len(z), 'bas': time.strftime('%Y-%m-%d', time.gmtime(z.min() / 1000)),
                  'bit': time.strftime('%Y-%m-%d', time.gmtime(z.max() / 1000)), 'n_dizi': len(diziler),
                  'n_kok': len({kok_fn(d) for d in diziler})},
         'kume': {'d_f': d_f, 'b': b, 'log_eta0': le0, 'mc': mc_kat, 'd_f_ham': float(korelasyon_boyutu(e, bo)),
                  'dogrulama': 'gunluk.hesapla denetimi bu koşuda yapılmadı.'},
         'genel': {}, 'alt_t': {}, 'alt_bant': {}, 'guvenilirlik': {}, 'kapsama': {}, 'sinirlar': SINIRLAR}
    for h in HEDEFLER:
        s['genel'][h] = tablo_satiri(satirlar, h, b=a.bootstrap)
        s['alt_t'][h] = {ad: tablo_satiri([r for r in satirlar if r['t'] == ad], h, b=a.bootstrap)
                         for _, ad in T_LISTE if any(r['t'] == ad for r in satirlar)}
        s['alt_bant'][h] = {ad: tablo_satiri([r for r in satirlar if r['bant'] == ad], h, b=a.bootstrap)
                            for ad, _, _ in BANTLAR if any(r['bant'] == ad for r in satirlar)}
        s['guvenilirlik'][h] = {'gunc': guvenilirlik(satirlar, h, 'gunc'), 'onsel': guvenilirlik(satirlar, h, 'onsel')}
        s['kapsama'][h] = kapsama(satirlar, h)
    s['guvenilirlik_bant'] = {h: {ad: guvenilirlik([r for r in satirlar if r['bant'] == ad], h, 'gunc') for ad, _, _ in BANTLAR
                                  if any(r['bant'] == ad for r in satirlar)} for h in ('M4', 'M5')}
    mek = [{**r, 'y': r['y_mekan']} for r in satirlar]
    s['mekan'] = {h: tablo_satiri(mek, h, b=a.bootstrap) for h in HEDEFLER}
    s['kaydirma_sirasi'] = [('M4', 'M4', None), ('M5', 'M5', None), ('M4_4', 'M4', '4–4,9'), ('M4_5', 'M4', '5–5,9'), ('M4_6', 'M4', '≥ 6')]
    s['kaydirma'] = {ad: kaydirma_analizi(da_satirlar, h, bant, b=a.bootstrap) for ad, h, bant in s['kaydirma_sirasi']}
    mcs = np.array(list(mc_d.values()))
    s['mc_ozet'] = {'min': float(mcs.min()), 'medyan': float(np.median(mcs)), 'max': float(mcs.max()),
                    'katalog_payi': float((mcs <= mc_kat + 1e-9).mean())}
    s['usgs'] = {'t1sa': usgs_tabani([r for r in satirlar if r['t'] == '1 sa'], b=a.bootstrap),
                 'hepsi': usgs_tabani(satirlar, b=a.bootstrap)}
    s['ozel'] = {}
    tz = lambda x: time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(x / 1000))
    for ad in OZEL:
        i = ozel_olay_bul(z, e, bo, m, ad)
        if i is None:
            s['ozel'][ad] = None
            continue
        if dizi_id[i] == i:
            d = i
            s['ozel'][ad] = {'zaman': tz(z[d]), 'mana': diziler[d]['mw'], 'enlem': float(e[d]), 'boylam': float(bo[d]), 'mc': mc_d[d],
                             'kok_mana': diziler[kok_fn(d)]['mw'], 'satirlar': [r for r in satirlar if r['dizi'] == d]}
            continue
        dz = int(dizi_id[i])
        dh, soy_h = varsayimsal_dizi(z, m, eb, bagli, i)
        sat_h = tahmin_uret(z, m, dizi_id, dh, soy_h, mc_kat, {i: mc_d.get(i, mc_kat)}, bitis, lambda d: d, konum=(e, bo))
        s['ozel'][ad] = {'katildi': {'zaman': tz(z[i]), 'mw': float(m[i]), 'dizi_zaman': tz(diziler[dz]['t0']), 'dizi_mana': diziler[dz]['mw'],
                                     'gun': float((z[i] - diziler[dz]['t0']) / GUN_MS)},
                         'varsayim': {'zaman': tz(z[i]), 'mana': float(m[i]), 'enlem': float(e[i]), 'boylam': float(bo[i]), 'mc': mc_d.get(i, mc_kat),
                                      'kok_mana': diziler[kok_fn(dz)]['mw'], 'satirlar': sat_h}}
    if a.dogrula:
        from hesap import gunluk
        p_g, kume_g, _, oz = gunluk.hesapla('tr', o, None, bitis - gunluk.SAKLA_GUN * GUN_MS, bitis)
        tamam = p_g['d_f'] == d_f and p_g['b'] == b and p_g['log_eta0'] == le0 and oz['bagli'] == int(bagli.sum())
        s['kume']['dogrulama'] = (f'gunluk.hesapla(tr) ile aynı parametreleri verir: d_f {p_g["d_f"]}, b {p_g["b"]}, η0 {p_g["log_eta0"]}, '
                                  f'bağlı olay {oz["bagli"]}, patlatmadan ayıklanan {oz["patlatma"]["ayiklanan"]} ({"eşit" if tamam else "FARKLI"}).')
    s['sure_s'] = time.time() - t_bas
    os.makedirs(os.path.dirname(CIKTI_JSON), exist_ok=True)
    with open(CIKTI_JSON, 'w', encoding='utf-8') as f:
        json.dump({**s, 'satirlar': satirlar}, f, ensure_ascii=False, default=lambda x: None if x != x else float(x))
    with open(RAPOR, 'w', encoding='utf-8') as f:
        f.write(rapor_yaz(s))
    print(f'bitti {s["sure_s"]:.0f} sn -> {CIKTI_JSON}')


if __name__ == '__main__':
    sys.exit(main())
