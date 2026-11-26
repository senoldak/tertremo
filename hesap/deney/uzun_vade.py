# Deney uzun_vade (gölge, canlı hesaba girmez): uzun vadeli oran modeli ve büyük deprem olasılığı.
#
# Gerekçe: docs/literatur-taramasi-4-2026-11-26.md §6 — Helmstetter, Kagan, Jackson 2007 (uyarlanır çekirdekli
# düzleştirilmiş sismisite); Werner ve ark. 2011 BSSA, doi 10.1785/0120090340 (uyarlanır çekirdek + tapered GR +
# negatif binom); Bayona ve ark. 2023 Seismic Record, doi 10.1785/0320230006 (sonuç düzleştirme ayarına duyarlı);
# Savran ve ark. 2022 pyCSEP.
#
# A) Uzamsal oran modeli geri-testi. Veri: USGS M ≥ 4,5, Türkiye kutusu (etas.KUTU), 2000-01-01 → 2026-10-25.
#    (dunya.csv.gz kutunun DIŞINI içerir — gunluk.katalogu 'tr' kutusunu EMSC'ye ayırıyor; bu yüzden kutu içi USGS
#    kaydı USGS FDSN'den indirilip hesap/.onbellek/deney/usgs-tr-2000.csv.gz'ye önbelleklenir.)
#    Eğitim 2000–2015, deneme 2016-01-01 → son, hedef bağımsız Mw ≥ 4,95; 0,5° ızgara; her model aynı toplam orana
#    ölçeklenir (eğitimdeki bağımsız M ≥ 4,95 sayısı/yıl × deneme süresi) ve aynı su seviyesi uygulanır.
# B) Tapered GR (Kagan 2002) ve kesilmemiş GR: Kart 19'un uzun katalogu (olasilik.uzun_katalog_yukle, Gardner–Knopoff,
#    tamlık 1964 Mw ≥ 6 / 1918 Mw ≥ 7), iki tamlık penceresi üstünde binli (0,1) olabilirlik; 10 yılda Mw ≥ 7 olasılığı.
import argparse
import json
import math
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np
from scipy import optimize, stats

from hesap import dogrulama as dg
from hesap import etas, kume, olasilik
from hesap import katalog as kat
from hesap.hucre import EPS, b_aki_utsu, kutula

UTC = timezone.utc
YIL_MS = 365.25 * 24 * 3600 * 1000
ONBELLEK = os.path.join(os.path.dirname(__file__), '..', '.onbellek')
DENEY = os.path.join(ONBELLEK, 'deney')
USGS_TR = os.path.join(DENEY, 'usgs-tr-2000.csv.gz')
CIKTI = os.path.join(DENEY, 'uzun_vade.json')

BAS = datetime(2000, 1, 1, tzinfo=UTC)
CV_BIT = datetime(2010, 1, 1, tzinfo=UTC)        # çapraz doğrulama: 2000–2009 → 2010–2015
EGITIM_BIT = datetime(2016, 1, 1, tzinfo=UTC)    # eğitim 2000–2015, deneme 2016–
SON = datetime(2026, 10, 26, tzinfo=UTC)         # önbellek 2026-10-25 sonuna kadar
MC = 4.5                                         # kaynak katalog eşiği (USGS M ≥ 4,5)
HEDEF = 4.95                                     # hedef eşik: kutulu Mw ≥ 5,0
SU = dg.SU
ALT = 5                                          # hücre başına ALT×ALT alt hücre (0,1° ≈ 11 km): çekirdek integrali için
SIGMALAR = (10, 15, 20, 30, 40, 50, 75, 100, 150)   # km; 11 km'den küçük bant alt hücre örneklemesiyle çözülmez
K_LISTE = (1, 2, 3, 4, 5, 6, 8, 10, 15, 20, 30)
DMIN_LISTE = (10, 15, 20, 30)                    # km; Helmstetter en küçük bant (katalog konum hatası ≥ 10 km)
KM_DERECE = 111.195


def ms(dt):
    return dt.timestamp() * 1000


# ---------- veri ----------

def indir(yol=USGS_TR):
    """Kutu içi USGS M ≥ 4,5 (yıllık parçalar; katalog._parcali ≤ 2 istek/sn kuralına uyar)."""
    k = etas.KUTU
    temel = {'minmagnitude': 4.5, 'format': 'geojson', 'orderby': 'time-asc', 'minlatitude': k['minlat'],
             'maxlatitude': k['maxlat'], 'minlongitude': k['minlon'], 'maxlongitude': k['maxlon']}
    olaylar = []
    for y in range(BAS.year, SON.year + 1):
        bas = datetime(y, 1, 1, tzinfo=UTC)
        bit = min(datetime(y + 1, 1, 1, tzinfo=UTC), SON)
        olaylar += kat._parcali(kat.USGS_URL, temel, kat.usgs_ayristir, bas, bit)
    kat.kaydet(yol, olaylar)
    return olaylar


def veri_yukle(yol=USGS_TR):
    olaylar = kat.yukle(yol) or indir(yol)
    olaylar = sorted(olaylar, key=lambda o: o['zaman_ms'])
    return {'z': np.array([o['zaman_ms'] for o in olaylar]), 'e': np.array([o['enlem'] for o in olaylar]),
            'bo': np.array([o['boylam'] for o in olaylar]), 'm': np.array([o['mw'] for o in olaylar]),
            'tur': np.array([o['tur'] for o in olaylar])}


# ---------- kümelenme ayırma ----------
# Seçim: en yakın komşu (Zaliapin & Ben-Zion). Gerekçe: canlı hesap (gunluk.py, etas.kumele) aynı yöntemi kullanıyor,
# eşik veriden (iki Gauss karışımı) geliyor ve ebeveyn yalnız geçmişte aranıyor (nedensel). Eşik, d_f ve b yalnız
# eğitim (2000–2015) olaylarından kurulur. Duyarlılık: Gardner–Knopoff (olasilik.gk_ayikla; Kart 19'un uzun
# katalogda kullandığı) — sabit pencere, nedensel değil; eğitim ve deneme sınırında ayrı geçiş yapılır.

def maske_nn(v, sinir_ms):
    egitim = v['z'] < sinir_ms
    d_f = kume.korelasyon_boyutu(v['e'][egitim], v['bo'][egitim])
    if not (etas.D_F_BANT[0] <= d_f <= etas.D_F_BANT[1]):
        d_f = etas.D_F_VARSAYILAN
    b0, _ = b_aki_utsu(v['m'][egitim], MC)
    _, le = kume.en_yakin_komsu(v['z'], v['e'], v['bo'], v['m'], d_f, b0, 'tr')
    eta0 = kume.esik(le[egitim])
    bag = np.ones(v['z'].size, bool) if not math.isfinite(eta0) else ~(le < eta0)
    return bag, {'yontem': 'en-yakin-komsu', 'd_f': float(d_f), 'b0': float(b0), 'log_eta0': float(eta0)}


def maske_gk(v, sinir_ms):
    """Eğitim kısmı yalnız eğitim olaylarıyla, deneme kısmı bütün katalogla ayıklanır (ileri bilgi sızmasın)."""
    egitim = v['z'] < sinir_ms
    tum = olasilik.gk_ayikla(v['z'], v['e'], v['bo'], v['m'])
    bag = tum.copy()
    bag[egitim] = olasilik.gk_ayikla(v['z'][egitim], v['e'][egitim], v['bo'][egitim], v['m'][egitim])
    return bag, {'yontem': 'gardner-knopoff'}


def hedef_hucre(v, maske, m_esik, bas_ms, bit_ms, yil=False):
    """Hedef olayların hücre indeksleri (kutu dışı atılır); yil=True ise (hücreler, takvim yılları)."""
    s = maske & (v['m'] >= m_esik - 1e-9) & (v['z'] >= bas_ms) & (v['z'] < bit_ms)
    h = dg.hucre(v['e'][s], v['bo'][s])
    if yil:
        y = np.floor(v['z'][s] / YIL_MS + 1970).astype(int)
        return h[h >= 0], y[h >= 0]
    return h[h >= 0]


# ---------- uzamsal çekirdekler ----------

def mesafe_matrisi(e1, b1, e2, b2):
    return kume.mesafe_km(np.asarray(e1)[:, None], np.asarray(b1)[:, None], np.asarray(e2)[None, :], np.asarray(b2)[None, :])


def alt_izgara():
    """Her 0,5° hücrenin ALT×ALT alt hücre merkezleri: (enlem, boylam, hücre indeksi, km² alan ağırlığı)."""
    ne, nb = dg.izgara()
    boy = dg.HUCRE / ALT
    k = etas.KUTU
    enl = k['minlat'] + (np.arange(ne * ALT) + 0.5) * boy
    boyl = k['minlon'] + (np.arange(nb * ALT) + 0.5) * boy
    ee, bb = np.meshgrid(enl, boyl, indexing='ij')
    idx = (np.arange(ne * ALT) // ALT)[:, None] * nb + (np.arange(nb * ALT) // ALT)[None, :]
    alan = np.cos(np.radians(ee)) * (boy * KM_DERECE) ** 2
    return ee.ravel(), bb.ravel(), idx.ravel(), alan.ravel()


class Cekirdekler:
    """Girdi olaylarından hücre ağırlıkları (toplam 1). Çekirdek yoğunluğu alt hücrelerde hesaplanır, hücre başına
    toplanır (alan ağırlıklı), kutu içinde yeniden normalleştirilir (kutu dışına taşan kütle atılır)."""

    def __init__(self, e, bo):
        self.n = len(e)
        self.se, self.sb, self.idx, self.alan = alt_izgara()
        self.ncell = int(self.idx.max()) + 1
        self.d2 = mesafe_matrisi(e, bo, self.se, self.sb) ** 2
        ee = mesafe_matrisi(e, bo, e, bo)
        self.komsu = np.sort(ee, axis=1)[:, 1:]   # kendisi hariç artan uzaklıklar

    def _hucre(self, yogunluk):
        h = np.bincount(self.idx, weights=yogunluk * self.alan, minlength=self.ncell)
        return h / h.sum()

    def sabit(self, sigma):
        s2 = float(sigma) ** 2
        return self._hucre((np.exp(-self.d2 / (2 * s2)) / (2 * math.pi * s2)).sum(axis=0))

    def bant(self, k, dmin):
        k = min(int(k), self.komsu.shape[1])
        return np.maximum(self.komsu[:, k - 1], float(dmin))

    def uyarlanir(self, k, dmin, sekil='guc'):
        """Helmstetter 2007: bant = k'ıncı komşu uzaklığı (≥ dmin). 'guc': K = d/(2π)·(r²+d²)^-1,5 (Helmstetter,
        Werner çekirdeği, kuyruğu ağır); 'gauss': aynı bant, Gauss çekirdek."""
        d = self.bant(k, dmin)[:, None]
        if sekil == 'guc':
            return self._hucre((d / (2 * math.pi) * (self.d2 + d ** 2) ** -1.5).sum(axis=0))
        return self._hucre((np.exp(-self.d2 / (2 * d ** 2)) / (2 * math.pi * d ** 2)).sum(axis=0))


def olay_ll(w, hucreler):
    """Olay başına ortalama log hücre olasılığı (su seviyeli, toplam 1 ağırlık). Aynı toplam orana ölçeklenmiş
    modellerde iki modelin farkı = pyCSEP T-testi bilgi kazancı (deprem başına, nat)."""
    return float(np.mean(np.log(dg.su_seviyesi(w)[hucreler]))) if len(hucreler) else math.nan


def en_iyi(tablo):
    return max(tablo, key=lambda a: tablo[a])


def cv_sec(v, maske, bit_ms, hizli=False):
    """2000–2009 girdi → 2010–2015 hedef (bağımsız M ≥ 4,95). Dönüş: seçilen parametreler + bütün tablo.
    İkincil: hedef M ≥ 4,5 ile seçim (daha çok olay, daha az gürültü; duyarlılık için)."""
    cv_bit = ms(CV_BIT)
    giris = maske & (v['m'] >= MC - 1e-9) & (v['z'] < cv_bit)
    hedefler = {'495': hedef_hucre(v, maske, HEDEF, cv_bit, bit_ms), '45': hedef_hucre(v, maske, MC, cv_bit, bit_ms)}
    ck = Cekirdekler(v['e'][giris], v['bo'][giris])
    sigmalar = SIGMALAR[::3] if hizli else SIGMALAR
    ks, dm = (K_LISTE[::4], DMIN_LISTE[::2]) if hizli else (K_LISTE, DMIN_LISTE)
    sonuc = {'girdi_olay': int(giris.sum()), 'hedef_olay': {a: int(len(h)) for a, h in hedefler.items()}}
    for ad, h in hedefler.items():
        gauss = {s: olay_ll(ck.sabit(s), h) for s in sigmalar}
        guc = {(k, d): olay_ll(ck.uyarlanir(k, d, 'guc'), h) for k in ks for d in dm}
        gau = {(k, d): olay_ll(ck.uyarlanir(k, d, 'gauss'), h) for k in ks for d in dm}
        sonuc[ad] = {'sigma_km': en_iyi(gauss), 'uyarlanir_guc': en_iyi(guc), 'uyarlanir_gauss': en_iyi(gau),
                     'tablo_gauss': {str(s): x for s, x in gauss.items()},
                     'tablo_guc': {f'{k}/{d}': x for (k, d), x in guc.items()},
                     'tablo_gauss_uyarlanir': {f'{k}/{d}': x for (k, d), x in gau.items()}}
    return sonuc


# ---------- sayı dağılımı: Poisson ve negatif binom ----------

def nb_alfa(yillik):
    """Yıllık sayılar için NB (ortalama μ = örnek ortalaması, var = μ + α μ²) α'sının en çok olabilirlik kestirimi.
    Eşit/az yayılımda α = 0 (Poisson). Werner ve ark. 2011: bağımsız olaylarda bile Poisson yayılımı küçümser."""
    y = np.asarray(yillik, float)
    mu = float(y.mean())
    if mu <= 0 or y.var(ddof=1) <= mu:
        return 0.0

    def eksi_ll(la):
        r = 1.0 / math.exp(la)
        return -stats.nbinom.logpmf(y, r, r / (r + mu)).sum()

    s = optimize.minimize_scalar(eksi_ll, bounds=(math.log(1e-4), math.log(10.0)), method='bounded')
    return float(math.exp(s.x))


def nb_dagilim(ortalama, alfa, sure_yil=1.0):
    """sure_yil yıllık toplam sayının dağılımı: yıllar bağımsız NB(μ, α) ise toplam NB(boyut = sure/α, ortalama μ·sure).
    α = 0 → Poisson."""
    m = ortalama * sure_yil
    if alfa <= 0:
        return stats.poisson(m)
    r = sure_yil / alfa
    return stats.nbinom(r, r / (r + m))


def n_kuantil(dagilim, gozlenen):
    """pyCSEP N-testi niceliklerinin aynısı: δ1 = P(N ≥ gözlenen), δ2 = P(N ≤ gözlenen); iki yönlü %5'te red."""
    d1, d2 = float(dagilim.sf(gozlenen - 1)), float(dagilim.cdf(gozlenen))
    return {'d1': d1, 'd2': d2, 'reddedildi': bool(d1 < 0.025 or d2 < 0.025)}


def poisson_n(beklenen, gozlenen):
    """csep.core.poisson_evaluations._number_test_ndarray (ndarray düzeyi)."""
    from csep.core.poisson_evaluations import _number_test_ndarray
    d1, d2 = _number_test_ndarray(beklenen, gozlenen)
    return {'d1': float(d1), 'd2': float(d2), 'reddedildi': bool(d1 < 0.025 or d2 < 0.025)}


def sayi_testleri(v, maske, bas_ms, egitim_bit_ms, son_ms, n_boot=1000, tohum=0):
    """Eğitim yıllık sayılarından NB α; deneme toplam ve yıllık N-testleri (Poisson ve NB)."""
    def yillik(a, b):
        s = maske & (v['m'] >= HEDEF - 1e-9) & (v['z'] >= a) & (v['z'] < b)
        yillar = np.floor((v['z'][s] / YIL_MS) + 1970).astype(int)
        y0, y1 = datetime.fromtimestamp(a / 1000, UTC).year, datetime.fromtimestamp((b - 1) / 1000, UTC).year
        return np.array([(yillar == y).sum() for y in range(y0, y1 + 1)])

    egit = yillik(bas_ms, egitim_bit_ms)
    den = yillik(egitim_bit_ms, son_ms)
    mu = float(egit.mean())
    alfa = nb_alfa(egit)
    rng = np.random.default_rng(tohum)
    alfa_b = np.array([nb_alfa(rng.choice(egit, egit.size)) for _ in range(n_boot)])
    sure = (son_ms - egitim_bit_ms) / YIL_MS
    toplam_gozlenen = int(den.sum())
    tam_yillar = np.concatenate([egit, den[:-1]])     # 2000–2025 (2026 kısmi, dışarıda)
    alfa_tum = nb_alfa(tam_yillar)                    # geriye dönük: ileriye dönük değil, yalnız duyarlılık
    yil_sure = [1.0] * (len(den) - 1) + [sure - (len(den) - 1)]    # son yıl kısmi (2026: 1 Ocak–25 Ekim)
    yillik_sonuc = []
    for n, t in zip(den, yil_sure):
        yillik_sonuc.append({'gozlenen': int(n), 'sure_yil': round(t, 3),
                             'poisson': n_kuantil(nb_dagilim(mu, 0.0, t), int(n)),
                             'nb': n_kuantil(nb_dagilim(mu, alfa, t), int(n))})
    return {
        'egitim_yillik': egit.tolist(), 'egitim_ortalama': mu, 'egitim_varyans': float(egit.var(ddof=1)),
        'yayilim_orani': float(egit.var(ddof=1) / mu) if mu > 0 else None,
        'alfa': alfa, 'alfa_boot_5_95': [float(np.percentile(alfa_b, 5)), float(np.percentile(alfa_b, 95))],
        'alfa_sifir_orani': float(np.mean(alfa_b == 0)),
        'deneme_yillik': den.tolist(), 'deneme_sure_yil': sure,
        'deneme_yayilim_orani': float(den.var(ddof=1) / den.mean()) if den.mean() > 0 else None,
        'beklenen_toplam': mu * sure, 'gozlenen_toplam': toplam_gozlenen,
        'toplam_poisson': poisson_n(mu * sure, toplam_gozlenen),
        'toplam_nb': n_kuantil(nb_dagilim(mu, alfa, sure), toplam_gozlenen),
        'alfa_tum_donem_geriye_donuk': alfa_tum, 'toplam_nb_tum_donem_alfa': n_kuantil(nb_dagilim(mu, alfa_tum, sure), toplam_gozlenen),
        'yillik': yillik_sonuc,
        'yillik_red': {'poisson': int(sum(y['poisson']['reddedildi'] for y in yillik_sonuc)),
                       'nb': int(sum(y['nb']['reddedildi'] for y in yillik_sonuc)), 'yil': len(yillik_sonuc)},
    }


# ---------- değerlendirme ----------

def gozlenen_say(h, ncell):
    return np.bincount(h, minlength=ncell).astype(float)


def blok_bootstrap(fark, yillar, n_boot=2000, tohum=0):
    """Yıl blokları üstünde bootstrap: olay başına log oran farkının ortalaması (bilgi kazancı), %2,5–97,5.
    Aynı dizinin (artçı bulutu, çift kırılma) olayları bağımsız değil; T-testi bunu saymaz, blok bootstrap yılı birim alır."""
    fark, yillar = np.asarray(fark, float), np.asarray(yillar)
    ys = np.unique(yillar)
    top = np.array([fark[yillar == y].sum() for y in ys])
    say = np.array([(yillar == y).sum() for y in ys])
    rng = np.random.default_rng(tohum)
    idx = rng.integers(0, ys.size, (n_boot, ys.size))
    ig = top[idx].sum(axis=1) / np.maximum(say[idx].sum(axis=1), 1)
    return {'alt': float(np.percentile(ig, 2.5)), 'ust': float(np.percentile(ig, 97.5)), 'blok': int(ys.size)}


def degerlendir(oranlar, h, n_sim, tohum=0, taban='bugun', yillar=None):
    """oranlar: {ad: hücre beklenen sayısı}; h: deneme olaylarının hücre indeksleri. pyCSEP ndarray düzeyi:
    L-testi (Poisson sayı dahil), S-testi (gözlenen sayıya koşullu), çiftli T-testi (taban modele göre)."""
    from csep.core.poisson_evaluations import _poisson_likelihood_test
    obs = gozlenen_say(h, next(iter(oranlar.values())).size)
    n = int(obs.sum())
    sonuc = {}
    for ad, r in oranlar.items():
        qs_l, ll_l, _ = _poisson_likelihood_test(r, obs, num_simulations=n_sim, seed=tohum, use_observed_counts=False,
                                                 normalize_likelihood=False)
        qs_s, ll_s, _ = _poisson_likelihood_test(r, obs, num_simulations=n_sim, seed=tohum, use_observed_counts=True,
                                                 normalize_likelihood=True)
        sonuc[ad] = {'L_kuantil': float(qs_l), 'L_ll': float(ll_l), 'S_kuantil': float(qs_s), 'S_ll': float(ll_s),
                     'olay_ll': olay_ll(r / r.sum(), h), 'beklenen': float(r.sum())}
        if ad != taban:
            sonuc[ad]['T_bugune_gore'] = dg.t_testi(r[h], oranlar[taban][h], n, r.sum(), oranlar[taban].sum())
            if yillar is not None:
                sonuc[ad]['blok_bootstrap_bugune_gore'] = blok_bootstrap(np.log(r[h]) - np.log(oranlar[taban][h]), yillar)
    return sonuc


def yontem_calistir(v, maske, bilgi, n_sim, n_boot, hizli=False, tohum=0):
    z, e, bo, m = v['z'], v['e'], v['bo'], v['m']
    bas, eg, son = ms(BAS), ms(EGITIM_BIT), ms(SON)
    sure_eg, sure_de = (eg - bas) / YIL_MS, (son - eg) / YIL_MS
    zaman = time.monotonic()
    cv = cv_sec(v, maske, eg, hizli)
    print(f"  {bilgi['yontem']}: çapraz doğrulama bitti ({time.monotonic() - zaman:.0f} s)", flush=True)
    sec = cv['495']
    giris = maske & (m >= MC - 1e-9) & (z < eg)
    ck = Cekirdekler(e[giris], bo[giris])
    n_egitim_495 = int((maske & (m >= HEDEF - 1e-9) & (z < eg)).sum())
    beklenen = n_egitim_495 / sure_eg * sure_de
    b_egitim, _ = b_aki_utsu(m[maske & (z < eg)], MC)
    ncell = ck.ncell
    w = {'duzgun': np.full(ncell, 1.0 / ncell)}
    p = dg.poisson_uzay(z, e, bo, m, maske, MC, b_egitim, bas, eg, hedef=HEDEF)
    w['bugun'] = p['hiz4'] / p['hiz4'].sum()
    w['gauss_sabit'] = ck.sabit(sec['sigma_km'])
    k, d = sec['uyarlanir_guc']
    w['uyarlanir_guc'] = ck.uyarlanir(k, d, 'guc')
    k2, d2 = sec['uyarlanir_gauss']
    w['uyarlanir_gauss'] = ck.uyarlanir(k2, d2, 'gauss')
    # ikincil: hedef M ≥ 4,5 ile seçilen parametreler
    s45 = cv['45']
    w['gauss_sabit_cv45'] = ck.sabit(s45['sigma_km'])
    k3, d3 = s45['uyarlanir_guc']
    w['uyarlanir_guc_cv45'] = ck.uyarlanir(k3, d3, 'guc')
    oranlar = {ad: dg.su_seviyesi(beklenen * x) for ad, x in w.items()}
    h, yh = hedef_hucre(v, maske, HEDEF, eg, son, yil=True)
    deg = degerlendir(oranlar, h, n_sim, tohum, yillar=yh)
    deg_duzgun = dg.t_testi(oranlar['bugun'][h], oranlar['duzgun'][h], len(h), oranlar['bugun'].sum(), oranlar['duzgun'].sum())
    # duyarlılık (seçimde kullanılmaz): bütün parametre ızgarasında deneme dönemi olay başına log olabilirlik
    duy = {'gauss': {str(s): olay_ll(ck.sabit(s), h) for s in (SIGMALAR[::3] if hizli else SIGMALAR)},
           'uyarlanir_guc': {f'{kk}/{dd}': olay_ll(ck.uyarlanir(kk, dd, 'guc'), h)
                             for kk in (K_LISTE[::4] if hizli else K_LISTE) for dd in (DMIN_LISTE[::2] if hizli else DMIN_LISTE)},
           'bugun': olay_ll(w['bugun'], h), 'duzgun': olay_ll(w['duzgun'], h)}
    bant = ck.bant(k, d)
    sayi = sayi_testleri(v, maske, bas, eg, son, n_boot=n_boot, tohum=tohum)
    tam = {'ayirma': bilgi, 'egitim_girdi_olay': int(giris.sum()), 'egitim_495': n_egitim_495,
           'deneme_495': int(len(h)), 'deneme_495_tum_olaylar': int(((m >= HEDEF - 1e-9) & (z >= eg) & (z < son)).sum()),
           'egitim_495_tum_olaylar': int(((m >= HEDEF - 1e-9) & (z < eg)).sum()),
           'b_egitim_bagimsiz': float(b_egitim), 'beklenen_deneme': float(beklenen), 'yil_egitim': sure_eg,
           'yil_deneme': sure_de, 'secim': {'sigma_km': sec['sigma_km'], 'uyarlanir_guc_k_dmin': list(sec['uyarlanir_guc']),
                                            'uyarlanir_gauss_k_dmin': list(sec['uyarlanir_gauss']),
                                            'cv45_sigma_km': s45['sigma_km'], 'cv45_uyarlanir_guc_k_dmin': list(s45['uyarlanir_guc'])},
           'bant_km': {'medyan': float(np.median(bant)), 'p10': float(np.percentile(bant, 10)),
                       'p90': float(np.percentile(bant, 90))},
           'cv': cv, 'degerlendirme': deg, 'bugun_duzgune_gore_T': deg_duzgun, 'duyarlilik_deneme': duy,
           'sayi': sayi, 'sure_s': round(time.monotonic() - zaman, 1)}
    return tam


def tamlik(v):
    """Tamlık kontrolü: dönem başına b(Mc) platosu, M ≥ 4,95 / M ≥ 4,5 oranı ve büyüklük türü payı."""
    donemler = [(2000, 2008), (2008, 2016), (2016, 2027)]
    z, m = v['z'], v['m']
    yil = np.floor(z / YIL_MS + 1970).astype(int)
    sonuc = {}
    for a, c in donemler:
        s = (yil >= a) & (yil < c)
        mm = m[s]
        b_mc = {}
        for mc in (4.5, 4.6, 4.7, 4.8, 4.95):
            b_mc[str(mc)] = float(b_aki_utsu(mm, mc)[0])
        n45, n495 = int((mm >= MC - 1e-9).sum()), int((mm >= HEDEF - 1e-9).sum())
        sonuc[f'{a}-{c - 1}'] = {'n_4.5': n45, 'n_4.95': n495, 'oran': n495 / n45 if n45 else None, 'b_mc': b_mc,
                                'beklenen_oran_b1.1': 10 ** (-1.1 * 0.5),
                                'mb_payi': float((v['tur'][s] == 'mb').mean()), 'Mw_payi': float((v['tur'][s] == 'Mw').mean())}
    sonuc['yillik_4.5'] = {str(y): int((yil == y).sum()) for y in range(2000, 2027)}
    sonuc['yillik_4.95'] = {str(y): int(((yil == y) & (m >= HEDEF - 1e-9)).sum()) for y in range(2000, 2027)}
    return sonuc


# ---------- B: tapered GR ----------
# Survivor (moment, Kagan 2002): S(M)/S(Mt) = (Mt/M)^β · exp((Mt − M)/Mc), M ≥ Mt; M = 10^(1,5 Mw + 9,1) → x = M/Mt,
# τ = Mt/Mc. τ = 0 kesilmemiş GR (β = 2/3 b). Mw 0,1'lik kutularda; Mt = 5,95 kutu alt kenarı (Mw ≥ 6 kutusu).
# Kayıt iki tamlık penceresinde: 1964→ Mw ≥ 6 (kenar 5,95), 1918–1963 Mw ≥ 7 (kenar 6,95). Poisson süreç olabilirliği;
# λ (kenar 5,95 üstü olay/yıl) profil olarak atılır: λ̂ = Σw / Σ T_pencere·S(kenar).
MT = 5.95
KENAR7 = 6.95
MC_IZGARA = np.round(np.arange(6.0, 12.0001, 0.05), 2)     # köşe büyüklüğü ızgarası; üst uç ≈ kesilmemiş
BETA_SINIR = (0.05, 4.0)


def log_surv(mw_kenar, beta, tau):
    x = 10.0 ** (1.5 * (np.asarray(mw_kenar, float) - MT))
    return -beta * np.log(x) - tau * (x - 1.0)


def tau_of(mc_mag):
    return 0.0 if mc_mag is None or not math.isfinite(mc_mag) else 10.0 ** (1.5 * (MT - mc_mag))


def uzun_veri(son_ms=None):
    """Kart 19'daki seçim: Gardner–Knopoff, Türkiye bölgeleri (+30 km); Mw ≥ 6 → 1964–, Mw ≥ 7 → 1918–1963.
    Dönüş: (kutulu büyüklükler, pencere etiketi 0/1, pencere listesi [(yıl, alt kenar)])."""
    son_ms = ms(SON) if son_ms is None else son_ms
    uk = olasilik.uzun_katalog_yukle()
    tut = olasilik.gk_ayikla(uk['z'], uk['e'], uk['bo'], uk['m'])
    adlar = olasilik.BolgeAtayici().ata(uk['e'], uk['bo'])
    ic = np.array([a is not None for a in adlar], bool)
    z, m = uk['z'], uk['m']
    b64, b18 = ms(datetime(1964, 1, 1, tzinfo=UTC)), ms(datetime(1918, 1, 1, tzinfo=UTC))
    s1 = tut & ic & (m >= 6.0 - EPS) & (z >= b64) & (z < son_ms)
    s2 = tut & ic & (m >= 7.0 - EPS) & (z >= b18) & (z < b64)
    mag = np.concatenate([kutula(m[s1]), kutula(m[s2])])
    pen = np.concatenate([np.zeros(int(s1.sum()), int), np.ones(int(s2.sum()), int)])
    yillar = [(son_ms - b64) / YIL_MS, (b64 - b18) / YIL_MS]
    return mag, pen, [(yillar[0], MT), (yillar[1], KENAR7)]


def _surv_pencere(pencereler, beta, tau):
    return float(sum(t * math.exp(float(log_surv(k, beta, tau))) for t, k in pencereler))


def profil_ll(beta, tau, mag, pen, w, pencereler):
    """λ profillenmiş log olabilirlik."""
    lo, hi = log_surv(mag - 0.05, beta, tau), log_surv(mag + 0.05, beta, tau)
    p = np.exp(lo) - np.exp(hi)
    if np.any(p <= 0):
        return -np.inf
    sw = float(w.sum())
    if sw <= 0:
        return -np.inf
    lam = sw / _surv_pencere(pencereler, beta, tau)
    return float((w * np.log(p)).sum() + sw * math.log(lam) - sw)


def beta_uydur(tau, mag, pen, w, pencereler, beta_sabit=None):
    """Verilen τ için en iyi β (ya da sabit β) → (β, ll)."""
    if beta_sabit is not None:
        return float(beta_sabit), profil_ll(beta_sabit, tau, mag, pen, w, pencereler)
    r = optimize.minimize_scalar(lambda bt: -profil_ll(bt, tau, mag, pen, w, pencereler), bounds=BETA_SINIR, method='bounded',
                                 options={'xatol': 1e-5})
    return float(r.x), float(-r.fun)


def lambda_hat(beta, tau, w, pencereler):
    return float(w.sum()) / _surv_pencere(pencereler, beta, tau)


def olasilik10(beta, tau, w, pencereler, yil=10.0, kenar=KENAR7):
    lam7 = lambda_hat(beta, tau, w, pencereler) * math.exp(float(log_surv(kenar, beta, tau)))
    return 1.0 - math.exp(-lam7 * yil)


def uydur_tum(mag, pen, w, pencereler, izgara=MC_IZGARA, beta_sabit=None):
    """Kesilmemiş GR ve tapered GR: {'gr': {...}, 'tapered': {...}, 'profil': {mc: ll}}."""
    b0, ll0 = beta_uydur(0.0, mag, pen, w, pencereler, beta_sabit)
    profil, betalar = {}, {}
    for mc in izgara:
        bt, ll = beta_uydur(tau_of(float(mc)), mag, pen, w, pencereler, beta_sabit)
        profil[float(mc)], betalar[float(mc)] = ll, bt
    mc_en = max(profil, key=profil.get)
    return {'gr': {'beta': b0, 'b': 1.5 * b0, 'll': ll0, 'k': 1 if beta_sabit is not None else 2},
            'tapered': {'beta': betalar[mc_en], 'mc_mag': mc_en, 'll': profil[mc_en], 'k': 2 if beta_sabit is not None else 3},
            'profil': profil, 'betalar': betalar}


def b_to_beta(b):
    return 2.0 * b / 3.0


def aralik_profil(profil, esik):
    """İki sütunlu profilden {mc: ll}: ll ≥ ll_max − esik/2 olan köşe büyüklükleri aralığı; (alt, ust, ust_acik)."""
    mx = max(profil.values())
    ok = [mc for mc, ll in profil.items() if 2 * (mx - ll) <= esik]
    return float(min(ok)), float(max(ok)), bool(max(ok) >= max(profil))


def uzun_vade_b(n_boot=1000, tohum=0, izgara_boot=None, beta_sabit=None):
    mag, pen, pencereler = uzun_veri()
    w1 = np.ones(mag.size)
    ana = uydur_tum(mag, pen, w1, pencereler, beta_sabit=beta_sabit)
    gr, tp = ana['gr'], ana['tapered']
    tau_t = tau_of(tp['mc_mag'])
    p_gr = olasilik10(gr['beta'], 0.0, w1, pencereler)
    p_tp = olasilik10(tp['beta'], tau_t, w1, pencereler)
    n7_toplam = int(((mag >= 7.0 - EPS) & (pen == 0)).sum() + (pen == 1).sum())
    yil7 = pencereler[0][0] + pencereler[1][0]
    p_say = 1 - math.exp(-n7_toplam / yil7 * 10)
    # 1964 sonrası pencerede doğrudan sayım (durağan olmayan hız duyarlılığı)
    n7_64 = int(((mag >= 7.0 - EPS) & (pen == 0)).sum())
    p_say64 = 1 - math.exp(-n7_64 / pencereler[0][0] * 10)
    izg = MC_IZGARA[::2] if izgara_boot is None else izgara_boot
    rng = np.random.default_rng(tohum)
    pg, pt, ps, ps64, mcb, bg, bt_, kenarda = [], [], [], [], [], [], [], 0
    for _ in range(n_boot):
        w = rng.poisson(1.0, mag.size).astype(float)
        if w.sum() < 3:
            continue
        a = uydur_tum(mag, pen, w, pencereler, izgara=izg, beta_sabit=beta_sabit)
        pg.append(olasilik10(a['gr']['beta'], 0.0, w, pencereler))
        pt.append(olasilik10(a['tapered']['beta'], tau_of(a['tapered']['mc_mag']), w, pencereler))
        mcb.append(a['tapered']['mc_mag'])
        bg.append(a['gr']['beta'])
        bt_.append(a['tapered']['beta'])
        w7 = (w * ((pen == 1) | (mag >= 7.0 - EPS))).sum()
        ps.append(1 - math.exp(-w7 / yil7 * 10))
        w64 = (w * ((pen == 0) & (mag >= 7.0 - EPS))).sum()
        ps64.append(1 - math.exp(-w64 / pencereler[0][0] * 10))
        kenarda += a['tapered']['mc_mag'] >= izg[-1] - 1e-9

    def ar(x):
        x = np.asarray(x)
        return {'p5': float(np.percentile(x, 5)), 'p10': float(np.percentile(x, 10)), 'p50': float(np.percentile(x, 50)),
                'p90': float(np.percentile(x, 90)), 'p95': float(np.percentile(x, 95))}

    aic_gr = 2 * gr['k'] - 2 * gr['ll']
    aic_tp = 2 * tp['k'] - 2 * tp['ll']
    lrt = 2 * (tp['ll'] - gr['ll'])
    mc_alt95, mc_ust95, ust_acik95 = aralik_profil(ana['profil'], 3.84)
    mc_alt90, mc_ust90, ust_acik90 = aralik_profil(ana['profil'], 2.71)
    ll_profil = {f'{k:.2f}': v for k, v in ana['profil'].items() if abs(k * 2 - round(k * 2)) < 1e-9}
    return {
        'beta_sabit': beta_sabit, 'veri': {'n_toplam': int(mag.size), 'n_1964_Mw6': int((pen == 0).sum()), 'n_1918_1963_Mw7': int((pen == 1).sum()),
                                           'n7_toplam_1918': n7_toplam, 'n7_1964': n7_64, 'yil_1964': pencereler[0][0],
                                           'yil_1918_1963': pencereler[1][0], 'yil7_toplam': yil7,
                                           'hiz7_1964_sonrasi': n7_64 / pencereler[0][0],
                                           'hiz7_1918_1963': int((pen == 1).sum()) / pencereler[1][0]},
        'gr': {**{k: v for k, v in gr.items()}, 'aic': aic_gr, 'p10_M7': p_gr, 'lambda_6': lambda_hat(gr['beta'], 0.0, w1, pencereler)},
        'tapered': {**{k: v for k, v in tp.items()}, 'aic': aic_tp, 'p10_M7': p_tp, 'tau': tau_t,
                    'lambda_6': lambda_hat(tp['beta'], tau_t, w1, pencereler),
                    'mc_moment_Nm': 10 ** (1.5 * tp['mc_mag'] + 9.1)},
        'delta_aic_gr_eksi_tapered': aic_gr - aic_tp, 'lrt': lrt,
        'lrt_p_karisim': float(0.5 * stats.chi2.sf(lrt, 1)) if lrt > 0 else 1.0,
        'mc_profil_95': {'alt': mc_alt95, 'ust': mc_ust95, 'ust_sinirda': ust_acik95},
        'mc_profil_90': {'alt': mc_alt90, 'ust': mc_ust90, 'ust_sinirda': ust_acik90},
        'mc_profil_ll_yarim_adim': ll_profil,
        'sayim_p10_M7': p_say, 'sayim_1964_p10_M7': p_say64,
        'bootstrap': {'cekim': len(pg), 'izgara_adim': float(izg[1] - izg[0]),
                      'gr_p10': ar(pg), 'tapered_p10': ar(pt), 'sayim_p10': ar(ps), 'sayim_1964_p10': ar(ps64),
                      'mc_mag': ar(mcb), 'mc_ust_sinirda_orani': kenarda / max(len(pg), 1),
                      'beta_gr': ar(bg), 'beta_tapered': ar(bt_)},
    }


# ---------- çalıştırma ----------

def _json(o):
    if isinstance(o, dict):
        return {str(k): _json(x) for k, x in o.items()}
    if isinstance(o, (list, tuple)):
        return [_json(x) for x in o]
    if isinstance(o, (np.floating, float)):
        return None if not math.isfinite(float(o)) else float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return o


def ana(argv=None):
    for akis in (sys.stdout, sys.stderr):
        if hasattr(akis, 'reconfigure'):
            akis.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description='uzun_vade gölge deneyi')
    ap.add_argument('--sim', type=int, default=10000, help='L/S testi simülasyon sayısı')
    ap.add_argument('--boot', type=int, default=1000)
    ap.add_argument('--hizli', action='store_true', help='indirgeme: seyrek parametre ızgarası, az çekim')
    ap.add_argument('--tohum', type=int, default=0)
    ap.add_argument('--cikti', default=CIKTI)
    a = ap.parse_args(argv)
    t = time.monotonic()
    v = veri_yukle()
    print(f"veri: {v['z'].size} olay M ≥ 4,5 kutu içi", flush=True)
    sonuc = {'surum': 'uzun_vade-1', 'hizli': a.hizli, 'veri': {'olay': int(v['z'].size)}}
    eg = ms(EGITIM_BIT)
    sonuc['tamlik'] = tamlik(v)
    for ad, f in (('nn', maske_nn), ('gk', maske_gk)):
        maske, bilgi = f(v, eg)
        bilgi['bagimsiz_orani'] = float(maske.mean())
        print(f"{ad}: bağımsız oran {maske.mean():.3f}", flush=True)
        sonuc[f'A_{ad}'] = yontem_calistir(v, maske, bilgi, a.sim if not a.hizli else 500, a.boot if not a.hizli else 50,
                                           a.hizli, a.tohum)
    print('B: tapered GR', flush=True)
    sonuc['B'] = uzun_vade_b(n_boot=a.boot if not a.hizli else 30, tohum=a.tohum)
    b_usgs = sonuc['A_nn']['b_egitim_bagimsiz']
    sonuc['B_beta_sabit'] = uzun_vade_b(n_boot=a.boot if not a.hizli else 30, tohum=a.tohum, beta_sabit=b_to_beta(b_usgs))
    sonuc['B_beta_sabit']['b_kullanilan'] = b_usgs
    sonuc['sure_s'] = round(time.monotonic() - t, 1)
    os.makedirs(os.path.dirname(a.cikti), exist_ok=True)
    with open(a.cikti, 'w', encoding='utf-8') as f:
        json.dump(_json(sonuc), f, ensure_ascii=False, indent=1)
    print(f"bitti {sonuc['sure_s']} s → {a.cikti}")
    return 0


if __name__ == '__main__':
    sys.exit(ana())
