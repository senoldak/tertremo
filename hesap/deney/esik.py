# Deney `esik`: ETAS'ı Mc altındaki küçük olaylarla da besle (tetikleyici eşik düşük), değerlendirmeyi M ≥ 4'te tut.
#
# Gerekçe: docs/literatur-taramasi-4-2026-11-26.md §4 (Stockman, Lawson & Werner 2023; Xiong ve ark. 2026 ön baskı;
# Mizrahi, Nandan & Wiemer 2021 JGR, doi:10.1029/2021JB022379).
#
# Paket desteği (rapor docs/olcum-deney-esik-2026-11.md): Mizrahi `etas` paketinde kaynak ve hedef kümesi ayrılamaz;
# olabilirlikte ikisi de "büyüklük ≥ mc_current" olaylardır (mc='var' ya da sabit mc). Ayrım yalnız simülasyon
# çıktısında vardır (Simulator.simulate m_threshold). Bu modülde ayrım böyle kurulur: uyum ve kaynak kümesi
# eşik_tetik'te (M ≥ 3,0), tahmin/değerlendirme hedef eşiğinde (M ≥ 4) — hesap/dogrulama.calistir'in kuralıyla aynı:
# kaynak = etas.kaynaklar(olaylar, t0, u['mc']), hedef = simülasyonda büyüklük ≥ hedef − ΔM/2.
# Sınır: sabit mc = tetik eşiği, yani EMSC'nin M3–4 aralığındaki eksikliği (özellikle büyük depremden sonra)
# modellenmez; paketin mc='var' yolu zamana bağlı tamamlanma ister (kapsam dışı, raporda).
#
# Protokol dogrulama.py'nin indirgenmiş kopyasıdır: aynı pencere (7 gün), yıllık yeniden uyum, aynı Mc/b/Poisson
# tabanı, aynı su seviyesi; fark yalnız uyum işlevi (tetikleyici eşiği) ve A/B'nin aynı döngüde, aynı tohumla koşması.
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np

from hesap import dogrulama as dg
from hesap import etas
from hesap import katalog as kat
from hesap.hucre import kutula

UTC = timezone.utc
GUN_MS = etas.GUN_MS
KAHRAMANMARAS_MS = datetime(2023, 2, 6, 1, 17, tzinfo=UTC).timestamp() * 1000  # Mw 7,8 (EMSC/USGS ≈ 01:17 UTC)
KM_GUN = 14


# ---------- uyum işlevleri ----------

def uyum_esikli(tetik):
    """dogrulama.model_kur'un uyum_fn'i: Mc yerine `tetik` (Mc'den küçükse) eşiğiyle paketin EM uyumu.
    b aynı kalır (Mc üstünde, kümelenmesi ayrılmış olaylardan): iki varyantın simülasyon büyüklük dağılımı aynı."""
    def fn(olaylar, t_ms, mc, b):
        return etas.uyum(olaylar, t_ms, min(tetik, mc), b)
    return fn


# ---------- karşılaştırma ölçütleri ----------

def esli_brier(p_a, p_b, o, tohum=0, tekrar=2000):
    """B'nin A'ya göre Brier becerisi 1 − BS_B/BS_A ve haftalar üzerinden eşli bootstrap %95 aralığı.
    Aynı hafta çiftleri yeniden örneklenir (haftalar arası bağımlılık yok sayılır; yaklaşık)."""
    p_a, p_b, o = np.asarray(p_a, float), np.asarray(p_b, float), np.asarray(o, float)
    if p_a.size == 0 or dg.brier(p_a, o) == 0:
        return {'beceri': None, 'alt': None, 'ust': None}
    r = np.random.default_rng(tohum)
    ix = r.integers(0, p_a.size, (tekrar, p_a.size))
    ba = ((p_a - o) ** 2)[ix].mean(1)
    bb = ((p_b - o) ** 2)[ix].mean(1)
    iyi = ba > 0
    bec = 1 - bb[iyi] / ba[iyi]
    return {'beceri': dg.brier_beceri(p_b, p_a, o), 'alt': float(np.percentile(bec, 2.5)),
            'ust': float(np.percentile(bec, 97.5))}


# ---------- haftalık değerlendirme (A ve B aynı döngüde) ----------

class Varyant:
    """Bir uyum işlevinin yıllık yeniden uyum zinciri ve ölçüt birikimi."""

    def __init__(self, ad, uyum_fn, tohum):
        self.ad, self.uyum_fn = ad, uyum_fn
        self.rng = np.random.default_rng(tohum)
        self.onceki = None
        self.model = None
        self.sim = None
        self.kayit = {k: [] for k in ('p5', 'o5', 'n_gozlenen', 'nt_d1', 'nt_d2', 'beklenen4')}
        self.hedef_hiz = []
        self.toplam = 0.0
        self.sim_toplam = None
        self.modeller = []
        self.sure = {'uyum_s': 0.0, 'simulasyon_s': 0.0}
        self.uyumlar = {}   # yeniden uyum tarihi (ms) → model (Kahramanmaraş günlük değerlendirmesi için)


def _yeniden_uyum(v, olaylar, z, e, bo, m, tm, mc_eg, hedef, gunluk):
    mod = dg.model_kur(olaylar, z, e, bo, m, tm, v.onceki, v.uyum_fn, mc=mc_eg, hedef=hedef)
    mod['t'] = tm
    if mod['uyum'] is not None:
        v.onceki = mod['uyum']
    v.sure['uyum_s'] += mod['uyum_s']
    u = mod['uyum']
    v.modeller.append({
        'tarih': datetime.fromtimestamp(tm / 1000, tz=UTC).date().isoformat(), 'durum': mod['durum'],
        'mc': mod['mc'], 'b': round(mod['b'], 3), 'uyum_s': mod['uyum_s'],
        'tetik_esigi': None if u is None else u['mc'], 'n': None if u is None else u['n'],
        'parametreler': None if u is None else {k: round(x, 3) for k, x in u['parametreler'].items()},
        'alfa': None if u is None else round(u['alfa'], 3), 'p': None if u is None else round(u['p'], 3),
        'dallanma': None if u is None or u['dallanma'] is None else round(u['dallanma'], 3)})
    gunluk(f'[{v.ad}] model {v.modeller[-1]}')
    v.model = mod
    v.sim = etas.Simulator(u) if u is not None else None
    v.uyumlar[tm] = mod
    return mod


def _hafta_simule(v, olaylar, t0, n, hedef, ne, nb):
    """Bir pencere için (hücre hızı, N sayıları, P(≥1 M≥5)). Model yoksa dogrulama.calistir'deki Poisson yedeği."""
    u = v.model['uyum']
    ts = time.monotonic()
    if v.sim is not None:
        sim = v.sim.calistir(etas.kaynaklar(olaylar, t0, u['mc']), n, v.rng)
        ic = etas.kutuda(sim['enlem'], sim['boylam'])
        s4 = ic & (sim['m'] >= hedef - etas.DM / 2)
        s5 = ic & (sim['m'] >= 5.0 - etas.DM / 2)
        p5 = np.unique(sim['kat'][s5]).size / n
        hiz = np.bincount(dg.hucre(sim['enlem'][s4], sim['boylam'][s4]), minlength=ne * nb) / n
        say = np.bincount(sim['kat'][s4], minlength=n)
    else:
        p5 = v.model['taban']['p5']
        hiz = v.model['taban']['hiz4']
        say = v.rng.poisson(hiz.sum(), n)
    v.sure['simulasyon_s'] += time.monotonic() - ts
    return hiz, say, p5


def karsilastir(olaylar, bit_ms, uyumlar, n=2000, bas_dt=dg.DENEME_BAS, tohum=0, pencere_sinir=None, gunluk=print):
    """uyumlar: {ad: uyum_fn}; ilk ad taban (A). Dönüş: {'varyant': {ad: ölçütler}, 'karsilastirma': {ad: B'nin A'ya...},
    'kapsam', 'haftalar'}. Her varyantın rng'si aynı tohumla başlar (A, dogrulama.calistir ile birebir aynı akışı izler)."""
    olaylar, z, e, bo, m = etas._diziler(olaylar)
    mk = kutula(m)
    hc = dg.hucre(e, bo)
    tarihler = dg.yeniden_uyum_tarihleri(bas_dt, bit_ms)
    pen = dg.pencereler(etas._ms(bas_dt), bit_ms)
    if pencere_sinir:
        pen = pen[:pencere_sinir]
    ne, nb = dg.izgara()
    mc_eg, mc_ham = etas.mc_egitim(z, m)
    hedef = max(dg.HEDEF_M, mc_eg)
    var = {ad: Varyant(ad, fn, tohum) for ad, fn in uyumlar.items()}
    for v in var.values():
        v.sim_toplam = np.zeros(n, np.int64)
    ortak = {k: [] for k in ('taban5', 'tum5', 'o5', 'o6', 'n_gozlenen')}
    hedef_pois, hedef_tum = [], []
    toplam = {'pois': 0.0, 'tum': 0.0}
    tm = None
    for t0 in pen:
        sonraki = [t for t in tarihler if t <= t0]
        if tm is None or (sonraki and sonraki[-1] > tm):
            tm = sonraki[-1] if sonraki else t0
            for v in var.values():
                _yeniden_uyum(v, olaylar, z, e, bo, m, tm, mc_eg, hedef, gunluk)
        ref = next(iter(var.values())).model   # Poisson tabanları Mc/b aynı olduğundan varyantlar arasında aynı
        t1 = t0 + 7 * GUN_MS
        g = (z >= t0) & (z < t1) & (hc >= 0)
        g4 = g & (mk >= hedef - 1e-9)
        n_goz = int(g4.sum())
        o5 = bool((g & (mk >= 5.0 - 1e-9)).any())
        o6 = bool((g & (mk >= 6.0 - 1e-9)).any())
        hp, ht = dg.su_seviyesi(ref['taban']['hiz4']), dg.su_seviyesi(ref['tum']['hiz4'])
        hedef_pois.extend(hp[hc[g4]])
        hedef_tum.extend(ht[hc[g4]])
        toplam['pois'] += hp.sum()
        toplam['tum'] += ht.sum()
        for k, x in (('taban5', ref['taban']['p5']), ('tum5', ref['tum']['p5']), ('o5', o5), ('o6', o6),
                     ('n_gozlenen', n_goz)):
            ortak[k].append(x)
        for v in var.values():
            hiz, say, p5 = _hafta_simule(v, olaylar, t0, n, hedef, ne, nb)
            hiz = dg.su_seviyesi(hiz)
            v.hedef_hiz.extend(hiz[hc[g4]])
            v.toplam += hiz.sum()
            v.sim_toplam += say
            h = dg.n_testi(say, n_goz)
            for k, x in (('p5', p5), ('o5', o5), ('n_gozlenen', n_goz), ('nt_d1', h['d1']), ('nt_d2', h['d2']),
                         ('beklenen4', float(hiz.sum()))):
                v.kayit[k].append(x)
        if len(ortak['o5']) % 20 == 0:
            gunluk(f"{len(ortak['o5'])}/{len(pen)} pencere " +
                   ', '.join(f"{v.ad} sim {v.sure['simulasyon_s']:.0f} s" for v in var.values()))
    n_top = int(sum(ortak['n_gozlenen']))
    sonuc = {'varyant': {}, 'karsilastirma': {}}
    for ad, v in var.items():
        gecme = [(a >= dg.ALFA / 2) and (b >= dg.ALFA / 2) for a, b in zip(v.kayit['nt_d1'], v.kayit['nt_d2'])]
        sonuc['varyant'][ad] = {
            't_testi_poisson': dg.t_testi(v.hedef_hiz, hedef_pois, n_top, v.toplam, toplam['pois']),
            'brier_beceri_poisson': dg.brier_beceri(v.kayit['p5'], ortak['taban5'], ortak['o5']),
            'brier': dg.brier(v.kayit['p5'], ortak['o5']),
            'n_haftalik_gecme': float(np.mean(gecme)) if gecme else None,
            'n_testi_toplam': dg.n_testi(v.sim_toplam, n_top),
            'ortalama_p5': float(np.mean(v.kayit['p5'])) if pen else None,
            'beklenen_m4_toplam': float(v.toplam), 'modeller': v.modeller, 'sure': {k: round(x, 1) for k, x in v.sure.items()}}
    ad0 = next(iter(var))
    for ad, v in var.items():
        if ad == ad0:
            continue
        a = var[ad0]
        sonuc['karsilastirma'][ad] = {
            'karsi': ad0,
            't_testi': dg.t_testi(v.hedef_hiz, a.hedef_hiz, n_top, v.toplam, a.toplam),
            'brier': esli_brier(a.kayit['p5'], v.kayit['p5'], ortak['o5']),
            'n_gecme_fark': sonuc['varyant'][ad]['n_haftalik_gecme'] - sonuc['varyant'][ad0]['n_haftalik_gecme']}
    sonuc['ortak'] = {'poisson_beklenen_m4': float(toplam['pois']), 'gozlenen_m4': n_top,
                      'gozlenen_m5_hafta': int(sum(ortak['o5'])), 'brier_poisson': dg.brier(ortak['taban5'], ortak['o5'])}
    sonuc['kapsam'] = {
        'pencere': len(pen), 'simulasyon': n, 'tohum': tohum, 'yeniden_uyum': 'yıllık (1 Ocak)', 'hedef_m': hedef,
        'mc': mc_eg, 'mc_mbs_ham': mc_ham, 'bas': bas_dt.date().isoformat(),
        'bit': datetime.fromtimestamp((pen[-1] + 7 * GUN_MS) / 1000, tz=UTC).date().isoformat() if pen else None}
    sonuc['haftalar'] = {'ortak': ortak, **{ad: v.kayit for ad, v in var.items()}}
    sonuc['_modeller'] = {ad: v.uyumlar for ad, v in var.items()}
    return sonuc


# ---------- Kahramanmaraş sonrası ilk 2 hafta, günlük pencereler ----------

def gunluk_degerlendir(olaylar, t_bas_ms, gun_sayisi, modeller, n=2000, tohum=0, gunluk=print):
    """modeller: {ad: dogrulama.model_kur çıktısı} (Kahramanmaraş öncesi son yıllık uyum; sonrası veri yok).
    Her 24 saatlik pencere kendinden önceki gözlenen olaylarla beslenir (kaynaklar). Dönüş: günlük satırlar ve
    ortak hedef olay başına ölçütler (aynı su seviyesi, hücre × gün, M ≥ hedef)."""
    olaylar, z, e, bo, m = etas._diziler(olaylar)
    mk = kutula(m)
    hc = dg.hucre(e, bo)
    ne, nb = dg.izgara()
    ad0 = next(iter(modeller))
    ref = modeller[ad0]
    hedef = max(dg.HEDEF_M, ref['mc'])
    sims = {ad: (etas.Simulator(md['uyum'], gun=1.0) if md['uyum'] is not None else None) for ad, md in modeller.items()}
    rng = {ad: np.random.default_rng(tohum) for ad in modeller}
    satirlar, hedef_hiz, hedef_pois = [], {ad: [] for ad in modeller}, []
    toplam = {ad: 0.0 for ad in modeller}
    toplam_pois = 0.0
    sim_toplam = {ad: np.zeros(n, np.int64) for ad in modeller}
    n_top = 0
    for d in range(gun_sayisi):
        t0 = t_bas_ms + d * GUN_MS
        g = (z >= t0) & (z < t0 + GUN_MS) & (hc >= 0)
        g4 = g & (mk >= hedef - 1e-9)
        o5 = bool((g & (mk >= 5.0 - 1e-9)).any())
        gun_pois = dg.su_seviyesi(ref['taban']['hiz4'] / 7)
        hedef_pois.extend(gun_pois[hc[g4]])
        toplam_pois += gun_pois.sum()
        n_top += int(g4.sum())
        satir = {'gun': d + 1, 'bas': datetime.fromtimestamp(t0 / 1000, tz=UTC).isoformat(timespec='minutes'),
                 'gozlenen_m4': int(g4.sum()), 'gozlenen_m5': o5, 'poisson_beklenen': float(gun_pois.sum())}
        for ad, md in modeller.items():
            u = md['uyum']
            if sims[ad] is None:
                continue
            sim = sims[ad].calistir(etas.kaynaklar(olaylar, t0, u['mc']), n, rng[ad])
            ic = etas.kutuda(sim['enlem'], sim['boylam'])
            s4 = ic & (sim['m'] >= hedef - etas.DM / 2)
            s5 = ic & (sim['m'] >= 5.0 - etas.DM / 2)
            hiz = dg.su_seviyesi(np.bincount(dg.hucre(sim['enlem'][s4], sim['boylam'][s4]), minlength=ne * nb) / n)
            say = np.bincount(sim['kat'][s4], minlength=n)
            h = dg.n_testi(say, int(g4.sum()))
            hedef_hiz[ad].extend(hiz[hc[g4]])
            toplam[ad] += hiz.sum()
            sim_toplam[ad] += say
            satir[ad] = {'beklenen_m4': float(hiz.sum()), 'p5': np.unique(sim['kat'][s5]).size / n,
                         'nt_d1': h['d1'], 'nt_d2': h['d2'], 'n_reddedildi': h['reddedildi'],
                         'ort_ll': float(sum(np.log(hiz[hc[g4]])) - hiz.sum())}
        satirlar.append(satir)
        gunluk(f"gün {d + 1}: gözlenen M≥{hedef:g} {int(g4.sum())}; " +
               ', '.join(f"{ad} {satir[ad]['beklenen_m4']:.1f}" for ad in modeller if ad in satir))
    ozet = {'gozlenen_m4': n_top, 'poisson_beklenen_m4': float(toplam_pois),
            'varyant': {ad: {'beklenen_m4': float(toplam[ad]),
                             'ortak_ll_poisson_farki': float(sum(np.log(hedef_hiz[ad])) - sum(np.log(hedef_pois))
                                                              - toplam[ad] + toplam_pois),
                             't_testi_poisson': dg.t_testi(hedef_hiz[ad], hedef_pois, n_top, toplam[ad], toplam_pois),
                             'n_gun_reddedildi': int(sum(s[ad]['n_reddedildi'] for s in satirlar if ad in s)),
                             'brier_p5': dg.brier([s[ad]['p5'] for s in satirlar if ad in s],
                                                  [s['gozlenen_m5'] for s in satirlar if ad in s])}
                        for ad in modeller if sims[ad] is not None}}
    for ad in list(modeller)[1:]:
        if sims[ad] is not None and sims[ad0] is not None:
            ozet.setdefault('karsilastirma', {})[ad] = {
                'karsi': ad0, 't_testi': dg.t_testi(hedef_hiz[ad], hedef_hiz[ad0], n_top, toplam[ad], toplam[ad0]),
                'brier_p5_fark': ozet['varyant'][ad]['brier_p5'] - ozet['varyant'][ad0]['brier_p5']}
    return {'gunler': satirlar, 'ozet': ozet, 'hedef_m': hedef}


# ---------- giriş ----------

def _json_hazirla(x):
    if isinstance(x, dict):
        return {str(k): _json_hazirla(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_json_hazirla(v) for v in x]
    if isinstance(x, (np.floating, np.integer, np.bool_)):
        return x.item()
    return x


def ana(argv=None):
    for akis in (sys.stdout, sys.stderr):
        if hasattr(akis, 'reconfigure'):
            akis.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description='Deney esik: tetikleyici eşik 3,0 / 3,5 ve hedef M≥4')
    ap.add_argument('--onbellek', default=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.onbellek'))
    ap.add_argument('--n', type=int, default=2000, help='simülasyon sayısı (varsayılan 2000; doğrulama 10 000)')
    ap.add_argument('--gunluk-n', type=int, default=4000, help='Kahramanmaraş günlük pencerelerde simülasyon')
    ap.add_argument('--pencere', type=int, default=None)
    ap.add_argument('--tohum', type=int, default=0)
    ap.add_argument('--esikler', default='3.0,3.5', help='B varyantlarının tetikleyici eşikleri')
    ap.add_argument('--cikti', default=None)
    a = ap.parse_args(argv)
    olaylar = kat.yukle(os.path.join(a.onbellek, 'tr.csv.gz'))
    bit_ms = max(o['zaman_ms'] for o in olaylar) + 1
    uyumlar = {'A': etas.uyum}
    for s in a.esikler.split(','):
        uyumlar[f'B{s.strip()}'] = uyum_esikli(float(s))
    t = time.monotonic()
    pr = lambda x: print(x, flush=True)  # noqa: E731
    s = karsilastir(olaylar, bit_ms, uyumlar, n=a.n, tohum=a.tohum, pencere_sinir=a.pencere, gunluk=pr)
    s['sure_toplam_s'] = round(time.monotonic() - t, 1)
    modeller = s.pop('_modeller')
    # Kahramanmaraş öncesi son yıllık uyum (2023-01-01)
    km_tarih = datetime(2023, 1, 1, tzinfo=UTC).timestamp() * 1000
    if all(km_tarih in modeller[ad] for ad in modeller) and not a.pencere:
        g = gunluk_degerlendir(olaylar, KAHRAMANMARAS_MS + 3600_000, KM_GUN,
                               {ad: modeller[ad][km_tarih] for ad in modeller}, n=a.gunluk_n, tohum=a.tohum, gunluk=pr)
        s['kahramanmaras'] = g
    s['surum'] = etas.MODEL_SURUM
    yol = a.cikti or os.path.join(a.onbellek, 'deney', 'esik.json')
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with open(yol, 'w', encoding='utf-8') as f:
        json.dump(_json_hazirla(s), f, ensure_ascii=False, indent=1)
    pr(f"BİTTİ {yol} {s['sure_toplam_s']} s")
    return 0


if __name__ == '__main__':
    sys.exit(ana())
