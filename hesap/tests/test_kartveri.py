import json

from hesap import kartveri


def test_yoksa_bos_sozluk(tmp_path):
    assert kartveri.oku(str(tmp_path / 'yok.json')) == {}


def test_yaz_digerlerini_korur(tmp_path):
    yol = str(tmp_path / 'alt' / 'kart-veri.json')
    kartveri.yaz(yol, 'gr', {'b': 1.0})
    kartveri.yaz(yol, 'etas', {'p5': 0.2})
    kartveri.yaz(yol, 'gr', {'b': 1.1})
    with open(yol, encoding='utf-8') as f:
        veri = json.load(f)
    assert veri == {'gr': {'b': 1.1}, 'etas': {'p5': 0.2}}


def test_bozuk_dosya_bos_sayilir(tmp_path):
    yol = tmp_path / 'kart-veri.json'
    yol.write_text('{bozuk', encoding='utf-8')
    kartveri.yaz(str(yol), 'etas', {'a': 1})
    assert kartveri.oku(str(yol)) == {'etas': {'a': 1}}


def test_birden_cok_anahtar_tek_yazimda(tmp_path):
    yol = str(tmp_path / 'kart-veri.json')
    kartveri.yaz(yol, 'x', 1)
    kartveri.guncelle(yol, {'etas': {'a': 1}, 'etasGizliKayit': []})
    assert kartveri.oku(yol) == {'x': 1, 'etas': {'a': 1}, 'etasGizliKayit': []}
