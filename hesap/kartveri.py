# Kart verisi: hesap/.onbellek/kart-veri.json (Actions cache). Birden çok hesap (gunluk, etas, dogrulama, olasılık)
# kendi anahtarını yazar; dosya her zaman birleştirilmiş bir sözlüktür. Yazım atomik (geçici dosya + os.replace).
import json
import os

VARSAYILAN = os.path.join(os.path.dirname(__file__), '.onbellek', 'kart-veri.json')


def oku(yol=VARSAYILAN):
    """Dosya yoksa ya da bozuksa {}."""
    try:
        with open(yol, encoding='utf-8') as f:
            veri = json.load(f)
        return veri if isinstance(veri, dict) else {}
    except (OSError, ValueError):
        return {}


def guncelle(yol, parcalar):
    """parcalar sözlüğündeki anahtarları yazar, diğer anahtarlara dokunmaz."""
    veri = oku(yol)
    veri.update(parcalar)
    os.makedirs(os.path.dirname(yol) or '.', exist_ok=True)
    gecici = yol + '.tmp'
    with open(gecici, 'w', encoding='utf-8') as f:
        json.dump(veri, f, ensure_ascii=False, separators=(',', ':'))
    os.replace(gecici, yol)
    return veri


def yaz(yol, anahtar, deger):
    return guncelle(yol, {anahtar: deger})
