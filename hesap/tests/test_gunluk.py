import json

import numpy as np
import pytest

from hesap import gunluk
from hesap.gunluk import Is, kume_farki, olay_satiri, tavanla, tekillestir

GUN_MS = 86_400_000


def test_kume_farki_yalniz_degisenler():
    onceki = {'a': ['x', -5.123], 'b': [None, -2.0], 'c': ['a', -6.5]}
    yeni = {'a': ['x', -5.1234], 'b': ['a', -6.0], 'c': ['a', -6.4], 'd': [None, None]}
    f = kume_farki(onceki, yeni)
    assert set(f) == {'b', 'c', 'd'}  # a: 3 basamağa yuvarlanınca aynı
    assert f['b'] == ['a', -6.0]


def test_tavan_yeni_once_ve_sinir():
    isler = [Is(agirlik=10, zaman=z, ifadeler=[('SQL', [z])], guncelle=None) for z in range(100)]
    oncelikli = [Is(agirlik=5, zaman=None, ifadeler=[('P', [])], guncelle=None)]
    secilen, kalan = tavanla(oncelikli, isler, tavan=105)
    assert secilen[0] is oncelikli[0]
    assert sum(i.agirlik for i in secilen) <= 105
    assert [i.zaman for i in secilen[1:]] == list(range(99, 89, -1))  # en yeni önce
    assert kalan == 90


def test_tavan_asilmazsa_hepsi():
    isler = [Is(agirlik=1, zaman=z, ifadeler=[], guncelle=None) for z in range(5)]
    secilen, kalan = tavanla([], isler, tavan=100)
    assert len(secilen) == 5 and kalan == 0


def test_olay_satiri_worker_sutunlari():
    o = {'id': 'emsc:20260101_0000001', 'zaman_ms': 1_767_225_600_000, 'enlem': 38.5, 'boylam': 30.0,
         'derinlik': 7.0, 'buyukluk': 3.1, 'tur': 'ML', 'mw': 1.017 * 3.1 - 0.012}
    s = olay_satiri(o, 'emsc', 1_767_300_000_000)
    assert s['katalog'] == 'tr' and s['hucre1'] == '38_30' and s['durum'] == 'islendi'
    assert s['kaynak'] == 'emsc' and s['eklendi'] == 1_767_300_000_000
    k = json.loads(s['kaynaklar'])
    assert list(k) == ['emsc'] and list(k['emsc']) == ['id', 'buyukluk', 'tur', 'zaman', 'mw']
    assert k['emsc']['id'] == '20260101_0000001'
    u = olay_satiri({**o, 'id': 'usgs:us7000abc', 'enlem': -20.0, 'boylam': 170.0, 'tur': 'Mw'}, 'usgs', 1)
    assert u['katalog'] == 'dunya' and json.loads(u['kaynaklar'])['usgs']['id'] == 'us7000abc'
    assert s['yer'] is None  # katalog kaydında yer yoksa


def test_olay_satiri_yer_ve_yuvarlanan_zaman():
    o = {'id': 'emsc:1', 'zaman_ms': 1_767_225_600_999.7, 'enlem': 38.5, 'boylam': 30.0, 'derinlik': 7.0,
         'buyukluk': 3.1, 'tur': 'ML', 'mw': 3.1, 'yer': 'WESTERN TURKEY'}
    s = olay_satiri(o, 'emsc', 1)
    assert s['yer'] == 'WESTERN TURKEY'
    assert s['zaman'] == 1_767_225_601_000  # int() 600_999'a keserdi
    assert json.loads(s['kaynaklar'])['emsc']['zaman'] == 1_767_225_601_000


def test_tekillestir_worker_kaydiyla():
    t = 1_767_225_600_000
    katalog = [
        {'id': 'emsc:A', 'zaman_ms': t, 'enlem': 38.0, 'boylam': 30.0, 'mw': 3.0},
        {'id': 'emsc:B', 'zaman_ms': t + 3600_000, 'enlem': 38.0, 'boylam': 30.0, 'mw': 3.0},
        {'id': 'emsc:C', 'zaman_ms': t + 7200_000, 'enlem': 38.0, 'boylam': 30.0, 'mw': 3.0},
        {'id': 'emsc:D', 'zaman_ms': t + 9000_000, 'enlem': 38.0, 'boylam': 30.0, 'mw': 3.0},
    ]
    d1 = [
        # A: AFAD kaydı, 20 s, 10 km, ΔMw 0,3 → eşleşir
        {'id': 'afad:1', 'zaman': t + 20_000, 'enlem': 38.09, 'boylam': 30.0, 'mw': 3.3, 'kaynaklar': '{"afad":{}}'},
        # B: kaynaklar'da aynı EMSC kimliği (konum çok farklı olsa bile) → eşleşir
        {'id': 'kandilli:2', 'zaman': t + 3600_000 + 90_000, 'enlem': 39.5, 'boylam': 30.0, 'mw': 3.0,
         'kaynaklar': '{"emsc":{"id":"B"}}'},
        # C: aynı kimlik zaten D1'de
        {'id': 'emsc:C', 'zaman': t + 7200_000, 'enlem': 38.0, 'boylam': 30.0, 'mw': 3.0, 'kaynaklar': '{}'},
        # D: 61 s → eşleşmez
        {'id': 'afad:4', 'zaman': t + 9000_000 + 61_000, 'enlem': 38.0, 'boylam': 30.0, 'mw': 3.0, 'kaynaklar': '{}'},
    ]
    esles = tekillestir(katalog, d1)
    assert esles == {'emsc:A': 'afad:1', 'emsc:B': 'kandilli:2', 'emsc:C': 'emsc:C'}


def test_plan_yalniz_degisen_kume_ve_yeni_olay():
    simdi = 1_767_225_600_000
    olaylar = [
        {'id': f'emsc:{i}', 'zaman_ms': simdi - (10 - i) * GUN_MS, 'enlem': 38.0, 'boylam': 30.0, 'derinlik': 5.0,
         'buyukluk': 3.0, 'tur': 'ML', 'mw': 3.0}
        for i in range(10)
    ]
    kume = {o['id']: [None, -3.0] for o in olaylar}
    durum = gunluk.bos_durum()
    # 0–4 zaten D1'de (önceki gece), kume'leri aynı; 2'nin kume'si değişti
    for o in olaylar[:5]:
        durum['olay'][o['id']] = o['zaman_ms']
        durum['kume'][o['id']] = [None, -3.0]
    kume['emsc:2'] = ['emsc:1', -6.0]
    isler = gunluk.olay_kume_isleri(olaylar, kume, durum, 'emsc', simdi)
    yeni = [i for i in isler if any(s.startswith('INSERT OR IGNORE INTO olay') for s, _ in i.ifadeler)]
    sadece_kume = [i for i in isler if i not in yeni]
    assert len(yeni) == 5 and len(sadece_kume) == 1
    assert sadece_kume[0].ifadeler[0][1][0] == 'emsc:2'
    # iş uygulanınca durum güncellenir → ikinci planda iş yok
    for i in isler:
        i.guncelle(durum)
    assert gunluk.olay_kume_isleri(olaylar, kume, durum, 'emsc', simdi) == []


def test_plan_400_gun_disi_yazilmaz():
    simdi = 1_767_225_600_000
    eski = {'id': 'emsc:e', 'zaman_ms': simdi - 401 * GUN_MS, 'enlem': 38.0, 'boylam': 30.0, 'derinlik': 5.0,
            'buyukluk': 3.0, 'tur': 'ML', 'mw': 3.0}
    assert gunluk.olay_kume_isleri([eski], {'emsc:e': [None, -3.0]}, gunluk.bos_durum(), 'emsc', simdi) == []


def test_plan_eslesen_kimlik_kullanilir():
    simdi = 1_767_225_600_000
    o = [{'id': 'emsc:A', 'zaman_ms': simdi - GUN_MS, 'enlem': 38.0, 'boylam': 30.0, 'derinlik': 5.0,
          'buyukluk': 3.0, 'tur': 'ML', 'mw': 3.0},
         {'id': 'emsc:B', 'zaman_ms': simdi - GUN_MS + 3600_000, 'enlem': 38.0, 'boylam': 30.0, 'derinlik': 5.0,
          'buyukluk': 2.5, 'tur': 'ML', 'mw': 2.5}]
    durum = gunluk.bos_durum()
    durum['esles'] = {'emsc:A': 'afad:1'}
    isler = gunluk.olay_kume_isleri(o, {'emsc:A': [None, -3.0], 'emsc:B': ['emsc:A', -7.0]}, durum, 'emsc', simdi)
    sql = [(s, p) for i in isler for s, p in i.ifadeler]
    assert not any(p and p[0] == 'emsc:A' for s, p in sql if 'INTO olay' in s)  # eşleşen olay eklenmez
    kume_sql = {p[0]: p for s, p in sql if 'INTO kume' in s}
    assert kume_sql['afad:1'][1] is None
    assert kume_sql['emsc:B'][1] == 'afad:1'  # ebeveyn kimliği D1'deki kimlik


def test_uygula_100_ifadelik_parcalar_ve_hata_sonrasi_durum(monkeypatch):
    cagrilar = []

    def sahte_toplu(ifadeler):
        if len(cagrilar) == 2:
            raise gunluk.d1.D1Hatasi('D1 HTTP 500: deneme')
        cagrilar.append(len(ifadeler))
        return [[] for _ in ifadeler]
    monkeypatch.setattr(gunluk.d1, 'toplu', sahte_toplu)
    durum = gunluk.bos_durum()

    def is_(k):
        return Is(agirlik=10, zaman=k, ifadeler=[('A', []), ('B', [])], guncelle=lambda d, k=k: d['olay'].update({k: k}))
    isler = [is_(k) for k in range(150)]
    try:
        gunluk.uygula(isler, durum)
    except gunluk.d1.D1Hatasi:
        pass
    assert cagrilar == [100, 100]  # bir işin ifadeleri bölünmez
    assert len(durum['olay']) == 100  # yalnız başarılı çağrıların işleri


def test_katalog_ayristirici_ve_onbellek(tmp_path):
    from hesap import katalog as kat
    assert kat.emsc_ayristir(b'<html>hata</html>') == []
    assert kat.usgs_ayristir(b'') == []
    emsc = json.dumps({'features': [
        {'id': 'x', 'geometry': {'coordinates': [27.1, 38.9, -7.0]},
         'properties': {'unid': '20260101_0000001', 'time': '2026-01-01T00:00:01.5Z', 'lat': 38.9, 'lon': 27.1,
                        'depth': 7.0, 'mag': 3.0, 'magtype': 'ml', 'flynn_region': 'WESTERN TURKEY'}},
        {'properties': {'unid': 'bozuk', 'time': 'x', 'mag': None}},
    ]}).encode()
    o = kat.emsc_ayristir(emsc)
    assert len(o) == 1 and o[0]['id'] == 'emsc:20260101_0000001' and o[0]['tur'] == 'ML'
    assert o[0]['zaman_ms'] == 1_767_225_601_500 and o[0]['mw'] == 1.017 * 3.0 - 0.012
    usgs = json.dumps({'features': [{'id': 'us7000abc', 'geometry': {'coordinates': [170.0, -20.0, 33.0]},
                                     'properties': {'time': 1_767_225_601_500, 'mag': 5.2, 'magType': 'mww',
                                                    'place': '120 km S of Isangel, Vanuatu'}}]})
    u = kat.usgs_ayristir(usgs.encode())
    assert u[0]['id'] == 'usgs:us7000abc' and u[0]['tur'] == 'Mw' and u[0]['mw'] == 5.2
    yol = str(tmp_path / 'tr.csv.gz')
    kat.kaydet(yol, o + u)
    assert kat.yukle(yol) == sorted(o + u, key=lambda x: x['zaman_ms'])
    assert o[0]['yer'] == 'WESTERN TURKEY' and u[0]['yer'] == '120 km S of Isangel, Vanuatu'


def test_eski_onbellek_yer_sutunsuz_okunur(tmp_path):
    # katalog-v1 önbelleği (yer sütunu yok) katalog-v2 koduyla okunabilmeli; yer None
    import csv
    import gzip
    from hesap import katalog as kat
    yol = str(tmp_path / 'tr.csv.gz')
    with gzip.open(yol, 'wt', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['id', 'zaman_ms', 'enlem', 'boylam', 'derinlik', 'buyukluk', 'tur', 'mw'])
        w.writerow(['emsc:1', 1_767_225_600_000, 38.5, 30.0, 7.0, 3.1, 'ML', 3.1])
    o = kat.yukle(yol)
    assert len(o) == 1 and o[0]['yer'] is None and o[0]['mw'] == 3.1
    kat.kaydet(yol, o)  # yeniden yazınca yer sütunu eklenir, boş yer None kalır
    assert kat.yukle(yol)[0]['yer'] is None


def _hesap_olaylari(n=400, tohum=3):
    r = np.random.default_rng(tohum)
    t0 = 1_700_000_000_000.0
    z = np.sort(r.uniform(t0, t0 + 300 * GUN_MS, n))
    return [{'id': f'emsc:{i}', 'zaman_ms': float(z[i]), 'enlem': float(r.uniform(37, 40)),
             'boylam': float(r.uniform(28, 33)), 'mw': float(2.0 + r.exponential(0.43))} for i in range(n)]


def test_d_f_bant_disi_onceki_ya_da_1_6(monkeypatch, capsys):
    olaylar = _hesap_olaylari()
    simdi = 1_700_000_000_000.0 + 301 * GUN_MS
    monkeypatch.setattr(gunluk, 'korelasyon_boyutu', lambda e, b: 0.49)
    p, *_ = gunluk.hesapla('tr', olaylar, None, 1_700_000_000_000.0, simdi)
    assert p['d_f'] == 1.6
    p, *_ = gunluk.hesapla('tr', olaylar, {'d_f': 1.42, 'b': 1.0, 'log_eta0': -5.0}, 1_700_000_000_000.0, simdi)
    assert p['d_f'] == 1.42
    assert 'UYARI' in capsys.readouterr().out


def test_esik_az_veri_onceki_log_eta0_ve_yazim_yok(monkeypatch):
    olaylar = _hesap_olaylari()
    simdi = 1_700_000_000_000.0 + 301 * GUN_MS
    monkeypatch.setattr(gunluk, 'esik', lambda x: float('nan'))
    onceki = {'d_f': 1.6, 'b': 1.0, 'log_eta0': -5.5}
    p, kume, hucreler, ozet = gunluk.hesapla('tr', olaylar, onceki, 1_700_000_000_000.0, simdi)
    assert p['log_eta0'] == -5.5 and ozet['param_yaz'] is False
    p, kume, hucreler, ozet = gunluk.hesapla('tr', olaylar, None, 1_700_000_000_000.0, simdi)
    assert p is None and kume == {} and hucreler == []


def test_bozuk_200_govdesi_onbellegi_silmez(monkeypatch):
    from datetime import datetime, timezone
    from hesap import katalog as kat
    simdi = datetime(2026, 10, 24, tzinfo=timezone.utc)
    t = simdi.timestamp() * 1000 - GUN_MS
    olaylar = {'emsc:A': {'id': 'emsc:A', 'zaman_ms': t, 'enlem': 38.0, 'boylam': 30.0, 'mw': 3.0}}
    meta = {'tr': {'bas': 0, 'tamam': simdi.timestamp() * 1000}}
    monkeypatch.setattr(kat, '_getir', lambda adres: b'<html>502</html>')
    import pytest
    with pytest.raises(kat.KaynakHatasi):
        gunluk.katalog_tamamla('tr', olaylar, meta, simdi, float('inf'), simdi)
    assert 'emsc:A' in olaylar
    # geçerli boş yanıt (204 / boş features) pencereyi tazeleyebilir
    monkeypatch.setattr(kat, '_getir', lambda adres: None)
    assert gunluk.katalog_tamamla('tr', olaylar, meta, simdi, float('inf'), simdi) is True
    assert olaylar == {}


def test_hucre_isleri_tavan_atlanan_satirin_hesabini_tazelemez():
    simdi = 1_767_225_600_000
    durum = gunluk.bos_durum()
    hucreler = []
    for i in range(150):
        s = {'anahtar': f'38_{i}', 'mc': 2.2, 'b': None, 'sigma_b': None, 'n': 10, 'lambda': 1.0, 'bh_p': 1.0}
        hucreler.append(s)
        durum['hucre'][f'tr|38_{i}'] = gunluk.hucre_degeri(s)
    hucreler[0] = {**hucreler[0], 'lambda': 2.0}  # yalnız 38_0 değişti
    isler = gunluk.hucre_isleri('tr', hucreler, durum, simdi)
    upsert = [i for i in isler if i.ifadeler[0][0] is gunluk.SQL_HUCRE]
    guncelle = [i for i in isler if i.ifadeler[0][0] is not gunluk.SQL_HUCRE]
    assert len(upsert) == 1 and upsert[0].ifadeler[0][1][1] == '38_0'
    # hesap tazeleme yalnız değişmeyen hücreler, adla; ifade başına ≤ 100 bağlı parametre
    anahtarlar = [a for i in guncelle for s, p in i.ifadeler for a in p[2:]]
    assert sorted(anahtarlar) == sorted(f'38_{i}' for i in range(1, 150))
    assert all(len(p) <= 100 for i in guncelle for s, p in i.ifadeler)
    assert sum(i.agirlik for i in guncelle) == 149
    # tavan upsert'i dışarıda bırakırsa 38_0'ın hesabı hiçbir ifadeyle tazelenmez
    secilen, kalan = gunluk.tavanla(guncelle + upsert, [], tavan=149)
    assert kalan == 1
    assert '38_0' not in [a for i in secilen for s, p in i.ifadeler for a in p]


def _birikim_olaylari(simdi):
    return [{'id': f'emsc:{i}', 'zaman_ms': simdi - i * GUN_MS, 'enlem': 38.0, 'boylam': 30.0} for i in range(0, 420, 10)]


def test_birikim_yalniz_400_gun_ve_d1_disi():
    simdi = 1_767_225_600_000
    olaylar = _birikim_olaylari(simdi)  # 0..410 gün: 41 olay 400 gün içinde, 1 dışında
    durum = gunluk.bos_durum()
    assert gunluk.birikim(olaylar, durum, simdi) == 41
    durum['olay']['emsc:0'] = simdi
    durum['esles']['emsc:10'] = 'afad:1'
    assert gunluk.birikim(olaylar, durum, simdi) == 39
    for o in olaylar:
        durum['olay'][o['id']] = o['zaman_ms']
    assert gunluk.birikim(olaylar, durum, simdi) == 0


def test_birikim_yalniz_yazilabilir_olaylari_sayar():
    # kume'si hesaplanamayan (eşik yok → yazılamayan) katalogun olayları doldurma modunu kilitlemesin
    simdi = 1_767_225_600_000
    olaylar = _birikim_olaylari(simdi)
    durum = gunluk.bos_durum()
    assert gunluk.birikim(olaylar, durum, simdi, yazilabilir={'emsc:0', 'emsc:10', 'emsc:410'}) == 2
    assert gunluk.birikim(olaylar, durum, simdi, yazilabilir=set()) == 0
    assert gunluk.mod_sec(gunluk.birikim(olaylar, durum, simdi, yazilabilir=set())) == ('normal', 20_000)


def test_mod_ve_tavan():
    assert gunluk.mod_sec(5) == ('doldurma', 40_000)
    assert gunluk.mod_sec(0) == ('normal', 20_000)
    assert gunluk.mod_sec(5, tavan=1000) == ('doldurma', 1000)  # elle verilen tavan önceliklidir
    assert gunluk.mod_sec(5, ayni_gun=True) == ('doldurma', 5_000)
    assert gunluk.mod_sec(0, ayni_gun=True) == ('normal', 5_000)
    assert gunluk.mod_sec(5, tavan=30_000, ayni_gun=True) == ('doldurma', 30_000)


def test_ayni_utc_gunu():
    gun = 86_400_000
    g = 20_000 * gun
    assert gunluk.ayni_utc_gunu(g + 3 * 3_600_000, g + 22 * 3_600_000)      # 03:01 ve 22:08 UTC
    assert not gunluk.ayni_utc_gunu(g + 22 * 3_600_000, g + gun + 3 * 3_600_000)
    assert not gunluk.ayni_utc_gunu(None, g)


def test_tavan_iki_modda_da_asilmaz():
    for birikim, beklenen in ((7, 40_000), (0, 20_000)):
        mod, tavan = gunluk.mod_sec(birikim)
        assert tavan == beklenen
        isler = [Is(agirlik=10, zaman=z, ifadeler=[], guncelle=None) for z in range(10_000)]
        secilen, kalan = tavanla([Is(agirlik=4, zaman=None, ifadeler=[], guncelle=None)], isler, tavan)
        assert sum(i.agirlik for i in secilen) <= tavan
        assert len(secilen) - 1 == (tavan - 4) // 10 and kalan == 10_000 - (tavan - 4) // 10
        assert [i.zaman for i in secilen[1:4]] == [9999, 9998, 9997]  # en yeni önce


def _heterojen_olaylar(tohum=5, b_alt=0.6):
    """ML ~2'den eksik kayıtlı (görünür b ≈ 0,6), 4 ve üstü tam (b = 1,1): MAXC tamlığın altında kalır."""
    r = np.random.default_rng(tohum)
    kutu = lambda x: np.round(np.round(x / 0.1) * 0.1, 1)
    ust = kutu(3.95 + r.exponential(1 / (1.1 * np.log(10)), 4000))
    alt = kutu(1.95 + r.exponential(1 / (b_alt * np.log(10)), 14000))
    m = np.concatenate([alt[alt < 3.95], ust])
    r.shuffle(m)
    t0 = 1_546_300_800_000.0   # 2019-01-01: ETAS eğitim penceresi (2018–2021) içinde
    z = np.sort(r.uniform(t0, t0 + 900 * GUN_MS, m.size))
    return [{'id': f'emsc:{i}', 'zaman_ms': float(z[i]), 'enlem': float(r.uniform(37, 40)),
             'boylam': float(r.uniform(28, 33)), 'mw': float(m[i])} for i in range(m.size)]


def test_katalog_mc_mbs_heterojen_katalogda_maxc_degil():
    olaylar = _heterojen_olaylar()
    m = np.array([o['mw'] for o in olaylar])
    z = np.array([o['zaman_ms'] for o in olaylar])
    mc, kaynak = gunluk.katalog_mc('tr', z, m)
    assert kaynak == 'MBS' and mc >= 3.6
    assert gunluk.mc_maxc(m) < 3.0
    b_mbs, _ = gunluk.b_aki_utsu(m, mc)
    b_maxc, _ = gunluk.b_aki_utsu(m, gunluk.mc_maxc(m))
    assert b_mbs == pytest.approx(1.1, abs=0.15) and b_maxc < 0.8


def test_hesapla_b_mbs_ve_hucre_tabani():
    olaylar = _heterojen_olaylar()
    simdi = 1_546_300_800_000.0 + 901 * GUN_MS
    p, kume, hucreler, ozet = gunluk.hesapla('tr', olaylar, None, 1_546_300_800_000.0, simdi)
    assert ozet['mc_kaynak'] == 'MBS' and ozet['mc'] >= 3.6
    assert p['b'] == pytest.approx(1.1, abs=0.15)
    assert all(h['mc'] >= ozet['mc'] - 1e-9 for h in hucreler)


def test_hesapla_mbs_yoksa_maxc_yedegi(monkeypatch, capsys):
    olaylar = _hesap_olaylari()
    simdi = 1_700_000_000_000.0 + 301 * GUN_MS
    monkeypatch.setattr(gunluk.etas, 'mc_mbs', lambda m, *a, **k: float('nan'))
    p, _, _, ozet = gunluk.hesapla('tr', olaylar, None, 1_700_000_000_000.0, simdi)
    assert ozet['mc_kaynak'] == 'MAXC' and p is not None
    assert 'MAXC yedeği' in capsys.readouterr().out


def test_b_bant_disi_onceki_ya_da_1_0(monkeypatch, capsys):
    olaylar = _hesap_olaylari()
    simdi = 1_700_000_000_000.0 + 301 * GUN_MS
    monkeypatch.setattr(gunluk, 'b_aki_utsu', lambda m, mc, dm=0.1: (0.4, 0.01))
    p, *_ = gunluk.hesapla('tr', olaylar, None, 1_700_000_000_000.0, simdi)
    assert p['b'] == 1.0
    assert 'dışında' in capsys.readouterr().out
    p, *_ = gunluk.hesapla('tr', olaylar, {'d_f': 1.6, 'b': 0.93, 'log_eta0': -5.0}, 1_700_000_000_000.0, simdi)
    assert p['b'] == 0.93
