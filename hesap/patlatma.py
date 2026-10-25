# Patlatma imzası bayrağı (Wiemer & Baer 2000, BSSA 90(2), doi:10.1785/0119990104: taş ocağı patlatmaları katalogda
# gündüz, hafta içi ve belirli saatlerde yığılır; katalog düzeyinde zaman-saat/hafta günü örüntüsüyle ayıklanır).
# Burada yalnız HESAPTAN düşürme: bayraklı 1° hücrenin M < M_UST olayları b/λ/olağan dışı tabanından ve NN uyumundan çıkar.
# Hiçbir kartta ya da mesajda hücre/olay "taş ocağı" diye adlandırılmaz.
#
# Pencere: yerel (Europe/Istanbul) 08:00–17:00, Pzt–Cum. Türkiye 2016'dan beri kalıcı UTC+3 (yaz saati yok; katalog 2018'den başlıyor),
# bu yüzden sabit +3 saat. Gerekçe: ocak ve maden işletmelerinin vardiyası ve patlatma saati mesai içindedir; ilgili literatür
# (Horasan vd. 2009 İstanbul, Yılmaz vd. 2012 Karadeniz) gündüz bloğunu kullanır. Beklenen pay katalog geneli p0 (aynı küçük
# olaylardan ölçülür), böylece günlük tespit ve kayıt eğilimleri sabit zeminde kalır.
# Test: hücrede n ≥ 30 küçük (M < 3,5) olay; tek yönlü binom P(X ≥ k | n, p0); hücreler arası Benjamini–Hochberg; q < 0,01;
# ek koruma: pay − p0 ≥ 0,10 (yalnız anlamlılık, 1°'lik hücrede binlerce olayda ufak sapmayı bile yakalar).
# Küçük olay seçimi: patlatmalar küçüktür (M ≲ 3,5); büyük olaylar test girdisine ve düşürmeye girmez (gerçek deprem riskine karşı tutucu).
import numpy as np
from scipy.stats import binom

from hesap.hucre import bh_duzelt, hucre_anahtari

TSI_MS = 3 * 3600 * 1000
GUN_MS = 86_400_000
M_UST = 3.5
N_EN_AZ = 30
Q_ESIK = 0.01
FAZLA_EN_AZ = 0.10  # etki büyüklüğü tabanı: hücre payı p0'dan en az 0,10 yüksek olmalı (büyük n'de anlamlı ama önemsiz sapmaları, örn. artçı dizisi hücresini, bayraklamaz)
PENCERE = (8, 17)   # [08:00, 17:00) yerel
HAFTA_ICI = 5       # Pzt=0 … Cum=4


def pencerede(zaman_ms):
    """Boolean dizi: yerel saat 08:00–17:00 ve Pzt–Cum. 1970-01-01 Perşembe (weekday 3)."""
    yerel = np.asarray(zaman_ms, float).astype(np.int64) + TSI_MS
    gun = yerel // GUN_MS
    saat = (yerel % GUN_MS) // 3_600_000
    hafta_gunu = (gun + 3) % 7
    return (saat >= PENCERE[0]) & (saat < PENCERE[1]) & (hafta_gunu < HAFTA_ICI)


def bayrakli(zaman, enlem, boylam, mw, katalog='tr', m_ust=M_UST, n_en_az=N_EN_AZ, q_esik=Q_ESIK, fazla_en_az=FAZLA_EN_AZ):
    """→ (bayrak: {anahtar: {n, k, pay, q}}, p0, test_edilen_hucre_sayisi). Girdi: baslangic_ms sonrası bütün katalog."""
    zaman, enlem, boylam, mw = (np.asarray(x, float) for x in (zaman, enlem, boylam, mw))
    kucuk = mw < m_ust
    if not kucuk.any():
        return {}, float('nan'), 0
    ic = pencerede(zaman[kucuk])
    p0 = float(ic.mean())
    anahtar = np.array([hucre_anahtari(e, b, katalog) for e, b in zip(enlem[kucuk], boylam[kucuk])], dtype=object)
    satirlar = []
    for a in np.unique(anahtar):
        sec = anahtar == a
        n = int(sec.sum())
        if n < n_en_az:
            continue
        k = int(ic[sec].sum())
        satirlar.append((str(a), n, k, float(binom.sf(k - 1, n, p0))))
    if not satirlar:
        return {}, p0, 0
    q = bh_duzelt([s[3] for s in satirlar])
    bayrak = {a: {'n': n, 'k': k, 'pay': round(k / n, 3), 'q': float(qq)}
              for (a, n, k, _), qq in zip(satirlar, q) if qq < q_esik and k / n - p0 >= fazla_en_az}
    return bayrak, p0, len(satirlar)


def ayiklama_maskesi(zaman, enlem, boylam, mw, bayrak, katalog='tr', m_ust=M_UST):
    """Boolean: bayraklı hücrede ve mw < m_ust (hesaptan düşecek olaylar)."""
    mw = np.asarray(mw, float)
    if not bayrak:
        return np.zeros(mw.size, bool)
    anahtar = np.array([hucre_anahtari(e, b, katalog) for e, b in zip(enlem, boylam)], dtype=object)
    return np.isin(anahtar, list(bayrak)) & (mw < m_ust)
