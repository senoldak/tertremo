# Günlük hesap (GitHub Actions, her gece 03:00 UTC).
# Önbellek (Actions cache, csv.gz) → eksik günleri indir (Türkiye EMSC, dünya USGS) → her katalog için d_f, b, η, η0
# → kume, kume_param, hucre (+ bh_p) → D1.
#
# Ücretsiz plan bütçesi (D1: hesap geneli 5M okunan / 100k yazılan satır / gün):
# - Tam katalog yalnız önbellekte; D1'de yalnız son 400 gün.
# - D1'den tablo okunmaz: neyin değiştiği önceki gecenin çıktısıyla (önbellekteki d1_durum.json.gz) yerelde karşılaştırılır.
# - Gecelik yazım tavanı 20.000 satır (indeks satırları dahil tahmini ağırlık); aşılırsa en yeni olaylar önce.
#   Doldurma modu: son 400 günün D1'e yazılmamış (ve yazılabilir: kume'si hesaplanmış) olayı varsa tavan 40.000
#   (geçmiş ~6 gecede dolar). Pay: Worker ≈ 5–8k/gün + hesabın geri kalanı ≈ 15–25k/gün; 40k + Worker < 100k
#   günlük kotanın yarısı civarında kalır, eşzamanlı bir tamir/yeniden çalıştırmaya yer bırakır.
#   Aynı UTC gününde ikinci çalıştırma (elle deneme, yeniden çalıştırma) en çok 5.000 yazar: D1 kotası 00:00 UTC'de
#   sıfırlanır; 26 Ekim'de iki doldurma gecesi (03:01 + 22:08 UTC) 77k yazdı, hesap 100k'yı aştı.
# - kume_param eşikleri tolerans içinde kalırsa önceki değerler korunur: aksi halde d_f'nin her gece küçük oynaması
#   bütün kume satırlarını yeniden yazdırırdı.
import argparse
import bisect
import gzip
import json
import math
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

import numpy as np

from hesap import d1, etas
from hesap import kartblok, kartveri, olasilik, patlatma
from hesap import katalog as kat
from hesap.hucre import b_aki_utsu, hucre_anahtari, hucre_istatistik, mc_maxc
from hesap.kume import en_yakin_komsu, esik, korelasyon_boyutu, mesafe_km

GUN_MS = 86_400_000
SAKLA_GUN = 400
TAVAN = 20_000
TAVAN_DOLDURMA = 40_000
TAVAN_AYNI_GUN = 5_000
PARCA = 100
# D1 satır yazımı: her indeks ayrı satır sayılır. olay: tablo + PK + 6 indeks; kume: tablo + PK; hucre/kume_param upsert.
AG_OLAY = 8
AG_KUME = 2
AG_HUCRE = 2
AG_PARAM = 2
D_F_BANT = (1.0, 2.0)   # bant dışı d_f (küçük/kümeli örnek) → önceki ya da literatür 1,6
D_F_VARSAYILAN = 1.6
B_VARSAYILAN = 1.0
B_BANT = (0.6, 1.5)    # bant dışı katalog b'si (Mc yanlış seçimi belirtisi) → önceki ya da 1,0
TOLERANS = {'d_f': 0.05, 'b': 0.05, 'log_eta0': 0.1}
KAYNAK = {'tr': 'emsc', 'dunya': 'usgs'}
UTC = timezone.utc
BASLANGIC = {'tr': datetime(2018, 1, 1, tzinfo=UTC), 'dunya': datetime(2000, 1, 1, tzinfo=UTC)}
PARCA_GUN = {'tr': 31, 'dunya': 92}
ORTUSME_GUN = 3   # her gece son 3 gün yeniden indirilir (kaynak düzeltmeleri, silinen olaylar)
TEKIL_GUN = 2     # Worker'ın canlı kaydıyla çakışma yalnız son 2 gün için D1'den denetlenir
ZAMAN_MS = 60_000
MESAFE_KM = 50
MW_FARK = 0.7

SQL_OLAY = ('INSERT OR IGNORE INTO olay (id, zaman, enlem, boylam, derinlik, mw, buyukluk, tur, kaynak, kaynaklar, '
            'yer, katalog, tsunami, durum, eklendi, hucre1) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)')
SQL_KUME = ('INSERT INTO kume (olay_id, ebeveyn_id, log_eta) VALUES (?, ?, ?) '
            'ON CONFLICT(olay_id) DO UPDATE SET ebeveyn_id = excluded.ebeveyn_id, log_eta = excluded.log_eta')
SQL_HUCRE = ('INSERT INTO hucre (katalog, anahtar, mc, b, sigma_b, n, lambda, bh_p, hesap) '
             'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(katalog, anahtar) DO UPDATE SET mc = excluded.mc, '
             'b = excluded.b, sigma_b = excluded.sigma_b, n = excluded.n, lambda = excluded.lambda, '
             'bh_p = excluded.bh_p, hesap = excluded.hesap')
SQL_HUCRE_HESAP = 'UPDATE hucre SET hesap = ? WHERE katalog = ? AND anahtar IN ({})'
HESAP_PARCA = 98  # D1: ifade başına en çok 100 bağlı parametre
SQL_PARAM = ('INSERT INTO kume_param (katalog, d_f, b, log_eta0, hesap) VALUES (?, ?, ?, ?, ?) '
             'ON CONFLICT(katalog) DO UPDATE SET d_f = excluded.d_f, b = excluded.b, '
             'log_eta0 = excluded.log_eta0, hesap = excluded.hesap')
SQL_SIL_KUME = 'DELETE FROM kume WHERE olay_id IN (SELECT id FROM olay INDEXED BY olay_zaman WHERE zaman < ?)'
SQL_SIL_OLAY = 'DELETE FROM olay WHERE zaman < ?'
SQL_GUN = ("SELECT id, zaman, enlem, boylam, mw, kaynaklar FROM olay INDEXED BY olay_katalog_zaman "
           "WHERE katalog IN ('tr', 'dunya') AND zaman >= ? AND zaman < ?")


@dataclass
class Is:
    """D1'e yazılacak bir iş: tahmini satır yazımı, sıralama zamanı (None = öncelikli), ifadeler, durum güncellemesi."""
    agirlik: int
    zaman: Optional[float]
    ifadeler: list = field(default_factory=list)
    guncelle: Optional[Callable] = None


def bos_durum():
    return {'olay': {}, 'esles': {}, 'kume': {}, 'hucre': {}, 'param': {}, 'son_calisma': None}


# ---------- yardımcılar ----------

def katalogu(enlem, boylam):
    """src/bolge.js katalogu: Türkiye kutusu (35,5–42,5 K, 25,5–45 D) + 2°."""
    return 'tr' if 33.5 <= enlem <= 44.5 and 23.5 <= boylam <= 47 else 'dunya'


def _ms(dt):
    return dt.timestamp() * 1000


def _dt(ms):
    return datetime.fromtimestamp(ms / 1000, tz=UTC)


def _yuvarla(x, n):
    return None if x is None or not math.isfinite(x) else round(float(x), n)


def olay_satiri(o, kaynak, simdi):
    ham = o['id'].split(':', 1)[1]
    zaman = round(o['zaman_ms'])
    kayit = {'id': ham, 'buyukluk': o['buyukluk'], 'tur': o['tur'], 'zaman': zaman, 'mw': o['mw']}
    return {
        'id': o['id'], 'zaman': zaman, 'enlem': o['enlem'], 'boylam': o['boylam'],
        'derinlik': o['derinlik'], 'mw': o['mw'], 'buyukluk': o['buyukluk'], 'tur': o['tur'], 'kaynak': kaynak,
        'kaynaklar': json.dumps({kaynak: kayit}, separators=(',', ':'), ensure_ascii=False),
        'yer': o.get('yer'), 'katalog': katalogu(o['enlem'], o['boylam']), 'tsunami': 0, 'durum': 'islendi',
        'eklendi': int(simdi), 'hucre1': hucre_anahtari(o['enlem'], o['boylam'], 'tr'),
    }


def _olay_params(s):
    return [s[c] for c in ('id', 'zaman', 'enlem', 'boylam', 'derinlik', 'mw', 'buyukluk', 'tur', 'kaynak',
                           'kaynaklar', 'yer', 'katalog', 'tsunami', 'durum', 'eklendi', 'hucre1')]


def _kume_ayni(a, b):
    if a is None or b is None:
        return False
    return a[0] == b[0] and _yuvarla(a[1], 3) == _yuvarla(b[1], 3)


def kume_farki(onceki, yeni):
    """Yalnız (ebeveyn_id, log_eta 3 basamak) değişen ya da yeni satırlar."""
    return {k: v for k, v in yeni.items() if not _kume_ayni(onceki.get(k), v)}


def birikim(olaylar, durum, simdi, yazilabilir=None):
    """Son 400 günün D1'e henüz yazılmamış (ne kendi kimliğiyle ne eşleşmeyle) katalog olayı sayısı. yazilabilir
    verilirse yalnız o kimlikler (kume'si hesaplanmış olaylar) sayılır: eşiği kurulamayan bir katalog hiçbir olayını
    yazamaz, onun olayları doldurma modunu sonsuza dek açık tutmasın."""
    sinir = simdi - SAKLA_GUN * GUN_MS
    return sum(1 for o in olaylar
               if o['zaman_ms'] >= sinir and o['id'] not in durum['olay'] and o['id'] not in durum['esles']
               and (yazilabilir is None or o['id'] in yazilabilir))


def ayni_utc_gunu(onceki_ms, simdi):
    return onceki_ms is not None and int(onceki_ms) // GUN_MS == int(simdi) // GUN_MS


def mod_sec(birikim_sayisi, tavan=None, ayni_gun=False):
    """(mod, tavan): birikim varsa 'doldurma' 40.000, yoksa 'normal' 20.000; aynı UTC gününde ikinci çalıştırma
    en çok 5.000. Elle verilen tavan önceliklidir."""
    mod = 'doldurma' if birikim_sayisi > 0 else 'normal'
    if tavan is None:
        tavan = TAVAN_DOLDURMA if mod == 'doldurma' else TAVAN
        if ayni_gun:
            tavan = min(tavan, TAVAN_AYNI_GUN)
    return mod, tavan


def tavanla(oncelikli, isler, tavan=TAVAN):
    """Öncelikli işler önce, sonra en yeni olay önce; toplam ağırlık tavanı aşmaz. (seçilen, kalan_sayısı)."""
    secilen, toplam, kalan = [], 0, 0
    for i in oncelikli:
        if toplam + i.agirlik <= tavan:
            secilen.append(i)
            toplam += i.agirlik
        else:
            kalan += 1
    dolu = False
    for i in sorted(isler, key=lambda i: i.zaman, reverse=True):
        if not dolu and toplam + i.agirlik <= tavan:
            secilen.append(i)
            toplam += i.agirlik
        else:
            dolu = True
            kalan += 1
    return secilen, kalan


def ayni_olay(o, s):
    """src/katalog.js ayniOlay: |Δt| ≤ 60 s, ≤ 50 km, |ΔMw| ≤ 0,7."""
    if s.get('mw') is None or s.get('zaman') is None:
        return False
    return (abs(o['zaman_ms'] - s['zaman']) <= ZAMAN_MS
            and float(mesafe_km(o['enlem'], o['boylam'], s['enlem'], s['boylam'])) <= MESAFE_KM
            and abs(o['mw'] - s['mw']) <= MW_FARK + 1e-9)


def tekillestir(olaylar, satirlar):
    """Katalog olayı → D1'deki aynı olayın kimliği (Worker birlestir kuralı: önce aynı kaynak kimliği, sonra o
    kaynağı henüz taşımayan en yakın zamanlı ayniOlay eşleşmesi)."""
    satirlar = sorted(satirlar, key=lambda s: s['zaman'])
    zamanlar = [s['zaman'] for s in satirlar]
    kimlik = {s['id']: s for s in satirlar}
    kaynaklar = {}
    kaynak_kimlik = {}
    for s in satirlar:
        try:
            k = json.loads(s.get('kaynaklar') or '{}')
        except ValueError:
            k = {}
        kaynaklar[s['id']] = set(k) if isinstance(k, dict) else set()
        for ad, kayit in (k.items() if isinstance(k, dict) else []):
            if isinstance(kayit, dict) and kayit.get('id') is not None:
                kaynak_kimlik[(ad, str(kayit['id']))] = s
    esles = {}
    for o in sorted(olaylar, key=lambda o: o['zaman_ms']):
        kaynak, ham = o['id'].split(':', 1)
        if o['id'] in kimlik:
            esles[o['id']] = o['id']
            continue
        en = kaynak_kimlik.get((kaynak, ham))
        if en is None:
            i0 = bisect.bisect_left(zamanlar, o['zaman_ms'] - ZAMAN_MS)
            i1 = bisect.bisect_right(zamanlar, o['zaman_ms'] + ZAMAN_MS)
            for s in satirlar[i0:i1]:
                if kaynak in kaynaklar[s['id']] or not ayni_olay(o, s):
                    continue
                if en is None or abs(s['zaman'] - o['zaman_ms']) < abs(en['zaman'] - o['zaman_ms']):
                    en = s
        if en is not None:
            esles[o['id']] = en['id']
            kaynaklar[en['id']].add(kaynak)
    return esles


# ---------- D1 iş planı ----------

def olay_kume_isleri(olaylar, kume, durum, kaynak, simdi):
    """Son 400 gün: D1'de olmayan olaylar (olay + kume) ve kume'si değişen olaylar."""
    sinir = simdi - SAKLA_GUN * GUN_MS
    esles = durum['esles']
    isler = []
    for o in olaylar:
        if o['zaman_ms'] < sinir or o['id'] not in kume:
            continue
        cid = o['id']
        did = esles.get(cid, cid)
        eb, le = kume[cid]
        yeni = [esles.get(eb, eb) if eb else None, _yuvarla(le, 3)]
        d1de = cid in durum['olay'] or cid in esles
        kume_ifade = (SQL_KUME, [did, yeni[0], yeni[1]])
        if not d1de:
            def g(d, cid=cid, did=did, yeni=yeni, z=o['zaman_ms']):
                d['olay'][cid] = z
                d['kume'][did] = yeni
            isler.append(Is(AG_OLAY + AG_KUME, o['zaman_ms'],
                            [(SQL_OLAY, _olay_params(olay_satiri(o, kaynak, simdi))), kume_ifade], g))
        elif not _kume_ayni(durum['kume'].get(did), yeni):
            def g(d, did=did, yeni=yeni):
                d['kume'][did] = yeni
            isler.append(Is(AG_KUME, o['zaman_ms'], [kume_ifade], g))
    return isler


def hucre_degeri(s):
    return [_yuvarla(s['mc'], 2), _yuvarla(s['b'], 3), _yuvarla(s['sigma_b'], 3), int(s['n']),
            _yuvarla(s['lambda'], 4), _yuvarla(s['bh_p'], 4)]


def hucre_isleri(katalog, hucreler, durum, simdi):
    isler, degismeyen = [], []
    for s in hucreler:
        anahtar = f"{katalog}|{s['anahtar']}"
        deger = hucre_degeri(s)
        if durum['hucre'].get(anahtar) == deger:
            degismeyen.append(s['anahtar'])
            continue

        def g(d, anahtar=anahtar, deger=deger):
            d['hucre'][anahtar] = deger
        isler.append(Is(AG_HUCRE, None, [(SQL_HUCRE, [katalog, s['anahtar'], *deger, int(simdi)])], g))
    # Değeri aynı kalan hücrelerin yalnız hesap zamanı tazelenir (Worker 48 saatten eskiyi bayat sayar). Adla:
    # tavan bir upsert'i dışarıda bırakırsa o satırın eski değeri taze hesap zamanıyla görünmesin.
    for i in range(0, len(degismeyen), HESAP_PARCA):
        parca = degismeyen[i:i + HESAP_PARCA]
        sql = SQL_HUCRE_HESAP.format(','.join('?' * len(parca)))
        isler.append(Is(len(parca), None, [(sql, [int(simdi), katalog, *parca])], None))
    return isler


def param_isi(katalog, p, simdi):
    def g(d):
        d['param'][katalog] = {k: p[k] for k in ('d_f', 'b', 'log_eta0')}
    return Is(AG_PARAM, None, [(SQL_PARAM, [katalog, p['d_f'], p['b'], p['log_eta0'], int(simdi)])], g)


def silme_isi(durum, kat_zaman, simdi):
    sinir = int(simdi - SAKLA_GUN * GUN_MS)
    tahmin = sum(1 for z in durum['olay'].values() if z < sinir)
    tahmin += sum(1 for c in durum['esles'] if kat_zaman.get(c, 0) < sinir)

    def g(d):
        d['olay'] = {k: z for k, z in d['olay'].items() if z >= sinir}
        d['esles'] = {c: i for c, i in d['esles'].items() if kat_zaman.get(c, 0) >= sinir}
        canli = set(d['olay']) | set(d['esles'].values())
        d['kume'] = {k: v for k, v in d['kume'].items() if k in canli}
    return Is(max(1, tahmin) * (AG_OLAY + AG_KUME), None,
              [(SQL_SIL_KUME, [sinir]), (SQL_SIL_OLAY, [sinir])], g), tahmin


def uygula(secilen, durum):
    """İşleri 100 ifadelik REST çağrılarıyla gönderir; her başarılı çağrıdan sonra durum güncellenir."""
    parca, parca_isler = [], []

    def gonder():
        if parca:
            d1.toplu(parca)
            for i in parca_isler:
                if i.guncelle:
                    i.guncelle(durum)
        parca.clear()
        parca_isler.clear()

    for i in secilen:
        if len(parca) + len(i.ifadeler) > PARCA:
            gonder()
        parca.extend(i.ifadeler)
        parca_isler.append(i)
    gonder()


# ---------- katalog ----------

def katalog_tamamla(ad, olaylar, meta, simdi_dt, bitis, ilk_baslangic):
    """Önbellekteki katalogu bugüne tamamlar (bütçe dolarsa yarım bırakır). Tamamlandıysa True."""
    m = meta.setdefault(ad, {})
    if m.get('tamam') is None:
        m['bas'] = _ms(ilk_baslangic)
        bas = ilk_baslangic
    else:
        bas = min(_dt(m['tamam']), simdi_dt - timedelta(days=ORTUSME_GUN))
    indir = kat.emsc_indir if ad == 'tr' else kat.usgs_indir
    while bas < simdi_dt:
        if time.monotonic() > bitis:
            return False
        bit = min(bas + timedelta(days=PARCA_GUN[ad]), simdi_dt)
        yeni = [o for o in indir(bas, bit) if katalogu(o['enlem'], o['boylam']) == ad]
        b0, b1 = _ms(bas), _ms(bit)
        for k in [k for k, o in olaylar.items() if b0 <= o['zaman_ms'] < b1]:
            del olaylar[k]
        for o in yeni:
            olaylar[o['id']] = o
        m['tamam'] = b1
        bas = bit
    return True


def _oku_json(yol, varsayilan):
    if not os.path.exists(yol):
        return varsayilan
    with gzip.open(yol, 'rt', encoding='utf-8') as f:
        return json.load(f)


def _yaz_json(yol, veri):
    gecici = yol + '.tmp'
    with gzip.open(gecici, 'wt', encoding='utf-8') as f:
        json.dump(veri, f, separators=(',', ':'))
    os.replace(gecici, yol)


# ---------- hesap ----------

def sabitle(onceki, yeni):
    """Önceki değerler tolerans içindeyse onları korur. (değerler, değişti_mi)."""
    if onceki and all(k in onceki for k in yeni) and all(abs(yeni[k] - onceki[k]) < TOLERANS[k] for k in yeni):
        return {k: onceki[k] for k in yeni}, False
    return dict(yeni), True


def katalog_mc(ad, z, m):
    """Katalog geneli tamlık Mc'si (b, NN kümeleme ve hücre tabanı), MBS ile (etas.mc_mbs, aynı sabitler).
    Türkiye: ETAS zinciriyle aynı eğitim penceresi (2018–2021, etas.mc_egitim): kayan bütün-katalog MBS'si her gece
    4,0 ↔ 4,1 oynar ve b'yi tolerans dışına iter. Dünya: katalogun tamamı; USGS M ≥ 4,5 kesimli, n ~186 bin → σ_b çok küçük, ölçüt
    b'nin yavaş kaymasını (mb → Mw, 1,16 → 1,0) reddeder ve MBS bulamaz → pratikte MAXC (4,7; b 1,14). MAXC yalnız MBS hiçbir aday bulamazsa
    yedek: heterojen EMSC kutusunda MAXC (2,2) tamlığın altında kalır ve b'yi ≈ 0,68'e çeker (tamlıkta ≈ 1,1).
    Dönüş: (Mc, 'MBS' | 'MAXC')."""
    mbs = etas.mc_egitim(z, m)[1] if ad == 'tr' else etas.mc_mbs(m)
    if math.isfinite(mbs):
        return mbs, 'MBS'
    print(f'UYARI {ad}: MBS Mc bulunamadı; MAXC yedeği kullanıldı')
    return mc_maxc(m), 'MAXC'


def bagimsiz_maske(ad, z, e, bo, m, mc, onceki_param):
    """Patlatma testi için ön kümeleme: bütün katalogda NN, ebeveynsiz (log η ≥ eşik) olaylar → bool dizi.
    Parametreler önceki geceden (d_f, b, log_eta0) varsa onlar; yoksa bu katalogdan kestirilir. Eşik kurulamazsa None (test bütün küçük olaylarla)."""
    op = onceki_param or {}
    if all(k in op for k in ('d_f', 'b', 'log_eta0')):
        d_f, b, le0 = op['d_f'], op['b'], op['log_eta0']
        _, log_eta = en_yakin_komsu(z, e, bo, m, d_f, b, ad)
    else:
        d_f = korelasyon_boyutu(e, bo)
        d_f = d_f if D_F_BANT[0] <= d_f <= D_F_BANT[1] else op.get('d_f', D_F_VARSAYILAN)
        b, _ = b_aki_utsu(m, mc)
        b = b if math.isfinite(b) and B_BANT[0] <= b <= B_BANT[1] else op.get('b', B_VARSAYILAN)
        _, log_eta = en_yakin_komsu(z, e, bo, m, d_f, b, ad)
        le0 = esik(log_eta)
        if not math.isfinite(le0):
            return None
    return ~(log_eta < le0)


def hesapla(ad, olaylar, onceki_param, baslangic_ms, simdi):
    olaylar = sorted(olaylar, key=lambda o: o['zaman_ms'])
    ids = [o['id'] for o in olaylar]
    z = np.array([o['zaman_ms'] for o in olaylar])
    e = np.array([o['enlem'] for o in olaylar])
    bo = np.array([o['boylam'] for o in olaylar])
    m = np.array([o['mw'] for o in olaylar])
    mc, mc_kaynak = katalog_mc(ad, z, m)   # Mc: bütün katalogla (ETAS zinciriyle aynı tanım)
    # patlatma imzası (hesap/patlatma.py): bayraklı 1° hücrenin M < 3,5 olayları b/λ/baz ve NN uyumundan düşer (yalnız Türkiye)
    bayrak, p0, n_test = ({}, math.nan, 0)
    if ad == 'tr':
        son = z >= baslangic_ms
        bag = bagimsiz_maske(ad, z, e, bo, m, mc, onceki_param)   # artçı koruması: test bağımsız olaylarla (hesap/patlatma.py)
        bayrak, p0, n_test = patlatma.bayrakli(z[son], e[son], bo[son], m[son], ad,
                                               bagimsiz=None if bag is None else bag[son])
    at = patlatma.ayiklama_maskesi(z, e, bo, m, bayrak, ad)
    ids_tum = ids
    if at.any():
        tut = ~at
        ids, z, e, bo, m = [i for i, t in zip(ids, tut) if t], z[tut], e[tut], bo[tut], m[tut]
    d_f = korelasyon_boyutu(e, bo)
    b, _ = b_aki_utsu(m, mc)
    d_f_ham, b_ham = d_f, b
    if not (D_F_BANT[0] <= d_f <= D_F_BANT[1]):
        d_f = (onceki_param or {}).get('d_f', D_F_VARSAYILAN)
        print(f'UYARI {ad}: d_f {d_f_ham:.3f} [{D_F_BANT[0]}, {D_F_BANT[1]}] dışında; {d_f} kullanıldı')
    if not math.isfinite(b):
        b = (onceki_param or {}).get('b', B_VARSAYILAN)
        print(f'UYARI {ad}: b hesaplanamadı; {b} kullanıldı')
    elif not (B_BANT[0] <= b <= B_BANT[1]):
        b = (onceki_param or {}).get('b', B_VARSAYILAN)
        print(f'UYARI {ad}: b {b_ham:.3f} [{B_BANT[0]}, {B_BANT[1]}] dışında (Mc {mc}, {mc_kaynak}); {b} kullanıldı')
    p, degisti = sabitle(onceki_param, {'d_f': round(d_f, 3), 'b': round(b, 3)})
    ebeveyn, log_eta = en_yakin_komsu(z, e, bo, m, p['d_f'], p['b'], ad)
    eta0 = esik(log_eta)
    param_yaz = True
    if not math.isfinite(eta0):
        # az veri: eşik kurulamadı → önceki log_eta0 korunur, kume_param yazılmaz; önceki yoksa katalog atlanır
        print(f'UYARI {ad}: log η eşiği için yeterli veri yok (< 20)')
        if not onceki_param or 'log_eta0' not in onceki_param:
            return None, {}, [], {'n': len(ids), 'param_yaz': False}
        p = {k: onceki_param[k] for k in ('d_f', 'b', 'log_eta0')}
        ebeveyn, log_eta = en_yakin_komsu(z, e, bo, m, p['d_f'], p['b'], ad)
        param_yaz = False
    elif degisti or not onceki_param or 'log_eta0' not in onceki_param:
        p['log_eta0'] = round(eta0, 3)
    else:
        p['log_eta0'] = sabitle({'log_eta0': onceki_param['log_eta0']}, {'log_eta0': round(eta0, 3)})[0]['log_eta0']
    bagli = log_eta < p['log_eta0']
    kume = {}
    for i, cid in enumerate(ids):
        le = float(log_eta[i])
        kume[cid] = [ids[ebeveyn[i]] if bagli[i] else None, round(le, 3) if math.isfinite(le) else None]
    for cid in ids_tum:   # hesaptan düşenler (patlatma imzalı hücrede küçük olay): ebeveynsiz, η yok
        kume.setdefault(cid, [None, None])
    hucreler = hucre_istatistik(z, e, bo, m, ~bagli, ad, baslangic_ms, simdi, mc_katalog=mc)
    for s in hucreler:
        if s['anahtar'] in bayrak:
            s['patlatma'] = True
    ozet = {'n': len(ids), 'd_f_ham': round(d_f_ham, 3), 'b_ham': round(b_ham, 3), 'mc': mc, 'mc_kaynak': mc_kaynak,
            'log_eta0_ham': round(eta0, 3) if math.isfinite(eta0) else None, 'param_yaz': param_yaz,
            'bagli': int(bagli.sum()), 'hucre': len(hucreler),
            'patlatma': {'p0': None if not math.isfinite(p0) else round(p0, 4), 'test': n_test, 'hucreler': bayrak,
                         'ayiklanan': int(at.sum())},
            'anlamli': sum(1 for s in hucreler if s['bh_p'] is not None and s['bh_p'] < 0.05)}
    return p, kume, hucreler, ozet


# ---------- kart verisi ----------

def kart_verisi(onbellek, olaylar_tr, hucreler_tr, bas_ms, simdi, kume_tr=None, b_tr=None, mc_tr=None, patlatma_ozeti=None):
    """Dönemsel kartların girdisi: hesap/.onbellek/kart-veri.json 'gr' (son ayın G–R bloğu) ve 'hucreler'
    (b ve λ haritaları; hucre tablosuyla aynı değerler). Kart verisi D1 gecesini asla düşürmez: hata yalnız uyarıdır."""
    yol = os.path.join(onbellek, 'kart-veri.json')
    parcalar = {}
    ay_bas, ay_bit, ay = kartblok.ay_araligi(simdi)
    # G–R: son 12 ay (önceki ayın sonuna kadar), katalog Mc'sinin (MBS) üstünde; kart başlığında ay korunur
    if mc_tr is None:
        tum = sorted(olaylar_tr, key=lambda o: o['zaman_ms'])
        mc_tr = katalog_mc('tr', np.array([o['zaman_ms'] for o in tum]), np.array([o['mw'] for o in tum]))[0] if tum else math.nan
    mw_12 = [o['mw'] for o in olaylar_tr if ay_bit - 365.25 * GUN_MS <= o['zaman_ms'] < ay_bit]
    parcalar['gr'] = kartblok.gr_blogu(mw_12, ay, mc_tr)
    parcalar['hucreler'] = kartblok.hucre_blogu(hucreler_tr, simdi, bas_ms, b_tr, patlatma_ozeti)
    parcalar['patlatma'] = patlatma_ozeti   # bayraklı hücreler yalnız burada (D1'de sütun yok); kartlarda ad verilmez
    kartveri.guncelle(yol, parcalar)
    if kume_tr:
        # Kart 19: uzun dönem olasılık; bağımsız olay = bu gecenin kümelemesinde ebeveyni olmayan (hesapla'nın `kume`si)
        try:
            tr = sorted((o for o in olaylar_tr if o['id'] in kume_tr), key=lambda o: o['zaman_ms'])
            z, e, bo, m = (np.array([o[k] for o in tr], float) for k in ('zaman_ms', 'enlem', 'boylam', 'mw'))
            bagimsiz = np.array([kume_tr[o['id']][0] is None for o in tr], bool)
            olasilik.uzun_katalog_guncelle(os.path.join(onbellek, 'uzun-katalog.json'))   # ağ hatası yalnız uyarı; taban/önbellek kullanılır
            uzun = olasilik.uzun_katalog_yukle(onbellek=os.path.join(onbellek, 'uzun-katalog.json'))
            parcalar['uzunDonem'] = olasilik.uzun_donem_blogu(z, e, bo, m, bagimsiz, simdi, uzun=uzun)
            kartveri.guncelle(yol, {'uzunDonem': parcalar['uzunDonem']})
        except Exception as h:
            print(f'UYARI uzun dönem olasılığı hesaplanamadı: {type(h).__name__}: {h}', file=sys.stderr)
    return parcalar


# ---------- D1 tekilleştirme ----------

def d1_tekillestir(tum, durum, simdi):
    bilinen = set(durum['olay']) | set(durum['esles'])
    if durum['son_calisma'] is None:
        r = d1.sorgu('SELECT MIN(zaman) AS m FROM olay')
        enk = r[0].get('m') if r else None
        if enk is None:
            return 0, 0
        bas = max(enk, simdi - SAKLA_GUN * GUN_MS)
    else:
        bas = min(simdi - TEKIL_GUN * GUN_MS, durum['son_calisma'] - GUN_MS)
    bas = (int(bas) // GUN_MS) * GUN_MS
    aday = [o for o in tum if o['zaman_ms'] >= bas and o['id'] not in bilinen]
    if not aday:
        return 0, 0
    gunler = range(bas, int(simdi) + GUN_MS, GUN_MS)
    satirlar = {}
    for sonuc in d1.toplu([(SQL_GUN, [g - ZAMAN_MS, g + GUN_MS + ZAMAN_MS]) for g in gunler]):
        for s in sonuc:
            satirlar[s['id']] = s
    esles = tekillestir(aday, list(satirlar.values()))
    zaman = {o['id']: o['zaman_ms'] for o in aday}
    for cid, did in esles.items():
        if cid == did:
            durum['olay'][cid] = zaman[cid]
        else:
            durum['esles'][cid] = did
    return len(gunler), len(esles)


def okuma_tahmini(tum, simdi, tekil_gun, hucre_sayisi, yazilacak_ifade):
    """Gecelik okunan satır tahmini: gün sorguları (Worker'ın fazladan küçük olaylarıyla ×2), silinecek eski satırlar,
    hucre hesap güncellemesi, her yazım ifadesi için ~1."""
    son30 = sum(1 for o in tum if o['zaman_ms'] >= simdi - 30 * GUN_MS) / 30
    return int(tekil_gun * son30 * 2 + 2 * son30 * 2 + hucre_sayisi + yazilacak_ifade)


# ---------- ana akış ----------

def ana(argv=None):
    for akis in (sys.stdout, sys.stderr):
        if hasattr(akis, 'reconfigure'):
            akis.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description='tertremo günlük hesap')
    ap.add_argument('--kuru', action='store_true', help='D1\'e yazmadan her şeyi yap, sayıları yazdır')
    ap.add_argument('--onbellek', default=os.path.join(os.path.dirname(__file__), '.onbellek'))
    ap.add_argument('--butce', type=float, default=540, help='indirme süresi bütçesi (s)')
    ap.add_argument('--tavan', type=int, default=None, help='vars.: doldurma 40.000, normal 20.000')
    ap.add_argument('--tr-baslangic', help='ilk çalıştırma: Türkiye katalog başlangıcı (YYYY-AA-GG)')
    ap.add_argument('--dunya-baslangic', help='ilk çalıştırma: dünya katalog başlangıcı (YYYY-AA-GG)')
    a = ap.parse_args(argv)
    t0 = time.monotonic()
    simdi_dt = datetime.now(UTC).replace(microsecond=0)
    simdi = _ms(simdi_dt)
    os.makedirs(a.onbellek, exist_ok=True)
    yol = {ad: os.path.join(a.onbellek, f'{ad}.csv.gz') for ad in KAYNAK}
    meta_yol = os.path.join(a.onbellek, 'meta.json.gz')
    durum_yol = os.path.join(a.onbellek, 'd1_durum.json.gz')
    meta = _oku_json(meta_yol, {})
    durum = {**bos_durum(), **_oku_json(durum_yol, {})}
    ilk = {
        'tr': datetime.fromisoformat(a.tr_baslangic).replace(tzinfo=UTC) if a.tr_baslangic else BASLANGIC['tr'],
        'dunya': datetime.fromisoformat(a.dunya_baslangic).replace(tzinfo=UTC) if a.dunya_baslangic
        else BASLANGIC['dunya'],
    }

    # 1) katalog
    olaylar, tamam, hata = {}, {}, None
    for ad in KAYNAK:
        olaylar[ad] = {o['id']: o for o in kat.yukle(yol[ad])}
        once = len(olaylar[ad])
        try:
            tamam[ad] = katalog_tamamla(ad, olaylar[ad], meta, simdi_dt, t0 + a.butce, ilk[ad])
        except (kat.KaynakHatasi, OSError) as h:  # URLError/HTTPError OSError alt sınıfı
            # tamamlanan parçalar tutarlı: önbelleğe yazılır, ama D1'e hiçbir şey yazılmaz
            hata = f'{ad}: {type(h).__name__}: {h}'
            tamam[ad] = False
        kat.kaydet(yol[ad], olaylar[ad].values())
        print(f'katalog {ad}: {len(olaylar[ad])} olay ({len(olaylar[ad]) - once:+d}), '
              f"tamam {_dt(meta[ad]['tamam']).isoformat() if meta[ad].get('tamam') else '-'}"
              f"{'' if tamam[ad] else ' (YARIM)'}")
    _yaz_json(meta_yol, meta)
    if hata:
        print(f'HATA: kaynak indirilemedi ({hata}); D1 yazımı yok', file=sys.stderr)
        return 1
    if not all(tamam.values()):
        print('ÖZET katalog yarım (indirme bütçesi doldu), sonraki gece sürecek; D1 yazımı yok')
        return 0

    # 2) hesap
    sonuc = {}
    for ad in KAYNAK:
        t1 = time.monotonic()
        bas = max(_ms(BASLANGIC[ad]), meta[ad].get('bas', _ms(BASLANGIC[ad])))
        p, kume, hucreler, ozet = hesapla(ad, list(olaylar[ad].values()), durum['param'].get(ad), bas, simdi)
        sonuc[ad] = (p, kume, hucreler, ozet['param_yaz'], ozet.get('patlatma'))
        if p is None:
            print(f"hesap {ad}: n={ozet['n']} — eşik yok, bu katalog için D1 yazımı yok")
            continue
        print(f"hesap {ad}: n={ozet['n']} Mc={ozet['mc']} d_f={p['d_f']} (ham {ozet['d_f_ham']}) "
              f"b={p['b']} (ham {ozet['b_ham']}) log_eta0={p['log_eta0']} (ham {ozet['log_eta0_ham']}) "
              f"bağlı={ozet['bagli']} hücre={ozet['hucre']} BH anlamlı={ozet['anlamli']} "
              f"patlatma bayrak={len(ozet['patlatma']['hucreler'])}/{ozet['patlatma']['test']} ayıklanan={ozet['patlatma']['ayiklanan']} "
              f'({time.monotonic() - t1:.1f} s)')

    # kart verisi (D1'den bağımsız; hata gece işini düşürmez)
    try:
        bas_tr = max(_ms(BASLANGIC['tr']), meta['tr'].get('bas', _ms(BASLANGIC['tr'])))
        kv = kart_verisi(a.onbellek, list(olaylar['tr'].values()), sonuc['tr'][2], bas_tr, simdi, sonuc['tr'][1],
                        (sonuc['tr'][0] or {}).get('b'), patlatma_ozeti=sonuc['tr'][4])
        print(f"kart verisi: gr {'yok' if kv['gr'] is None else kv['gr']['ay']}, hücre {len(kv['hucreler']['hucreler'])}, "
              f"uzunDonem {'var' if 'uzunDonem' in kv else 'yok'}")
    except Exception as h:
        print(f'UYARI kart verisi yazılamadı: {type(h).__name__}: {h}', file=sys.stderr)

    # 3) D1
    tum = [o for ad in KAYNAK for o in olaylar[ad].values()]
    tekil_gun = TEKIL_GUN + 1
    if d1.hazir():
        tekil_gun, n_esles = d1_tekillestir(tum, durum, simdi)
        print(f'tekilleştirme: {tekil_gun} gün sorgusu, {n_esles} eşleşme')
    else:
        # Sırlar henüz tanımlı değilse katalog yine önbellekte birikir; D1'e yazılmaz (kuru gibi)
        if not a.kuru:
            print('UYARI: CF_D1_TOKEN / CF_HESAP / D1_ID tanımlı değil; D1 yazımı yok (kuru)', file=sys.stderr)
            a.kuru = True
        print('tekilleştirme atlandı (sır yok)')
    kat_zaman = {o['id']: o['zaman_ms'] for o in tum}
    oncelikli = [param_isi(ad, sonuc[ad][0], simdi) for ad in KAYNAK if sonuc[ad][3]]
    for ad in KAYNAK:
        oncelikli += hucre_isleri(ad, sonuc[ad][2], durum, simdi)
    sil, sil_tahmin = silme_isi(durum, kat_zaman, simdi)
    oncelikli.append(sil)
    isler = []
    for ad in KAYNAK:
        isler += olay_kume_isleri(list(olaylar[ad].values()), sonuc[ad][1], durum, KAYNAK[ad], simdi)
    yazilabilir = {cid for ad in KAYNAK for cid in sonuc[ad][1]}
    bekleyen = birikim(tum, durum, simdi, yazilabilir)
    mod, tavan = mod_sec(bekleyen, a.tavan, ayni_gun=ayni_utc_gunu(durum['son_calisma'], simdi))
    a.tavan = tavan
    secilen, kalan = tavanla(oncelikli, isler, a.tavan)
    yeni = {ad: 0 for ad in KAYNAK}
    kume_yaz = hucre_yaz = 0
    for i in secilen:
        for s, p in i.ifadeler:
            if s is SQL_OLAY:
                yeni['tr' if p[0].startswith('emsc:') else 'dunya'] += 1
            elif s is SQL_KUME:
                kume_yaz += 1
            elif s is SQL_HUCRE:
                hucre_yaz += 1
            elif s.startswith('UPDATE hucre SET hesap'):
                hucre_yaz += i.agirlik
    agirlik = sum(i.agirlik for i in secilen)
    mod_metni = f'mod: {mod} (yazılmamış {bekleyen}, bu gece sonrası kalan {bekleyen - sum(yeni.values())})'
    ifade = sum(len(i.ifadeler) for i in secilen)
    tahmin_okuma = okuma_tahmini(tum, simdi, tekil_gun, sum(len(sonuc[ad][2]) for ad in KAYNAK), ifade)
    if a.kuru:
        print(f"ÖZET (kuru) {mod_metni}, yeni olay {sum(yeni.values())} (tr {yeni['tr']}, dunya {yeni['dunya']}), "
              f'kume yazımı {kume_yaz}, hucre yazımı {hucre_yaz}, silme tahmini {sil_tahmin}, '
              f'tavan dışı kalan {kalan}, yazım ağırlığı {agirlik}/{a.tavan}, {ifade} ifade '
              f'({math.ceil(ifade / PARCA)} REST çağrısı), okunan satır tahmini {tahmin_okuma}')
        return 0
    try:
        uygula(secilen, durum)
        durum['son_calisma'] = simdi
    finally:
        _yaz_json(durum_yol, durum)
    print(f"ÖZET {mod_metni}, yeni olay {sum(yeni.values())} (tr {yeni['tr']}, dunya {yeni['dunya']}), kume yazımı {kume_yaz}, "
          f'hucre yazımı {hucre_yaz}, silme tahmini {sil_tahmin}, tavan dışı kalan {kalan}, '
          f"yazım ağırlığı {agirlik}/{a.tavan}, D1 okunan {d1.sayac['okunan']} / yazılan {d1.sayac['yazilan']} "
          f"({d1.sayac['istek']} REST çağrısı), okunan tahmini {tahmin_okuma}")
    return 0


if __name__ == '__main__':
    try:
        sys.exit(ana())
    except d1.D1Hatasi as h:
        print(f'HATA: {h}', file=sys.stderr)
        sys.exit(1)
