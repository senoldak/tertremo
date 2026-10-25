# Haftalık deprem olasılığı (Kart 20): uzay–zaman ETAS.
#
# Uygulama: L. Mizrahi `etas` paketi, https://github.com/lmizrahi/etas, sürüm 3.0.0,
#   kommit 097f08b69a4f06f9c38d14799dedfbd4543144e3 (hesap/requirements-etas.txt'te sabit).
#   Lisans: MIT, Copyright (c) 2024 ETH Zurich, Leila Mizrahi.
#   Yöntem: Mizrahi, Nandan & Wiemer 2021, SRL, doi:10.1785/0220200231 (EM tersine çözüm) ve
#   JGR 126, doi:10.1029/2021JB022379.
# - Uyum: paketin EM tersine çözümü (ETASParameterCalculation) EMSC Türkiye kutusunda (33,5–44,5 K, 23,5–47 D),
#   M ≥ Mc; Mc = eğitim döneminde (2018–2021) b kararlılığı (MBS) ile seçilir; b sabit = kümelenmesi ayrılmış
#   (hesap/kume en yakın komşu, gece hesabıyla aynı işlem) olayların Aki–Utsu b'si. Haftalık (pazar) ve kutuda
#   M ≥ 5,5'ten sonra yeniden uyum; her gece yalnız simülasyon.
# - Simülasyon: paketin çekirdek fonksiyonları (expected_aftershocks, upper_gamma_ext, haversine, polygon_surface)
#   ve paketin simulate_catalog_continuation'ıyla aynı kurallar (arka plan yerleri P_background ağırlıklı + 0,1°
#   Gauss, Omori–Utsu üstel kesmeli zaman, kuvvet yasası uzaklık, G-R büyüklük), ama 10.000 katalog birlikte
#   vektörleştirilmiş: paketin döngüsü katalog başına ~0,1–0,5 s sürüyor (10.000 katalog > 6 dk bütçesi).
#   Eşdeğerlik testi: hesap/tests/test_etas.py::test_simulasyon_paketin_surdurmesiyle_ayni.
#   Pencereye düşen çocuk sayısı Poisson(pencere içi beklenen) ile çekilir (paket bütün çocukları çekip pencere
#   dışını atar; dağılım aynı).
# - etas.simulation `seismostats`ı (AGPL-3.0) yalnız bir dönüş tipi için içe aktarıyor; o işlevi kullanmadığımız
#   için kurulu değilse yerine boş bir modül konur (AGPL bağımlılığı yok).
# - Akla yatkınlık: α_etkin = a − ρ·γ > 2,5, p = 1 + ω < 0,9 ya da dallanma oranı ≥ 1 → son iyi uyum; o da yoksa
#   yalnız Poisson ("bu hafta model güncellenemedi").
# - Poisson tabanı (Kart 19 ile aynı λ): bağımsız (kümelenmesi ayrılmış) olaylardan λ(Mc)/yıl,
#   λ(M) = λ(Mc)·10^(−b(M−Mc)), P(7 gün) = 1 − exp(−λ·7/365,25).
import argparse
import gzip
import json
import math
import os
import sys
import time
import types
from datetime import datetime, timedelta, timezone

import numpy as np

from hesap import katalog as kat
from hesap import kartveri
from hesap.hucre import b_aki_utsu, kutula, mc_maxc
from hesap.kume import en_yakin_komsu, esik, korelasyon_boyutu

UTC = timezone.utc
GUN_MS = 86_400_000
YIL_GUN = 365.25
DM = 0.1
KUTU = {'minlat': 33.5, 'maxlat': 44.5, 'minlon': 23.5, 'maxlon': 47.0}  # katalog.EMSC_KUTU
YARDIMCI_BAS = datetime(2018, 1, 1, tzinfo=UTC)   # kaynak olarak kullanılır, hedef değil
BIRINCIL_BAS = datetime(2019, 1, 1, tzinfo=UTC)   # hedef olaylar bu tarihten sonra
COPPERSMITH = 100
M_MAX = 8.0          # simülasyonda en büyük büyüklük kutusu (paket varsayılanı sınırsız)
# Mc: b-değeri kararlılığı (MBS; Cao & Gao 2002, Woessner & Wiemer 2005) YALNIZ eğitim döneminde (2018–2021)
# seçilir ve bütün zincirde (uyum, simülasyon, b, Poisson tabanı, doğrulama) aynen kullanılır. EMSC kutusunda ML ~4'te,
# mb/Mw üstte kesiliyor: birleşik b, Mc 3,5'te 0,83, Mc ≥ 4'te ≈ 1,1 (raporun tanı tablosu). Bu yüzden MAXC/KS
# (2,2/2,5) kullanılmaz. Eğitim verisi yoksa MC_YEDEK.
MC_ADAYLAR = np.round(np.arange(2.0, 5.01, 0.1), 1)
MBS_GENISLIK = 0.5   # b ortalaması Mc … Mc + 0,5 aralığında (6 kutu)
MBS_EN_AZ = 100      # Mc + 0,5 kesiminde b için en az olay (üst uçtaki küçük örnek gürültüsü)
MBS_K = 2.0          # ölçüt toleransı: 2·σ_b (~%95)
MC_YEDEK = 4.0
EGITIM_BAS = datetime(2018, 1, 1, tzinfo=UTC)
EGITIM_BIT = datetime(2022, 1, 1, tzinfo=UTC)
B_ARALIK = (0.6, 1.5)
B_VARSAYILAN = 1.0
D_F_BANT = (1.0, 2.0)
D_F_VARSAYILAN = 1.6
SIMULASYON = 10_000
SIMULASYON_EN_AZ = 5_000
GUN = 7.0
ARKA_SIGMA = 0.1     # paketin gaussian_scale varsayılanı (derece)
ESIKLER = (5.0, 6.0)
YENIDEN_UYUM_M = 5.5
ALFA_UST = 2.5
P_ALT = 0.9
# MODEL_SURUM: Mc / b / uyum kuralı ya da simülasyon kuralı değişirse MUTLAKA artırılır. Doğrulama sonucu ve gizli
# kayıt haftaları yalnız aynı sürüm için geçerlidir (kapi()).
MODEL_SURUM = 'etas-2'
GIZLI_EN_AZ = 8
GIZLI_TUT = 104
THETA_0 = {'log10_mu': -7.5, 'log10_k0': -2.5, 'a': 1.8, 'log10_c': -2.5, 'omega': -0.02, 'log10_tau': 3.5,
           'log10_d': -0.85, 'gamma': 1.3, 'rho': 0.66}
PARAMETRELER = ('log10_mu', 'log10_k0', 'a', 'log10_c', 'omega', 'log10_tau', 'log10_d', 'gamma', 'rho')
BOLGE_DOSYA = os.path.join(os.path.dirname(__file__), '..', 'data', 'bolgeler.json')
IL_DOSYA = os.path.join(os.path.dirname(__file__), '..', 'data', 'harita', 'iller.json')


# ---------- paket ----------

_PAKET = {}


def paket():
    """etas modülleri (tembel içe aktarma). seismostats yoksa boş modül konur (bkz. başlık)."""
    if not _PAKET:
        try:
            import seismostats  # noqa: F401
        except ImportError:
            import pandas as pd
            sahte = types.ModuleType('seismostats')
            sahte.ForecastCatalog = pd.DataFrame
            sys.modules['seismostats'] = sahte
        import logging
        import warnings
        logging.getLogger('etas').setLevel(logging.WARNING)
        # Paketin pandas 3 / shapely 2.2 kullanım uyarıları (inplace=, shapely.ops.transform): sabitlenmiş
        # sürümlerde davranış aynı; gece günlüğünü ve test çıktısını boğmasın.
        warnings.filterwarnings('ignore', category=DeprecationWarning, module=r'etas(\.|$)')
        warnings.filterwarnings('ignore', category=FutureWarning, module=r'etas(\.|$)')
        from etas import inversion, mc_b_est, simulation
        _PAKET.update(inversion=inversion, mc_b_est=mc_b_est, simulation=simulation)
    return types.SimpleNamespace(**_PAKET)


def kutu_koseleri(kutu=KUTU):
    """Paketin şekil biçimi: [[enlem, boylam], ...]."""
    return [[kutu['minlat'], kutu['minlon']], [kutu['maxlat'], kutu['minlon']],
            [kutu['maxlat'], kutu['maxlon']], [kutu['minlat'], kutu['maxlon']]]


def kutuda(enlem, boylam, kutu=KUTU):
    enlem, boylam = np.asarray(enlem), np.asarray(boylam)
    return ((enlem >= kutu['minlat']) & (enlem <= kutu['maxlat'])
            & (boylam >= kutu['minlon']) & (boylam <= kutu['maxlon']))


def _ms(dt):
    return dt.timestamp() * 1000


def _naif(ms):
    """Paket zamanları saat dilimsiz (UTC) pandas zamanı bekler."""
    return datetime.fromtimestamp(ms / 1000, tz=UTC).replace(tzinfo=None)


def _diziler(olaylar):
    olaylar = sorted(olaylar, key=lambda o: o['zaman_ms'])
    z = np.array([o['zaman_ms'] for o in olaylar], float)
    e = np.array([o['enlem'] for o in olaylar], float)
    b = np.array([o['boylam'] for o in olaylar], float)
    m = np.array([o['mw'] for o in olaylar], float)
    return olaylar, z, e, b, m


# ---------- Mc, b, kümelenme ----------

def mc_mbs(m, adaylar=MC_ADAYLAR, dm=DM, genislik=MBS_GENISLIK, en_az=MBS_EN_AZ, k=MBS_K):
    """MBS (Cao & Gao 2002; Woessner & Wiemer 2005), kalıcı plato biçimi: her aday için ölçüt
    |b_ort(Mc … Mc+genişlik) − b(Mc)| ≤ k·σ_b(Mc) (Shi & Bolt σ, k = 2). Dönüş: kendisi ve üstündeki bütün adaylar
    (Mc + genişlik'te ≥ en_az olay olan) ölçütü sağlayan en küçük Mc; yoksa nan. İlk sağlayan aday yerine kalıcı
    plato: ML/mb karışımı alt magnitüdlerde sahte bir b ≈ 0,8 platosu üretiyor (eğitim verisinde 2,5–3,2'de ölçüt
    sağlanıyor, 3,3–3,9'da bozuluyor). Saf G-R'de (n 5.000–20.000) Mc'yi 2,0–2,2 bulur (test)."""
    km = kutula(m)
    adim = int(round(genislik / dm))
    sonuc = []
    for mc in adaylar:
        if (km >= mc + genislik - 1e-9).sum() < en_az:
            break
        b0, s0 = b_aki_utsu(km, mc, dm)
        bler = [b_aki_utsu(km, round(mc + i * dm, 6), dm)[0] for i in range(adim + 1)]
        sonuc.append((float(round(mc, 1)), abs(float(np.mean(bler)) - b0) <= k * s0))
    secim = math.nan
    for mc, ok in reversed(sonuc):
        if not ok:
            break
        secim = mc
    return secim


def mc_egitim(z, m, bas=EGITIM_BAS, bit=EGITIM_BIT):
    """Eğitim döneminin (2018–2021) MBS Mc'si; bulunamazsa MC_YEDEK. Dönüş: (Mc, ham MBS)."""
    s = (z >= _ms(bas)) & (z < _ms(bit))
    ham = mc_mbs(m[s]) if s.any() else math.nan
    return (ham if math.isfinite(ham) else MC_YEDEK), ham


def kumele(z, e, b, m):
    # DONDURULDU: ETAS zinciri ön kayıtla sabit (docs/etas-on-kayit.md); b0 için mc_maxc BİLEREK korunuyor,
    # gece hesabının MBS tabanlı b'siyle farkı bilinen bir sapmadır.
    """Gece hesabıyla aynı en yakın komşu kümelemesi (gunluk.hesapla): bağımsız olay maskesi ve kullanılan d_f."""
    d_f = korelasyon_boyutu(e, b)
    if not (D_F_BANT[0] <= d_f <= D_F_BANT[1]):
        d_f = D_F_VARSAYILAN
    b0, _ = b_aki_utsu(m, mc_maxc(m))
    if not math.isfinite(b0):
        b0 = B_VARSAYILAN
    _, log_eta = en_yakin_komsu(z, e, b, m, d_f, b0, 'tr')
    eta0 = esik(log_eta)
    if not math.isfinite(eta0):
        return np.ones(z.size, bool), d_f
    return ~(log_eta < eta0), d_f


def bolgesel_b(m, bagimsiz, mc):
    """Kümelenmesi ayrılmış olayların Aki–Utsu b'si; aralık dışıysa B_VARSAYILAN. (b, ham_b)."""
    ham, _ = b_aki_utsu(m[bagimsiz], mc)
    if not math.isfinite(ham) or not (B_ARALIK[0] <= ham <= B_ARALIK[1]):
        return B_VARSAYILAN, ham
    return float(ham), float(ham)


# ---------- uyum ----------

class HizliAmac:
    """Paketin M adımı amaç fonksiyonu (inversion.neg_log_likelihood) ile birebir aynı değer, artı türev.

    Paket L-BFGS-B'yi sayısal türevle çağırıyor: her M adımında ~270 değerlendirme, her biri bütün kaynak–hedef
    çiftleri üzerinde pandas işlemi (Türkiye kutusu Mc 3,0'da 7,6 M çift → ~5 dk/yineleme). Burada çift terimi numpy
    ile ve çözümsel türevle hesaplanır; yalnız Γ(−ω, ·)'nın ω türevi ve (ω, τ, c, ρ)'ya bağlı skaler terim merkezi
    farkla. Aynı sınırlar ve tol ile L-BFGS-B. Eşdeğerlik testi: tests/test_etas.py::test_hizli_amac_paketle_ayni
    (değer 1e-9 göreli, türev sayısal türevle); sentetik katalogda iki yolun uyumu 3 basamağa kadar aynı."""

    def __init__(self, pij, kaynak, mc_min):
        inv = paket().inversion
        self.inv = inv
        self.mc_min = mc_min
        w = (pij['Pij'] * pij['zeta_plus_1']).to_numpy(float)
        dm = (pij['source_magnitude'] - mc_min).to_numpy(float)
        self.w, self.dm = w, dm
        self.r2 = pij['spatial_distance_squared'].to_numpy(float)
        self.t = pij['time_distance'].to_numpy(float)
        self.udm, self.idm = np.unique(np.round(dm, 9), return_inverse=True)
        self.W, self.Wm, self.Wt = float(w.sum()), float((w * dm).sum()), float((w * self.t).sum())
        self.km = kaynak['source_magnitude'].to_numpy(float)
        self.ks = kaynak['pos_source_to_start_time_distance'].to_numpy(float)
        self.ke = kaynak['source_to_end_time_distance'].to_numpy(float)
        self.kl = kaynak['l_hat'].to_numpy(float)

    def skaler(self, om, ltau, lc, rho):
        tau, c = 10 ** ltau, 10 ** lc
        return om * math.log(tau) - math.log(self.inv.upper_gamma_ext(-om, c / tau)) + math.log(rho)

    def deger(self, th):
        return self.deger_turev(th, turev=False)

    def deger_turev(self, th, turev=True):
        lk0, a, lc, om, ltau, ld, gam, rho = (float(x) for x in th)
        c, tau, d = 10 ** lc, 10 ** ltau, 10 ** ld
        w = self.w
        dp = (d * np.exp(gam * self.udm))[self.idm]
        s = self.r2 + dp
        tc = self.t + c
        wlns = float(w @ np.log(s))
        wlntc = float(w @ np.log(tc))
        C = self.skaler(om, ltau, lc, rho)
        dag = (self.W * (C - math.log(math.pi)) + rho * self.W * math.log(d) + rho * gam * self.Wm
               - (1 + rho) * wlns - (1 + om) * wlntc - (self.Wt + self.W * c) / tau)
        # Kaynak terimi (paketin expected_aftershocks'u ile aynı G): G = k0·e^(aΔm)·π·(d·e^(γΔm))^(−ρ)/ρ · T,
        # T = e^(c/τ)·τ^(−ω)·[Γ(−ω, (s+c)/τ) − Γ(−ω, (e+c)/τ)]; A = Σ [−lnΓ(l+1) − G + l·ln G].
        kdm = self.km - self.mc_min
        D = self._D(om, c, tau)
        G = (10 ** lk0 * np.exp(a * kdm) * math.pi * np.power(d * np.exp(gam * kdm), -rho) / rho
             * math.exp(c / tau) * tau ** (-om) * D)
        A = float(self.inv.ll_aftershock_term(self.kl, G).sum())
        f = -(A + dag)
        if not turev:
            return f
        oran = w * dp / s
        wds = float(oran.sum())
        wdsm = float(oran @ self.dm)
        winv = float(w @ (1 / tc))
        ln10 = math.log(10)

        def dC(i, h=1e-6):
            x = [om, ltau, lc, rho]
            x1, x2 = list(x), list(x)
            x1[i] += h
            x2[i] -= h
            return (self.skaler(*x1) - self.skaler(*x2)) / (2 * h)

        g_dag = np.array([
            0.0, 0.0,
            self.W * dC(2) + c * ln10 * (-(1 + om) * winv - self.W / tau),
            self.W * dC(0) - wlntc,
            self.W * dC(1) + ln10 * (self.Wt + self.W * c) / tau,
            ln10 * (rho * self.W - (1 + rho) * wds),
            rho * self.Wm - (1 + rho) * wdsm,
            self.W / rho + self.W * math.log(d) + gam * self.Wm - wlns,
        ])
        # ∂A/∂x = Σ (l − G)·∂lnG/∂x. ∂Γ(a, x)/∂x = −x^(a−1)·e^(−x) → c ve τ türevi çözümsel; ω merkezi farkla.
        fark = self.kl - G
        sf, sfd = float(fark.sum()), float(fark @ kdm)
        xs, xe = (self.ks + c) / tau, (self.ke + c) / tau
        with np.errstate(divide='ignore', invalid='ignore', over='ignore'):
            ps = np.power(xs, -om) * np.exp(-xs)
            pe = np.power(xe, -om) * np.exp(-xe)
            dlnT_dc = 1 / tau + np.nan_to_num((pe / xe - ps / xs) / (tau * D))
            dlnT_dtau = -c / tau ** 2 - om / tau + np.nan_to_num((ps - pe) / (tau * D))
            h = 1e-6
            dlnT_dom = -math.log(tau) + np.nan_to_num(
                (np.log(self._D(om + h, c, tau)) - np.log(self._D(om - h, c, tau))) / (2 * h))
        g_A = np.array([sf * ln10, sfd, c * ln10 * float(fark @ dlnT_dc), float(fark @ dlnT_dom),
                        tau * ln10 * float(fark @ dlnT_dtau), -rho * ln10 * sf, -rho * sfd,
                        -(math.log(d) + 1 / rho) * sf - gam * sfd])
        return f, -(g_A + g_dag)

    def _D(self, om, c, tau):
        ug = self.inv.upper_gamma_ext
        return np.asarray(ug(-om, (self.ks + c) / tau) - ug(-om, (self.ke + c) / tau), float)


_HIZLI = {}


def hizli_hesap_sinifi():
    """Paketin ETASParameterCalculation'ı; yalnız optimize_parameters HizliAmac + çözümsel türevle (aynı sınırlar,
    aynı tol). Serbest üretkenlik / arka plan terimi / kısıt varsa paketin kendi yolu kullanılır."""
    if 'sinif' not in _HIZLI:
        from scipy.optimize import minimize
        inv = paket().inversion

        class HizliHesap(inv.ETASParameterCalculation):
            def optimize_parameters(self, theta_0, ranges=inv.RANGES):
                if self.free_productivity or self.bg_term is not None or self.constraints:
                    return super().optimize_parameters(theta_0, ranges)
                mu_hat = self.n_hat / (self.area * self.timewindow_length)
                amac = HizliAmac(self.pij, self.source_events, self.m_ref - self.delta_m / 2)
                x0 = np.clip(np.asarray(theta_0[2:], float), [r[0] for r in ranges[2:]], [r[1] for r in ranges[2:]])
                res = minimize(amac.deger_turev, x0=x0, bounds=ranges[2:], jac=True, tol=1e-12)
                return np.array([np.log10(mu_hat), None, *res.x])

        _HIZLI['sinif'] = HizliHesap
    return _HIZLI['sinif']


def uyum(olaylar, bitis_ms, mc, b, kutu=KUTU, yardimci_bas=YARDIMCI_BAS, birincil_bas=BIRINCIL_BAS,
         theta_0=None, carpan=COPPERSMITH, hizli=True):
    """Paketin EM tersine çözümü. Dönüş: parametreler, b, beta, mc, alan, arka plan noktaları, ölçütler, süre.
    hizli=False: paketin kendi M adımı (sayısal türev; yavaş, eşdeğerlik denetimi için)."""
    import pandas as pd
    p = paket()
    sinif = hizli_hesap_sinifi() if hizli else p.inversion.ETASParameterCalculation
    t0 = time.monotonic()
    secim = [o for o in olaylar if o['zaman_ms'] < bitis_ms and kutula(o['mw']) >= mc - 1e-9
             and o['zaman_ms'] >= _ms(yardimci_bas)]
    df = pd.DataFrame({'latitude': [o['enlem'] for o in secim], 'longitude': [o['boylam'] for o in secim],
                       'time': pd.to_datetime([o['zaman_ms'] for o in secim], unit='ms'),
                       'magnitude': [o['mw'] for o in secim]},
                      index=pd.Index([o['id'] for o in secim], name='id'))
    beta = float(b * math.log(10))
    hesap = sinif({
        'catalog': df, 'auxiliary_start': _naif(_ms(yardimci_bas)), 'timewindow_start': _naif(_ms(birincil_bas)),
        'timewindow_end': _naif(bitis_ms), 'mc': float(mc), 'delta_m': DM, 'coppersmith_multiplier': carpan,
        'shape_coords': kutu_koseleri(kutu), 'beta': beta, 'theta_0': dict(theta_0 or THETA_0),
    })
    hesap.prepare()
    t_hazir = time.monotonic() - t0
    th = hesap.invert()
    hedef = hesap.target_events
    zeta = hedef['zeta_plus_1'] / hedef['zeta_plus_1'].max()
    arka = np.column_stack([hedef['latitude'].to_numpy(float), hedef['longitude'].to_numpy(float),
                            (hedef['P_background'] * zeta).to_numpy(float)])
    parametreler = {k: float(th[k]) for k in PARAMETRELER}
    sonuc = {
        'zaman': int(bitis_ms), 'mc': float(mc), 'b': float(b), 'beta': beta, 'alan_km2': float(hesap.area),
        'parametreler': parametreler, 'n': int(len(hedef)), 'n_kaynak': int(len(hesap.source_events)),
        'cift': int(len(hesap.distances)), 'yineleme': int(hesap.i or 0),
        'arka': np.round(arka, 4).tolist(), 'kutu': dict(kutu),
        'sure_s': round(time.monotonic() - t0, 1), 'hazirlik_s': round(t_hazir, 1), 'surum': MODEL_SURUM,
    }
    sonuc.update(olcutler(parametreler, beta))
    return sonuc


def olcutler(parametreler, beta):
    """α_etkin = a − ρ·γ (toplam artçı sayısının büyüklük üsteli), p = 1 + ω, dallanma oranı (paket)."""
    p = paket()
    alfa = parametreler['a'] - parametreler['rho'] * parametreler['gamma']
    dizi = p.inversion.parameter_dict2array({**parametreler, 'log10_iota': None})
    try:
        dal = float(p.inversion.branching_ratio(dizi, beta))
    except (AssertionError, FloatingPointError, ValueError):
        dal = math.inf
    return {'alfa': float(alfa), 'p': float(1 + parametreler['omega']), 'dallanma': dal if math.isfinite(dal) else None}


def makul(u):
    """(bool, neden). Brif: α > 2,5, p < 0,9 ya da dallanma ≥ 1 → makul değil."""
    if u is None:
        return False, 'uyum yok'
    if not all(math.isfinite(v) for v in u['parametreler'].values()):
        return False, 'parametre sonlu değil'
    if u['alfa'] > ALFA_UST:
        return False, f"α {u['alfa']:.2f} > {ALFA_UST}"
    if u['p'] < P_ALT:
        return False, f"p {u['p']:.2f} < {P_ALT}"
    if u['dallanma'] is None or not u['dallanma'] < 1:
        return False, f"dallanma {u['dallanma']} ≥ 1"
    return True, ''


def uyum_sec(yeni, son_iyi):
    """(kullanılacak uyum ya da None, durum): 'yeni', 'eski' (son iyi uyum), 'poisson' (hiçbiri)."""
    if yeni is not None and makul(yeni)[0]:
        return yeni, 'yeni'
    if son_iyi is not None and makul(son_iyi)[0]:
        return son_iyi, 'eski'
    return None, 'poisson'


# ---------- simülasyon ----------

def _buyuklukler(rng, n, beta, mc_s, m_max=M_MAX):
    """Paketin simulate_magnitudes'iyle aynı formül (m_max + ΔM/2'de kesik G-R), rng ile."""
    ust = m_max + DM / 2
    norm = 1 - math.exp(-beta * (ust - mc_s))
    return mc_s - np.log(1 - norm * rng.uniform(size=n)) / beta


class Simulator:
    """Bir uyumdan, gözlenen kaynaklar verildiğinde [0, gun] gün penceresinde n katalog sürdürmesi."""

    def __init__(self, u, gun=GUN, m_max=M_MAX):
        p = paket()
        self.p = p
        th = u['parametreler']
        self.th = th
        self.beta = u['beta']
        self.mc_s = u['mc'] - DM / 2
        self.gun = gun
        self.m_max = m_max
        self.kutu = u.get('kutu', KUTU)
        self.alan = u['alan_km2']
        self.theta = [th['log10_k0'], th['a'], th['log10_c'], th['omega'], th['log10_tau'], th['log10_d'],
                      th['gamma'], th['rho']]
        self.c = 10 ** th['log10_c']
        self.tau = 10 ** th['log10_tau']
        self.d = 10 ** th['log10_d']
        arka = np.asarray(u['arka'], float).reshape(-1, 3)
        w = np.clip(arka[:, 2], 0, None)
        self.arka = arka[w > 0]
        self.arka_p = w[w > 0] / w[w > 0].sum() if (w > 0).any() else None
        self._tablo_D = 0.0

    def _G(self, gecikme):
        return self.p.inversion.upper_gamma_ext(-self.th['omega'], (np.asarray(gecikme, float) + self.c) / self.tau)

    def _tablo(self, D):
        if D > self._tablo_D:
            t = np.concatenate([[0.0], np.logspace(-8, math.log10(max(D, 1.0) * 1.001), 8000)])
            self._t, self._g = t, self._G(t)  # azalan
            self._tablo_D = t[-1]

    def beklenen(self, m, d1, d2):
        """Kaynak başına [d1, d2] gecikme aralığında beklenen çocuk sayısı (paketin expected_aftershocks'u)."""
        if np.size(m) == 0:
            return np.zeros(0)
        return self.p.inversion.expected_aftershocks([np.asarray(m, float), np.asarray(d1, float),
                                                       np.asarray(d2, float)], [self.theta, self.mc_s])

    def gecikme(self, rng, d1, d2):
        """[d1, d2] aralığında Omori–Utsu (üstel kesmeli) gecikme: ters CDF, logaritmik tablo üzerinde."""
        y1, y2 = self._G(d1), self._G(d2)
        y = y1 - rng.uniform(size=np.size(d1)) * (y1 - y2)
        t = np.interp(-y, -self._g, self._t)
        return np.clip(t, d1, d2)

    def yer(self, rng, enlem, boylam, m):
        """Paketin generate_aftershocks'undaki gibi: r = √(((1−u)^(−1/ρ) − 1)·d·e^(γ(m−mc))) km, açı tekdüze."""
        inv = self.p.inversion
        d_g = self.d * np.exp(self.th['gamma'] * (m - self.mc_s))
        r = np.sqrt((np.power(1 - rng.uniform(size=m.size), -1 / self.th['rho']) - 1) * d_g)
        aci = rng.uniform(0, 2 * math.pi, size=m.size)
        derece_boy = inv.haversine(np.radians(enlem), np.radians(enlem), 0.0, np.radians(1.0))
        derece_en = inv.haversine(np.radians(enlem - 0.5), np.radians(enlem + 0.5), 0.0, 0.0)
        return enlem + r * np.cos(aci) / derece_en, boylam + r * np.sin(aci) / derece_boy

    def arka_plan(self, rng, n):
        mu = 10 ** self.th['log10_mu']
        sayi = rng.poisson(mu * self.alan * self.gun, n)
        toplam = int(sayi.sum())
        kat_id = np.repeat(np.arange(n), sayi)
        la = np.empty(toplam)
        lo = np.empty(toplam)
        eksik = np.arange(toplam)
        while eksik.size:
            if self.arka_p is None:
                la[eksik] = rng.uniform(self.kutu['minlat'], self.kutu['maxlat'], eksik.size)
                lo[eksik] = rng.uniform(self.kutu['minlon'], self.kutu['maxlon'], eksik.size)
            else:
                i = rng.choice(self.arka_p.size, eksik.size, p=self.arka_p)
                la[eksik] = self.arka[i, 0] + rng.normal(0, ARKA_SIGMA, eksik.size)
                lo[eksik] = self.arka[i, 1] + rng.normal(0, ARKA_SIGMA, eksik.size)
            eksik = eksik[~kutuda(la[eksik], lo[eksik], self.kutu)]
        t = rng.uniform(0, self.gun, toplam)
        m = _buyuklukler(rng, toplam, self.beta, self.mc_s, self.m_max)
        return kat_id, t, la, lo, m

    def calistir(self, kaynak, n, rng, kayit_alt=3.95, en_cok_olay=50_000_000):
        """kaynak: {'t': gün (≤ 0, pencere başına göre), 'enlem', 'boylam', 'm'} (M ≥ Mc gözlenen olaylar).
        Dönüş: kayit_alt üstü bütün simüle olaylar {'kat', 't', 'enlem', 'boylam', 'm', 'eb_enlem', 'eb_boylam'}
        (ebeveyn yeri; arka plan olaylarında nan) ve 'toplam'."""
        kt = np.asarray(kaynak['t'], float)
        km = np.asarray(kaynak['m'], float)
        D = float(-kt.min()) + self.gun if kt.size else self.gun
        self._tablo(D)
        parcalar = []
        toplam = 0

        def kaydet(kat_id, t, la, lo, m, eb_la, eb_lo):
            s = m >= kayit_alt
            parcalar.append((kat_id[s], t[s], la[s], lo[s], m[s], eb_la[s], eb_lo[s]))

        # 0) arka plan
        ebeveyn = self.arka_plan(rng, n)
        bos = np.full(ebeveyn[0].size, np.nan)
        kaydet(*ebeveyn, bos, bos)
        toplam += ebeveyn[0].size
        # 1) gözlenen olayların pencereye düşen çocukları: toplam Poisson(Λ), kaynak λ_j ile orantılı
        lam = self.beklenen(km, -kt, self.gun - kt)
        L = float(lam.sum()) if lam.size else 0.0
        if L > 0:
            sayi = rng.poisson(L, n)
            tum = int(sayi.sum())
            kat_id = np.repeat(np.arange(n), sayi)
            j = rng.choice(lam.size, tum, p=lam / L)
            t = kt[j] + self.gecikme(rng, -kt[j], self.gun - kt[j])
            eb_la, eb_lo = np.asarray(kaynak['enlem'], float)[j], np.asarray(kaynak['boylam'], float)[j]
            la, lo = self.yer(rng, eb_la, eb_lo, km[j])
            m = _buyuklukler(rng, tum, self.beta, self.mc_s, self.m_max)
            kaydet(kat_id, t, la, lo, m, eb_la, eb_lo)
            toplam += tum
            ebeveyn = tuple(np.concatenate([a, b]) for a, b in zip(ebeveyn, (kat_id, t, la, lo, m)))
        # 2) kuşaklar
        while ebeveyn[0].size:
            kat_id, t, la, lo, m = ebeveyn
            lam = self.beklenen(m, np.zeros_like(t), self.gun - t)
            k = rng.poisson(np.clip(lam, 0, None))
            if not k.any():
                break
            i = np.repeat(np.arange(k.size), k)
            ct = t[i] + self.gecikme(rng, np.zeros(i.size), self.gun - t[i])
            cla, clo = self.yer(rng, la[i], lo[i], m[i])
            cm = _buyuklukler(rng, i.size, self.beta, self.mc_s, self.m_max)
            ebeveyn = (kat_id[i], ct, cla, clo, cm)
            kaydet(*ebeveyn, la[i], lo[i])
            toplam += i.size
            if toplam > en_cok_olay:
                raise RuntimeError(f'simülasyon patladı ({toplam} olay); dallanma oranını denetle')
        if parcalar:
            kat_id, t, la, lo, m, eb_la, eb_lo = (np.concatenate(x) for x in zip(*parcalar))
        else:
            kat_id, t, la, lo, m, eb_la, eb_lo = (np.zeros(0),) * 7
        return {'kat': kat_id.astype(np.int64), 't': t, 'enlem': la, 'boylam': lo, 'm': m, 'eb_enlem': eb_la,
                'eb_boylam': eb_lo, 'n': n, 'toplam': toplam}


def kaynaklar(olaylar, t0_ms, mc, kutu=KUTU, yardimci_bas=YARDIMCI_BAS):
    """t0'dan önceki kutu içi M ≥ Mc olaylar (yardımcı başlangıçtan beri), pencere başına göre gün."""
    s = [o for o in olaylar if _ms(yardimci_bas) <= o['zaman_ms'] < t0_ms and kutula(o['mw']) >= mc - 1e-9
         and kutuda(o['enlem'], o['boylam'], kutu)]
    return {'t': np.array([(o['zaman_ms'] - t0_ms) / GUN_MS for o in s]),
            'enlem': np.array([o['enlem'] for o in s]), 'boylam': np.array([o['boylam'] for o in s]),
            'm': np.array([float(kutula(o['mw'])) for o in s])}


# ---------- bölgeler ----------

class Bolgeler:
    """data/bolgeler.json + data/harita/iller.json. ata(enlem, boylam) → bölge adı ya da None
    (il sınırları içinde ya da en yakın bölgeye ≤ tampon_km; uzaklık cos 39° ölçekli düzlemde)."""

    KOS = math.cos(math.radians(39))

    def __init__(self, bolge_dosya=BOLGE_DOSYA, il_dosya=IL_DOSYA):
        import shapely
        from shapely.geometry import Polygon
        with open(bolge_dosya, encoding='utf-8') as f:
            tanim = json.load(f)
        with open(il_dosya, encoding='utf-8') as f:
            iller = {il['ad']: il for il in json.load(f)}
        self.shapely = shapely
        self.tampon = tanim['tampon_km'] / 111.195
        self.adlar = [b['ad'] for b in tanim['bolgeler']]
        self.sekiller = []
        for b in tanim['bolgeler']:
            halkalar = []
            for ad in b['iller']:
                for r in iller[ad]['r']:
                    xy = np.asarray(r, float).reshape(-1, 2)
                    halkalar.append(Polygon(np.column_stack([xy[:, 0] * self.KOS, xy[:, 1]])).buffer(0))
            self.sekiller.append(shapely.union_all(halkalar))

    def ata(self, enlem, boylam):
        enlem, boylam = np.atleast_1d(np.asarray(enlem, float)), np.atleast_1d(np.asarray(boylam, float))
        if enlem.size == 0:
            return np.array([], dtype=object)
        nok = self.shapely.points(boylam * self.KOS, enlem)
        uz = np.vstack([self.shapely.distance(s, nok) for s in self.sekiller])
        enk = uz.argmin(axis=0)
        sonuc = np.array([self.adlar[i] for i in enk], dtype=object)
        sonuc[uz.min(axis=0) > self.tampon] = None
        return sonuc


# ---------- olasılıklar ----------

def olasiliklar(sim, bolgeler, esikler=ESIKLER, kutu=KUTU):
    """Simülasyondan P(≥ 1 olay ≥ eşik) kutuda ve bölge bölge (katalog kesri)."""
    n = sim['n']
    ic = kutuda(sim['enlem'], sim['boylam'], kutu)
    sonuc = {'turkiye': {}, 'bolgeler': {ad: {} for ad in bolgeler.adlar}}
    alt = min(esikler) - DM / 2
    s = ic & (sim['m'] >= alt)
    adlar = bolgeler.ata(sim['enlem'][s], sim['boylam'][s])
    for e in esikler:
        anahtar = f'p{int(e)}'
        ust = sim['m'][s] >= e - DM / 2
        sonuc['turkiye'][anahtar] = np.unique(sim['kat'][s][ust]).size / n
        for ad in bolgeler.adlar:
            sonuc['bolgeler'][ad][anahtar] = np.unique(sim['kat'][s][ust & (adlar == ad)]).size / n
    return sonuc


def poisson_olasilik(lam_mc_yil, mc, b, m, gun=GUN):
    lam = lam_mc_yil * 10 ** (-b * (m - mc))
    return 1 - math.exp(-lam * gun / YIL_GUN)


def poisson_taban(z, e, bo, m, bagimsiz, mc, b, bolgeler, bas_ms, bit_ms, esikler=ESIKLER, kutu=KUTU):
    """Kart 19 ile aynı λ: bağımsız olaylar, M ≥ Mc, [bas, bit) yılı başına; G-R ile eşiğe uzatılır."""
    yil = (bit_ms - bas_ms) / GUN_MS / YIL_GUN
    s = bagimsiz & (kutula(m) >= mc - 1e-9) & (z >= bas_ms) & (z < bit_ms) & kutuda(e, bo, kutu)
    adlar = bolgeler.ata(e[s], bo[s])
    sonuc = {'turkiye': {'lambda_mc': float(s.sum()) / yil}, 'bolgeler': {}}
    for ad in bolgeler.adlar:
        sonuc['bolgeler'][ad] = {'lambda_mc': float((adlar == ad).sum()) / yil}
    for kayit in [sonuc['turkiye'], *sonuc['bolgeler'].values()]:
        for esik_m in esikler:
            kayit[f'p{int(esik_m)}'] = poisson_olasilik(kayit['lambda_mc'], mc, b, esik_m)
    return sonuc


# ---------- gizli ileriye dönük kayıt ----------

def hafta_basi(ms):
    """O haftanın pazartesisi (UTC) 'YYYY-AA-GG'."""
    d = datetime.fromtimestamp(ms / 1000, tz=UTC).date()
    return (d - timedelta(days=d.weekday())).isoformat()


def gizli_kayit_guncelle(kayit, simdi_ms, tahmin, olaylar):
    """Haftada bir (o haftanın ilk çalıştırması) tahmin eklenir; süresi dolan kayıtların gözlemi doldurulur.
    tahmin None (Poisson modu) ise yeni kayıt eklenmez."""
    kayit = [dict(k) for k in (kayit or [])]
    hafta = hafta_basi(simdi_ms)
    if tahmin is not None and not any(k['hafta'] == hafta for k in kayit):
        kayit.append({'hafta': hafta, 'model': MODEL_SURUM, 'baslangic': int(simdi_ms),
                      'bitis': int(simdi_ms + GUN * GUN_MS), **tahmin})
    z = np.array([o['zaman_ms'] for o in olaylar], float)
    mm = kutula(np.array([o['mw'] for o in olaylar], float)) if olaylar else np.zeros(0)
    ic = kutuda(np.array([o['enlem'] for o in olaylar], float), np.array([o['boylam'] for o in olaylar], float)) \
        if olaylar else np.zeros(0, bool)
    for k in kayit:
        if k.get('gozlenen5') is None and k['bitis'] <= simdi_ms:
            s = ic & (z >= k['baslangic']) & (z < k['bitis'])
            k['gozlenen5'] = bool((mm[s] >= 5.0 - 1e-9).any())
            k['gozlenen6'] = bool((mm[s] >= 6.0 - 1e-9).any())
            k['enBuyuk'] = float(mm[s].max()) if s.any() else None
    return kayit[-GIZLI_TUT:]


def gizli_hafta(kayit, dogrulama):
    """Doğrulama tarihinden sonra başlamış, gözlemi dolmuş ve aynı model sürümüyle yapılmış hafta sayısı."""
    if not dogrulama or not dogrulama.get('tarih'):
        return 0
    return sum(1 for k in (kayit or []) if k.get('gozlenen5') is not None and k.get('model') == MODEL_SURUM
               and k['baslangic'] >= dogrulama['tarih'])


def kapi(dogrulama, kayit):
    """Yayın kapısı: doğrulama geçti VE gizli kayıt ≥ 8 hafta → kanal; aksi halde yalnız özel sohbet.
    Doğrulama yalnız aynı MODEL_SURUM için sayılır; başka sürümün sonucu "yapılmadı" gibi davranır."""
    if dogrulama and dogrulama.get('surum') != MODEL_SURUM:
        return {'gecti': None, 'ozet': f"doğrulama eski model sürümüne ait ({dogrulama.get('surum')})",
                'gizliHafta': 0, 'yayin': False}
    gecti = bool(dogrulama.get('gecti')) if dogrulama else False
    hafta = gizli_hafta(kayit, dogrulama)
    return {'gecti': gecti if dogrulama else None, 'ozet': (dogrulama or {}).get('ozet', 'doğrulama yapılmadı'),
            'gizliHafta': hafta, 'yayin': gecti and hafta >= GIZLI_EN_AZ}


# ---------- durum ----------

def _oku_gz(yol):
    if not os.path.exists(yol):
        return {}
    try:
        with gzip.open(yol, 'rt', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _yaz_gz(yol, veri):
    gecici = yol + '.tmp'
    with gzip.open(gecici, 'wt', encoding='utf-8') as f:
        json.dump(veri, f, separators=(',', ':'))
    os.replace(gecici, yol)


def uyum_gerekli(durum, olaylar, simdi_ms, zorla=False):
    """(bool, neden): uyum yok; pazar günü ve son uyum ≥ 2 gün önce; son uyumdan sonra kutuda M ≥ 5,5."""
    son = durum.get('son')
    if zorla:
        return True, 'zorla'
    if not son:
        return True, 'uyum yok'
    if son.get('surum') != MODEL_SURUM:
        return True, f"model sürümü değişti ({son.get('surum')} → {MODEL_SURUM})"
    if datetime.fromtimestamp(simdi_ms / 1000, tz=UTC).weekday() == 6 and simdi_ms - son['zaman'] >= 2 * GUN_MS:
        return True, 'haftalık (pazar)'
    for o in olaylar:
        if o['zaman_ms'] >= son['zaman'] and kutula(o['mw']) >= YENIDEN_UYUM_M - 1e-9 \
                and kutuda(o['enlem'], o['boylam']):
            return True, f"M {float(kutula(o['mw'])):.1f} sonrası"
    return False, ''


def _yuzde(x):
    return None if x is None else round(float(x), 4)


def blok(simdi_ms, mod, u, uyum_durumu, olas, taban, sure, n, kapi_durumu, neden=''):
    """kart-veri.json 'etas' bloğu."""
    def kayit(ad=None):
        o = (olas or {}).get('turkiye' if ad is None else 'bolgeler', {})
        o = o if ad is None else o.get(ad, {})
        t = taban['turkiye'] if ad is None else taban['bolgeler'][ad]
        r = {'p5': _yuzde(o.get('p5')), 'p6': _yuzde(o.get('p6')), 'norm5': _yuzde(t['p5']), 'norm6': _yuzde(t['p6'])}
        if ad is not None:
            r = {'ad': ad, **r}
        return r
    return {
        'surum': MODEL_SURUM, 'hesap': int(simdi_ms), 'baslangic': int(simdi_ms),
        'bitis': int(simdi_ms + GUN * GUN_MS), 'mod': mod, 'neden': neden, 'simulasyon': n if mod == 'etas' else 0,
        'turkiye': kayit(), 'bolgeler': [kayit(ad) for ad in taban['bolgeler']],
        'uyum': None if u is None else {
            'zaman': u['zaman'], 'durum': uyum_durumu, 'mc': u['mc'], 'b': u['b'],
            'parametreler': {k: round(v, 4) for k, v in u['parametreler'].items()},
            'alfa': round(u['alfa'], 3), 'p': round(u['p'], 3),
            'dallanma': None if u['dallanma'] is None else round(u['dallanma'], 3),
            'n': u['n'], 'sure_s': u['sure_s']},
        'poisson': {'mc': taban['mc'], 'b': taban['b'], 'lambdaMc': round(taban['turkiye']['lambda_mc'], 3)},
        'sure': sure, 'kapi': kapi_durumu,
    }


def ileri_sinav(simdi_ms, mod, olas, taban, olaylar, bolgeler, mc):
    """İleriye dönük sınav kaydı (docs/etas-on-kayit.md): D1 etas_kayit. D1 yoksa ya da hata olursa None;
    sınav hatası gece işini düşürmez."""
    from hesap import d1, etas_kayit
    if not d1.hazir():
        return None
    try:
        adlar = list(taban['bolgeler'])
        p = [olas['bolgeler'][ad]['p5'] if mod == 'etas' else None for ad in adlar]
        tb = [taban['bolgeler'][ad]['p5'] for ad in adlar]
        ata = lambda en, bo: list(bolgeler.ata(np.array(en, float), np.array(bo, float)))
        o = [dict(x, mw=float(kutula(np.array([x['mw']], float))[0])) for x in olaylar]
        s = etas_kayit.calistir(d1, MODEL_SURUM, mc, simdi_ms, hafta_basi(simdi_ms), p, tb, adlar, mod, o, ata)
        print(f"ileriye dönük sınav: {s['hafta']}/{s['hedef']} hafta")
        return {'hafta': s['hafta'], 'hedef': s['hedef']}
    except Exception as h:
        print(f'UYARI ileriye dönük sınav kaydı başarısız: {type(h).__name__}: {h}', file=sys.stderr)
        return None


# ---------- ana akış ----------

def ana(argv=None):
    for akis in (sys.stdout, sys.stderr):
        if hasattr(akis, 'reconfigure'):
            akis.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description='tertremo haftalık ETAS olasılığı')
    ap.add_argument('--onbellek', default=os.path.join(os.path.dirname(__file__), '.onbellek'))
    ap.add_argument('--kart-veri', default=None, help='vars.: <onbellek>/kart-veri.json')
    ap.add_argument('--n', type=int, default=SIMULASYON)
    ap.add_argument('--uyum', choices=['otomatik', 'zorla', 'yok'], default='otomatik')
    ap.add_argument('--simdi', help='deneme: ISO zaman (UTC)')
    ap.add_argument('--tohum', type=int, default=None)
    a = ap.parse_args(argv)
    t_bas = time.monotonic()
    simdi_dt = datetime.fromisoformat(a.simdi).replace(tzinfo=UTC) if a.simdi else datetime.now(UTC)
    simdi = _ms(simdi_dt.replace(microsecond=0))
    kv_yol = a.kart_veri or os.path.join(a.onbellek, 'kart-veri.json')
    durum_yol = os.path.join(a.onbellek, 'etas-durum.json.gz')
    durum = _oku_gz(durum_yol)
    # başka model sürümünün uyumu (farklı Mc/kural) yedek olarak da kullanılmaz
    for k in ('son', 'son_iyi'):
        if (durum.get(k) or {}).get('surum') != MODEL_SURUM:
            durum.pop(k, None)
    olaylar = [o for o in kat.yukle(os.path.join(a.onbellek, 'tr.csv.gz')) if o['zaman_ms'] < simdi]
    if not olaylar:
        print('HATA: önbellekte Türkiye kataloğu yok', file=sys.stderr)
        return 1
    olaylar, z, e, bo, m = _diziler(olaylar)
    sure = {}

    t1 = time.monotonic()
    bagimsiz, d_f = kumele(z, e, bo, m)
    sure['kumele_s'] = round(time.monotonic() - t1, 1)
    mc, mc_ham = mc_egitim(z, m)
    b, b_ham = bolgesel_b(m, bagimsiz, mc)
    bolgeler = Bolgeler()
    taban = poisson_taban(z, e, bo, m, bagimsiz, mc, b, bolgeler, max(z.min(), _ms(YARDIMCI_BAS)), simdi)
    taban.update(mc=mc, b=round(b, 3))
    print(f'Mc {mc} (eğitim MBS {mc_ham}), b {b:.3f} (ham {b_ham:.3f}), d_f {d_f:.3f}, '
          f'bağımsız {int(bagimsiz.sum())}/{z.size}, λ(Mc) {taban["turkiye"]["lambda_mc"]:.1f}/yıl')

    gerek, neden = uyum_gerekli(durum, olaylar, simdi, a.uyum == 'zorla')
    yeni = None
    if gerek and a.uyum != 'yok':
        t1 = time.monotonic()
        try:
            yeni = uyum(olaylar, simdi, mc, b)
            ok, red = makul(yeni)
            print(f"uyum ({neden}): {yeni['sure_s']} s, n {yeni['n']}, çift {yeni['cift']}, α {yeni['alfa']:.2f}, "
                  f"p {yeni['p']:.3f}, dallanma {yeni['dallanma']}, {'makul' if ok else 'MAKUL DEĞİL: ' + red}")
            durum['son'] = yeni
            if ok:
                durum['son_iyi'] = yeni
        except Exception as h:  # paket hatası gece işini düşürmesin; son iyi uyum kullanılır
            print(f'UYARI uyum başarısız: {type(h).__name__}: {h}', file=sys.stderr)
        sure['uyum_s'] = round(time.monotonic() - t1, 1)
        _yaz_gz(durum_yol, durum)
    u, uyum_durumu = uyum_sec(yeni if yeni is not None else durum.get('son'), durum.get('son_iyi'))
    if yeni is None and u is not None and u is durum.get('son'):
        uyum_durumu = 'son'

    olas, mod, n, neden_mod = None, 'poisson', 0, 'bu hafta model güncellenemedi'
    if u is not None:
        t1 = time.monotonic()
        n = max(a.n, 1)
        rng = np.random.default_rng(a.tohum)
        try:
            sim = Simulator(u).calistir(kaynaklar(olaylar, simdi, u['mc']), n, rng)
            olas = olasiliklar(sim, bolgeler)
            mod, neden_mod = 'etas', ''
            print(f"simülasyon: {n} katalog, {sim['toplam']} olay, {time.monotonic() - t1:.1f} s, "
                  f"P(M≥5) {olas['turkiye']['p5']:.3f} (olağan {taban['turkiye']['p5']:.3f})")
        except Exception as h:
            print(f'UYARI simülasyon başarısız: {type(h).__name__}: {h}', file=sys.stderr)
        sure['simulasyon_s'] = round(time.monotonic() - t1, 1)
    sure['toplam_s'] = round(time.monotonic() - t_bas, 1)

    kv = kartveri.oku(kv_yol)
    tahmin = None
    if mod == 'etas':
        tahmin = {'p5': _yuzde(olas['turkiye']['p5']), 'p6': _yuzde(olas['turkiye']['p6']),
                  'norm5': _yuzde(taban['turkiye']['p5']), 'norm6': _yuzde(taban['turkiye']['p6']),
                  'bolgeler': {ad: _yuzde(v['p5']) for ad, v in olas['bolgeler'].items()}}
    gizli = gizli_kayit_guncelle(kv.get('etasGizliKayit'), simdi, tahmin, olaylar)
    k = kapi(kv.get('etasDogrulama'), gizli)
    veri = blok(simdi, mod, u, uyum_durumu, olas, taban, sure, n, k, neden_mod)
    ileri = ileri_sinav(simdi, mod, olas, taban, olaylar, bolgeler, mc)
    if ileri:
        veri['ileri'] = ileri
    kartveri.guncelle(kv_yol, {'etas': veri, 'etasGizliKayit': gizli})
    print(f"ÖZET etas: mod {mod}, uyum {uyum_durumu}, süre {sure}, kapı {k}")
    return 0


if __name__ == '__main__':
    sys.exit(ana())
