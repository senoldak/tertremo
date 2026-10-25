# ETAS haftalık olasılığının sözde-ileriye dönük doğrulaması (yayın kapısı).
#
# Protokol (controller kararı, etas-tarama.md §4):
# - Eğitim 2018–2021; deneme 2022-01-01'den bugüne üst üste binmeyen 7 günlük pencereler.
# - Her pencere yalnız pencere başından önceki veriyle tahmin edilir: kaynaklar = pencereden önceki gözlenen olaylar;
#   parametreler, Mc, b ve Poisson tabanı her yıl 1 Ocak'ta o tarihe kadarki veriyle yeniden hesaplanır
#   (gece işi haftalık yeniden uyum yapar; burada yıllık — süre nedeniyle indirgeme, raporda belirtilir).
# - Karşılaştırma: kümelenmesi ayrılmış Poisson (Kart 19 ile aynı λ, uzaysal dağılım bağımsız olayların 0,5° hücre
#   sayılarından, 3×3 yumuşatılmış).
# - Ölçütler: pyCSEP (BSD-3, csep 0.8.0) paired T-testi (_t_test_ndarray; Rhoades vd. 2011) — M ≥ 4 hedefler,
#   0,5° hücre × hafta; Brier beceri skoru "kutuda ≥ 1 M ≥ 5"; katalog tabanlı N-testi (get_quantiles; Savran vd.
#   2022) bütün dönemin toplam M ≥ 4 sayısı ve haftalık geçme oranı (bilgi).
# - Her iki modele aynı su seviyesi: hücre hızı = 0,99·model + 0,01·toplam/hücre sayısı (sıfır hız log'u için).
# - Mc: eğitim döneminin (2018–2021) MBS Mc'si (etas.mc_egitim), bütün yıllarda aynı. Hedef eşik max(4, Mc).
# - gecti = IG > 0 ve %95 T-testi aralığı 0'ı dışlar VE Brier beceri > 0 VE haftalık N-testlerinin ≥ %90'ı %5'te
#   reddedilmez (iki yönlü: δ1 ≥ 0,025 ve δ2 ≥ 0,025). Controller kararı (yeniden çalıştırmadan önce donduruldu):
#   bütün dönemin toplam N-testi yalnız raporlanır (koşullu bağımsız pencere simülasyonlarını toplamak yayılımı
#   küçümsüyor; Şubat 2023 haftası belirleyici).
# - Ek bilgi (kapıya girmez): kümelenmesi ayrılmamış (bütün olaylar) Poisson'a karşı aynı ölçütler.
import argparse
import json
import math
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np

from hesap import etas, kartveri
from hesap import katalog as kat
from hesap.hucre import kutula

UTC = timezone.utc
GUN_MS = etas.GUN_MS
DENEME_BAS = datetime(2022, 1, 1, tzinfo=UTC)
HUCRE = 0.5
HEDEF_M = 4.0
SU = 0.01
ALFA = 0.05
N_HAFTALIK_ESIK = 0.90


# ---------- ızgara ----------

def izgara(kutu=etas.KUTU, boy=HUCRE):
    ne = int(round((kutu['maxlat'] - kutu['minlat']) / boy))
    nb = int(round((kutu['maxlon'] - kutu['minlon']) / boy))
    return ne, nb


def hucre(enlem, boylam, kutu=etas.KUTU, boy=HUCRE):
    """Kutu içi noktanın düz hücre indeksi (kutu dışı −1)."""
    ne, nb = izgara(kutu, boy)
    enlem, boylam = np.asarray(enlem, float), np.asarray(boylam, float)
    i = np.clip(np.floor((enlem - kutu['minlat']) / boy).astype(np.int64), 0, ne - 1)
    j = np.clip(np.floor((boylam - kutu['minlon']) / boy).astype(np.int64), 0, nb - 1)
    return np.where(etas.kutuda(enlem, boylam, kutu), i * nb + j, -1)


def su_seviyesi(hiz, su=SU):
    hiz = np.asarray(hiz, float)
    return (1 - su) * hiz + su * hiz.sum() / hiz.size


# ---------- ölçütler ----------

def t_testi(etas_hedef, pois_hedef, n_gozlenen, n_etas, n_pois, alfa=ALFA):
    """pyCSEP paired T-testi: ETAS'ın Poisson'a göre deprem başına bilgi kazancı ve %95 aralığı."""
    from csep.core.poisson_evaluations import _t_test_ndarray
    if n_gozlenen < 2:
        return {'ig': None, 'alt': None, 'ust': None, 'n': int(n_gozlenen)}
    r = _t_test_ndarray(np.asarray(etas_hedef, float), np.asarray(pois_hedef, float), n_gozlenen, n_etas, n_pois,
                        alpha=alfa)
    return {'ig': float(r['information_gain']), 'alt': float(r['ig_lower']), 'ust': float(r['ig_upper']),
            't': float(r['t_statistic']), 'n': int(n_gozlenen)}


def n_testi(sim_sayilari, gozlenen, alfa=ALFA):
    """pyCSEP katalog N-testi nicelikleri: δ1 = P(N_sim ≥ N_göz), δ2 = P(N_sim ≤ N_göz); iki yönlü red."""
    from csep.utils.stats import get_quantiles
    d1, d2 = get_quantiles(np.asarray(sim_sayilari), gozlenen)
    return {'d1': float(d1), 'd2': float(d2), 'gozlenen': int(gozlenen),
            'reddedildi': bool(d1 < alfa / 2 or d2 < alfa / 2)}


def brier(p, o):
    p, o = np.asarray(p, float), np.asarray(o, float)
    return float(np.mean((p - o) ** 2))


def brier_beceri(p_model, p_taban, o):
    bt = brier(p_taban, o)
    return None if bt == 0 else 1 - brier(p_model, o) / bt


def karar(tt, bss, haftalik_gecme):
    """Yayın kapısı (controller kararı): IG T-testi, Brier beceri ve haftalık N-testi geçme oranı ≥ %90."""
    return bool(tt.get('ig') is not None and tt['ig'] > 0 and tt['alt'] > 0
                and bss is not None and bss > 0
                and haftalik_gecme is not None and haftalik_gecme >= N_HAFTALIK_ESIK)


# ---------- Poisson tabanı (uzaysal) ----------

def poisson_uzay(z, e, bo, m, maske, mc, b, bas_ms, bit_ms, kutu=etas.KUTU, hedef=HEDEF_M):
    """maske (bağımsız ya da bütün) olaylardan haftalık M ≥ hedef hücre hızları ve kutuda P(≥1 M≥5), P(≥1 M≥6)."""
    yil = (bit_ms - bas_ms) / GUN_MS / etas.YIL_GUN
    s = maske & (kutula(m) >= mc - 1e-9) & (z >= bas_ms) & (z < bit_ms)
    h = hucre(e[s], bo[s], kutu)
    h = h[h >= 0]
    ne, nb = izgara(kutu)
    say = np.bincount(h, minlength=ne * nb).reshape(ne, nb).astype(float)
    pad = np.pad(say, 1, mode='edge')
    yum = sum(pad[1 + di:1 + di + ne, 1 + dj:1 + dj + nb] for di in (-1, 0, 1) for dj in (-1, 0, 1)) / 9
    lam_mc = h.size / yil
    hafta = 7 / etas.YIL_GUN
    lam4 = lam_mc * 10 ** (-b * (hedef - mc)) * hafta
    agirlik = yum.ravel() / yum.sum() if yum.sum() > 0 else np.full(ne * nb, 1 / (ne * nb))
    return {'hiz4': lam4 * agirlik, 'lambda_mc': lam_mc,
            'p5': etas.poisson_olasilik(lam_mc, mc, b, 5.0), 'p6': etas.poisson_olasilik(lam_mc, mc, b, 6.0)}


# ---------- çalıştırma ----------

def pencereler(bas_ms, bit_ms, gun=7):
    t = bas_ms
    sonuc = []
    while t + gun * GUN_MS <= bit_ms:
        sonuc.append(t)
        t += gun * GUN_MS
    return sonuc


def yeniden_uyum_tarihleri(bas_dt, bit_ms):
    yillar = range(bas_dt.year, datetime.fromtimestamp(bit_ms / 1000, tz=UTC).year + 1)
    return [datetime(y, 1, 1, tzinfo=UTC).timestamp() * 1000 for y in yillar]


def model_kur(olaylar, z, e, bo, m, t_ms, onceki, uyum_fn=etas.uyum, mc=None, hedef=HEDEF_M):
    """t_ms'ye kadarki veriyle Mc, b, kümelenme, ETAS uyumu ve Poisson tabanları."""
    s = z < t_ms
    bag, _ = etas.kumele(z[s], e[s], bo[s], m[s])
    if mc is None:
        mc = etas.mc_egitim(z[s], m[s])[0]
    b, b_ham = etas.bolgesel_b(m[s], bag, mc)
    gecmis = [o for o in olaylar if o['zaman_ms'] < t_ms]
    t0 = time.monotonic()
    try:
        u = uyum_fn(gecmis, t_ms, mc, b)
    except Exception as h:  # noqa: BLE001 — başarısız uyum = önceki iyi uyum (gece işindeki kural)
        print(f'UYARI uyum başarısız ({type(h).__name__}: {h})', file=sys.stderr)
        u = None
    sure = time.monotonic() - t0
    secilen, durum = etas.uyum_sec(u, onceki)
    bas = max(float(z.min()), etas._ms(etas.YARDIMCI_BAS))
    taban = poisson_uzay(z[s], e[s], bo[s], m[s], bag, mc, b, bas, t_ms, hedef=hedef)
    tum = poisson_uzay(z[s], e[s], bo[s], m[s], np.ones(int(s.sum()), bool), mc, b, bas, t_ms, hedef=hedef)
    return {'uyum': secilen, 'durum': durum, 'mc': mc, 'b': b, 'b_ham': b_ham, 'taban': taban, 'tum': tum,
            'uyum_s': round(sure, 1), 'ham': u}


def calistir(olaylar, bit_ms, n=etas.SIMULASYON, bas_dt=DENEME_BAS, tohum=0, uyum_fn=etas.uyum, gunluk=print,
             pencere_sinir=None):
    olaylar, z, e, bo, m = etas._diziler(olaylar)
    mk = kutula(m)
    hc = hucre(e, bo)
    rng = np.random.default_rng(tohum)
    tarihler = yeniden_uyum_tarihleri(bas_dt, bit_ms)
    pen = pencereler(etas._ms(bas_dt), bit_ms)
    if pencere_sinir:
        pen = pen[:pencere_sinir]
    ne, nb = izgara()
    mc_eg, mc_ham = etas.mc_egitim(z, m)   # yalnız 2018–2021 verisi; bütün yıllarda aynı
    hedef = max(HEDEF_M, mc_eg)
    kayit = {k: [] for k in ('p5', 'p6', 'taban5', 'tum5', 'o5', 'o6', 'n_gozlenen', 'nt_d1', 'nt_d2')}
    hedef_etas, hedef_pois, hedef_tum = [], [], []
    toplam = {'etas': 0.0, 'pois': 0.0, 'tum': 0.0}
    sim_toplam = np.zeros(n, np.int64)
    modeller, onceki, model = [], None, None
    sure = {'uyum_s': 0.0, 'simulasyon_s': 0.0}
    for t0 in pen:
        sonraki = [t for t in tarihler if t <= t0]
        if model is None or (sonraki and sonraki[-1] > model['t']):
            tm = sonraki[-1] if sonraki else t0
            model = model_kur(olaylar, z, e, bo, m, tm, onceki, uyum_fn, mc=mc_eg, hedef=hedef)
            model['t'] = tm
            if model['uyum'] is not None:
                onceki = model['uyum']
            sure['uyum_s'] += model['uyum_s']
            u = model['uyum']
            modeller.append({'tarih': datetime.fromtimestamp(tm / 1000, tz=UTC).date().isoformat(),
                             'durum': model['durum'], 'mc': model['mc'], 'b': round(model['b'], 3),
                             'uyum_s': model['uyum_s'],
                             'parametreler': None if u is None else {k: round(v, 3) for k, v in u['parametreler'].items()},
                             'alfa': None if u is None else round(u['alfa'], 3),
                             'p': None if u is None else round(u['p'], 3),
                             'dallanma': None if u is None or u['dallanma'] is None else round(u['dallanma'], 3)})
            gunluk(f"model {modeller[-1]}")
            sim_obj = etas.Simulator(u) if u is not None else None
        t1 = t0 + 7 * GUN_MS
        g = (z >= t0) & (z < t1) & (hc >= 0)
        g4 = g & (mk >= hedef - 1e-9)
        o5 = bool((g & (mk >= 5.0 - 1e-9)).any())
        o6 = bool((g & (mk >= 6.0 - 1e-9)).any())
        n_goz = int(g4.sum())
        ts = time.monotonic()
        if sim_obj is not None:
            sim = sim_obj.calistir(etas.kaynaklar(olaylar, t0, u['mc']), n, rng)
            ic = etas.kutuda(sim['enlem'], sim['boylam'])
            s4 = ic & (sim['m'] >= hedef - etas.DM / 2)
            s5 = ic & (sim['m'] >= 5.0 - etas.DM / 2)
            s6 = ic & (sim['m'] >= 6.0 - etas.DM / 2)
            p5 = np.unique(sim['kat'][s5]).size / n
            p6 = np.unique(sim['kat'][s6]).size / n
            hiz = np.bincount(hucre(sim['enlem'][s4], sim['boylam'][s4]), minlength=ne * nb) / n
            say = np.bincount(sim['kat'][s4], minlength=n)
        else:  # model yok: ETAS yerine Poisson (kapıyı geçemez — ölçütler kıyas için yine hesaplanır)
            p5, p6 = model['taban']['p5'], model['taban']['p6']
            hiz = model['taban']['hiz4']
            say = rng.poisson(hiz.sum(), n)
        sure['simulasyon_s'] += time.monotonic() - ts
        hiz = su_seviyesi(hiz)
        hp = su_seviyesi(model['taban']['hiz4'])
        ht = su_seviyesi(model['tum']['hiz4'])
        hedef_etas.extend(hiz[hc[g4]])
        hedef_pois.extend(hp[hc[g4]])
        hedef_tum.extend(ht[hc[g4]])
        toplam['etas'] += hiz.sum()
        toplam['pois'] += hp.sum()
        toplam['tum'] += ht.sum()
        sim_toplam += say
        haftalik = n_testi(say, n_goz)
        for k, v in (('p5', p5), ('p6', p6), ('taban5', model['taban']['p5']), ('tum5', model['tum']['p5']),
                     ('o5', o5), ('o6', o6), ('n_gozlenen', n_goz), ('nt_d1', haftalik['d1']),
                     ('nt_d2', haftalik['d2'])):
            kayit[k].append(v)
        if len(kayit['p5']) % 20 == 0:
            gunluk(f"{len(kayit['p5'])}/{len(pen)} pencere, simülasyon {sure['simulasyon_s']:.0f} s")
    n_goz_top = int(sum(kayit['n_gozlenen']))
    tt = t_testi(hedef_etas, hedef_pois, n_goz_top, toplam['etas'], toplam['pois'])
    tt_tum = t_testi(hedef_etas, hedef_tum, n_goz_top, toplam['etas'], toplam['tum'])
    bss = brier_beceri(kayit['p5'], kayit['taban5'], kayit['o5'])
    bss_tum = brier_beceri(kayit['p5'], kayit['tum5'], kayit['o5'])
    nt = n_testi(sim_toplam, n_goz_top)
    haftalik_gecen = float(np.mean([(a >= ALFA / 2) and (b >= ALFA / 2)
                                    for a, b in zip(kayit['nt_d1'], kayit['nt_d2'])])) if pen else None
    gecti = karar(tt, bss, haftalik_gecen) and all(md['durum'] != 'poisson' for md in modeller)
    return {
        'gecti': gecti, 't_testi': tt, 'brier_beceri': bss,
        'n_testi': {'haftalik_gecme': haftalik_gecen, 'esik': N_HAFTALIK_ESIK, 'toplam': nt},
        'brier': {'etas': brier(kayit['p5'], kayit['o5']), 'poisson': brier(kayit['taban5'], kayit['o5'])},
        'ek': {'t_testi_tum_poisson': tt_tum, 'brier_beceri_tum_poisson': bss_tum,
               'ortalama_p5': float(np.mean(kayit['p5'])) if pen else None,
               'ortalama_taban5': float(np.mean(kayit['taban5'])) if pen else None,
               'gozlenen_m5_hafta_orani': float(np.mean(kayit['o5'])) if pen else None,
               'gozlenen_m6_hafta': int(sum(kayit['o6'])),
               'toplam_m4': {'gozlenen': n_goz_top, 'etas_beklenen': float(toplam['etas']),
                             'poisson_beklenen': float(toplam['pois']),
                             'sim_ortanca': float(np.median(sim_toplam)),
                             'sim_5_95': [float(np.percentile(sim_toplam, 5)), float(np.percentile(sim_toplam, 95))]}},
        'kapsam': {'pencere': len(pen), 'simulasyon': n, 'yeniden_uyum': 'yıllık (1 Ocak)',
                   'bas': bas_dt.date().isoformat(),
                   'bit': datetime.fromtimestamp((pen[-1] + 7 * GUN_MS) / 1000, tz=UTC).date().isoformat() if pen else None,
                   'hucre_derece': HUCRE, 'hedef_m': hedef, 'mc': mc_eg, 'mc_mbs_ham': mc_ham, 'su_seviyesi': SU},
        'modeller': modeller, 'haftalar': kayit,
        'sure': {k: round(v, 1) for k, v in sure.items()},
    }


def _sayi(x, n=2):
    return '—' if x is None else f'{x:.{n}f}'.replace('.', ',').replace('-', '−')


def ozet(s):
    tt, nt = s['t_testi'], s['n_testi']
    k = s['kapsam']
    hg = nt['haftalik_gecme']
    return (f"{k['bas'][:4]}–{(k['bit'] or '')[:4]}, {k['pencere']} hafta: Poisson'a göre bilgi kazancı "
            f"{_sayi(tt['ig'])}/deprem (%95 {_sayi(tt['alt'])}…{_sayi(tt['ust'])}), Brier becerisi "
            f"{_sayi(s['brier_beceri'])}, haftalık N-testi geçme %{'—' if hg is None else round(100 * hg)} "
            f"(eşik %{round(100 * nt['esik'])}); {'geçti' if s['gecti'] else 'geçmedi'}")


def ana(argv=None):
    for akis in (sys.stdout, sys.stderr):
        if hasattr(akis, 'reconfigure'):
            akis.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description='ETAS sözde-ileriye dönük doğrulama')
    ap.add_argument('--onbellek', default=os.path.join(os.path.dirname(__file__), '.onbellek'))
    ap.add_argument('--kart-veri', default=None)
    ap.add_argument('--n', type=int, default=etas.SIMULASYON)
    ap.add_argument('--simdi', help='deneme: ISO zaman (UTC)')
    ap.add_argument('--pencere', type=int, default=None, help='indirgeme: en çok bu kadar pencere')
    ap.add_argument('--tohum', type=int, default=0)
    a = ap.parse_args(argv)
    simdi = datetime.fromisoformat(a.simdi).replace(tzinfo=UTC) if a.simdi else datetime.now(UTC)
    simdi_ms = etas._ms(simdi)
    olaylar = [o for o in kat.yukle(os.path.join(a.onbellek, 'tr.csv.gz')) if o['zaman_ms'] < simdi_ms]
    t = time.monotonic()
    s = calistir(olaylar, simdi_ms, n=a.n, tohum=a.tohum, pencere_sinir=a.pencere,
                 gunluk=lambda x: print(x, flush=True))
    s['sure']['toplam_s'] = round(time.monotonic() - t, 1)
    if a.pencere or a.n < etas.SIMULASYON:
        s['kapsam']['indirgeme'] = f'pencere sınırı {a.pencere}, simülasyon {a.n}'
    s['tarih'] = int(simdi_ms)
    s['surum'] = etas.MODEL_SURUM
    s['ozet'] = ozet(s)
    with open(os.path.join(a.onbellek, 'etas-dogrulama.json'), 'w', encoding='utf-8') as f:
        json.dump(s, f, ensure_ascii=False, indent=1)
    kv_yol = a.kart_veri or os.path.join(a.onbellek, 'kart-veri.json')
    kartveri.yaz(kv_yol, 'etasDogrulama', {k: s[k] for k in ('gecti', 'ozet', 'tarih', 'surum', 'kapsam')}
                 | {'olcutler': {'t_testi': s['t_testi'], 'brier_beceri': s['brier_beceri'], 'n_testi': s['n_testi']}})
    print('ÖZET', s['ozet'], s['sure'])
    return 0


if __name__ == '__main__':
    sys.exit(ana())
