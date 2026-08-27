# Satranç Motoru — Durum ve Yol Haritası

*Son güncelleme: 2026-08-27 (2. revizyon)*

İki kod tabanı var: **chess-bot** (Python, bu repo) ve **atropos** (C++, `~/Desktop/atropos`).
Karar: atropos'un kalan fazları Python'da yazılacak, kazanımları buraya taşınacak.

---

## 1. Bugün nerede duruyoruz

```
chess-bot   124 python dosyası · 10 paket · 719 test · mypy temiz · 53.758 nps
atropos      43 C++ dosyası · Phase 16/31 · 8.938 nps · git yok
```

chess-bot çalışır durumda: 8 seviyeli motor merdiveni, UCI protokolü, Elo veritabanı,
üç turnuva formatı, Streamlit arayüzü, opsiyonel LLM yorumu, beş araştırma modülü ve
çalıştırılmış notebook'ları.

---

## 2. Ne yaptık

### 2.1 Motor merdiveni (Phase 1-4)

Sekiz seviye, her biri bir öncekine tek bir teknik ekliyor:

| Seviye | Teknik | Hedef Elo | Ölçülen |
|---|---|---:|---:|
| 1 | Rastgele legal hamle | 200 | — |
| 2 | Materyal sayımı, 1-ply | 600 | %96.9 vs L1 |
| 3 | Minimax, depth 3 | 900 | %100 vs L2 |
| 4 | Alpha-beta + iterative deepening | 1200 | %93.8 vs L3 |
| 5 | Piece-square tables, tapered eval | 1500 | %84.4 vs L4 |
| 6 | Quiescence, TT, killer, MVV-LVA | 1800 | %90.6 vs L5 |
| 7 | Null-move, LMR, history, aspiration | 2100 | %63.1, SPRT ile kabul |
| 8 | Uyarlanabilir zaman + opsiyonel LLM danışman | 2400 | ölçülebilir üstünlük yok |

Merdivenin tamamı sekans testinden geçirildi (`H1: en az 100 Elo`, 0.1sn/hamle):

| eşleşme | oyun | skor | Elo | %95 aralık | hüküm |
|---|---:|---:|---:|---:|---|
| L2 vs L1 | 9 | %88.9 | +361 | [+194, +800] | kabul |
| L3 vs L2 | 7 | %100 | +800 | [+800, +800] | kabul |
| L4 vs L3 | 9 | %88.9 | +361 | [+194, +800] | kabul |
| L5 vs L4 | 33 | %68.2 | +132 | [+45, +240] | kabul |
| L6 vs L5 | 9 | %88.9 | +361 | [+134, +800] | kabul |
| L7 vs L6 | 65 | %63.1 | +93 | [+21, +174] | kabul |
| L8 vs L7 | 25 | %38.0 | −85 | [−238, +40] | red |

**Merdiven Level 7'ye kadar sıralı.** Alt üç basamak toplam 25 oyunda çözüldü —
sabit gauntlet aynı üçü için 48 oyun harcamış ve daha zayıf bir iddia üretmişti.

Merdivenin omurgası şu kural: **alpha-beta, minimax ile aynı skoru döndürmeli.**
Aynı derinlik, aynı değerlendirme, aynı sonuç — sadece node sayısı farklı. Bu eşdeğerlik
bir test, ve L6/L7'de gelen her budama numarasının altındaki emniyet ağı.

### 2.2 Ölçüm altyapısı

| Araç | Ne yapar |
|---|---|
| `engine/perft.py` | Hamle üretimini yayınlanmış node sayılarına karşı kanıtlar |
| `engine/tactics.py` | 8 pozisyonluk taktik suite, hızlı regresyon koruması |
| `elo/` | Elo hesabı, SQLite veritabanı, tracker, leaderboard |
| `tournament/` | Round-robin, Swiss, gauntlet + açılış kitabı |
| `tournament/uci_engine.py` | Dış UCI motorunu `BaseEngine` gibi gösterir |
| `elo/sprt.py` | Sekans testi — oyunlar cevap verdiği an durur, güven aralığıyla |
| `--workers N` | Paralel oyun üretimi; 6 işçi ≈ 5.5× verim (ölçüldü) |
| `scripts/` | ladder, calibrate, eval_ab, sprt_match, ladder_sprt, self_play_run |

### 2.3 UCI (atropos'tan taşınan)

Protokol parser, motor seçenekleri, zaman yönetimi, thread'li arama, cooperative stop.
`Level` bir UCI seçeneği (1-8) — merdiveni dışarıdan ölçülebilir kılan şey bu.

cutechess-cli bağımlılığı **yok**. Protokolü doğrudan konuşmak birkaç yüz satır ve bir
kurulum adımını ortadan kaldırıyor. Zor kısım protokol değil, kötü davranan rakip:
asılan, ölen, illegal hamle döndüren. Her biri turnuvayı değil o oyunu bitiriyor.

### 2.4 Araştırma modülleri

Beşi de kurulu, testli ve notebook'ları çalıştırılmış:

- **`rl_tuning`** — Değerlendirme parametreleri üzerinde policy gradient (antitetik örnekleme)
- **`self_play`** — TDLeaf(λ), 10.000 oyunluk koşu yapıldı
- **`minimal_nnue`** — 6 mimari, 385 → 269K parametre, girdi ablasyonu
- **`hybrid_eval`** — Karmaşıklık tabanlı katman yönlendirmesi, gecikme bütçesiyle
- **`alphazero_lite`** — 4 blok ResNet + PUCT MCTS + self-play döngüsü

---

## 3. Ölçümler ve bulgular

### 3.1 Dış kalibrasyon: atropos merdivende nerede?

atropos'u kendi merdivenimize karşı oynattık (0.3sn/hamle, sabit zaman kontrolü):

```
atropos vs L4   %85.0     atropos vs L6   %15.0
atropos vs L5   %50.0     atropos vs L7   %15.0
─────────────────────────────────────────────────
performance rating: 1538  →  Level 5'in basamağı
```

**İlginç olan nerede durduğu değil, neden orada durduğu.** atropos'ta L6'nın sahip
olduğu her şey var — quiescence, TT, killer, MVV-LVA — ve L6'ya %85 kaybediyor.
Sahip olmadığı şey hız: **8.938 node/sn'ye karşı ~54.000**.

> *Özellik paritesi, throughput'a yeniliyor.*

Bu sayılar merdivenin nominal birimlerinde; mutlak Elo için bilinen ratingli bir motor gerekir.

### 3.2 Hız: +%39, bedavaya

Profil tek bir şeyi yüksek sesle söyledi: **199.916 node için 1.318.794 hamle üretimi**
— node başına 6.6, bir tane yeterken. Quiescence tüm legal listeyi kurup alışlara
filtreliyordu, ve quiescence node'ların %69'u.

| | nps |
|---|---:|
| önce | 41.817 |
| forcing hamleleri doğrudan üret | 51.000 |
| + bitboard piyon yapısı | **58.138** |

Aynı ağaç, aynı node sayısı (108.966). Hamle üretimi node başına 6.6'dan 2.1'e düştü.

### 3.3 Evaluation v3: demet düştü, içindeki bir terim ship edildi

Passed pawn, açık hat, kral güvenliği. **Demet olarak iki kez reddedildi** —
sonra terimler tek tek test edildi ve biri kabul edildi.

| ne test edildi | oyun | skor | Elo | hüküm |
|---|---:|---:|---:|---|
| v3-full (üçü birden) | 60 | %43.3 | −47 | reddedildi |
| v3-shelter (ikisi) | 359 | %49.7 | −2 | reddedildi |
| v3-passers (sadece geçer piyon) | 714 | %51.5 | +11 | çözülmedi |
| **v3-rooks (sadece kale açık hat)** | **318** | **%56.3** | **+44** | **KABUL** |

**İşe yarayan terim, tekrar eden iki terimin altında gömülüydü.** Ayırmak buldu.

Yapısal sebep tablolarda görünüyor:

| piyon sırası | PST endgame bonusu | geçer piyon bonusu | toplam |
|---:|---:|---:|---:|
| 4 | 20 | 40 | 60 |
| 6 | 50 | 120 | 170 |
| 7 | 80 | 200 | 280 |

PST zaten piyona ilerlediği için ödüyor; geçer piyon terimi üstüne bir daha ödüyor.
Aynı örtüşme kral güvenliği için de geçerli (KING_MG zaten şahı köşeye itiyor).
Kale açık hat, üçünün içinde tablonun **gerçekten kodlayamayacağı** tek terim —
kalenin durduğu kare tabloda, altındaki hattın açık olup olmadığı piyonlara bağlı.

Benimseme: `positional_score`'a girdi, `positional_score_v2` kayıt için korundu,
ve terim `EvalParams`'a **ayarlanabilir parametre** olarak eklendi (9 → 11).
Bedeli: 58.138 → 53.758 nps (−%7.5) karşılığında +44 Elo.

v3-shelter'ın yolculuğu öğretici:

| oyun | skor | Elo | LLR |
|---:|---:|---:|---:|
| 64 | %58.6 | +60 | +1.00 |
| 198 | %57.1 | +49 | **+2.31** |
| 313 | %52.7 | +19 | −0.07 |
| 359 | %49.7 | **−2** | **−2.96** → red |

198. oyunda kabul etmeye **0.63 kalmıştı**. Orada duran sabit bir maç onu ship ederdi.

### 3.4 TDLeaf(λ): 10.000 oyun

```
öğrenilen tablo vs material-only başlangıç:  %59.4  →  +66 Elo
elle yazılmış tablolar vs öğrenilen:         %59.4  →  +66 Elo
elle yazılmış vs material-only:              %73.4  →  +175 Elo
```

TD, çıplak materyal sayımıyla insanın yazdığı tablolar arasındaki **175 Elo'luk açığın
~%38'ini kapattı** — ve oraya insanın yoluyla neredeyse hiç ortak yanı olmayan bir
rotadan geldi (at merkez−kenar farkı −13.9, hedef +70; şekil korelasyonu −0.16).

Soğuk başlangıç bulgusu: sıfır ağırlıktan öğrenme çalışmıyor. Her pozisyonu sıfır sayan
eval rastgele oynar, rastgele oyunlar kesin bitmez, beraberlik serisi gradyan taşımaz.
İlk koşuda ortalama TD farkı **tam olarak 0.0000** çıktı.

### 3.5 Minimal NNUE: gecikme sütunu tartışmayı bitiriyor

```
architecture      params   MAE cp   1-pos µs
──────────────────────────────────────────────
linear-folded        385    357.7        4.9
mlp-16            12.321    216.0       10.2
mlp-128           98.561    160.3       13.1
nnue-336x32      269.201    185.3       22.5
```

Elle yazılmış değerlendirme **6.4µs**. Doğrusal tabanı anlamlı yenen her ağ 10-22µs —
yerine geçeceğinin 2-4 katı. **Bu ölçekte, bu dilde bir NNUE aramanın içinde kendini
ödeyemiyor.**

Ablasyon sürprizi: **katlanmış 384'lük kodlama, yarı parametreyle 768'liği yeniyor**
(157.7 vs 180.9 cp). Renk simetrisi, onu kırma özgürlüğünden değerli.

### 3.6 AlphaZero-lite: hamle kodlaması tasarımın %96'sı

| | düz `from × to` | AlphaZero 8×8×73 |
|---|---:|---:|
| toplam parametre | 8.735.249 | **345.178** |
| underpromotion | vezire çöküyor | kodlanıyor |

25× küçük, ve fark tamamen hiç düşünmeyen bir katmandan geliyor.

---

## 4. Bulunan hatalar

| Nerede | Ne | Nasıl bulundu |
|---|---|---|
| **atropos** | stdout hiç flush edilmiyor → hiçbir GUI'ye karşı oynayamaz | UCI köprüsü 60sn bekledi |
| chess-bot UCI | `go depth N`, L6/7/8'de sessizce yok sayılıyor | Kodu okurken şüphelenip test ettim |
| chess-bot UCI | Derinlik limiti aramadan sonra motora yapışıyor | Yukarıdakini ararken çıktı |
| Taktik suite | 2 illegal pozisyon, 3 yanlış hamle | Suite'i kendi doğrulama testi |
| AlphaZero kodlayıcı | a1→c4 sessizce a1→d4'e kodlanıyor | 300 pozisyonluk çakışma taraması |
| Piyon yapısı | Çift yönlü fill her piyonu "doubled" sayıyor | Eşdeğerlik testi ilk koşuda |
| Test suite | Tek test 127sn (suite'in %70'i) | `--durations` |
| **Kendi raporum** | "L8 bir gerileme" — aralık sıfırı kapsıyordu | Özelliği kendi yokluğuna karşı test edince |

atropos'taki düzeltme tek satır (`std::cout << std::unitbuf;`), gerekçesi yorumda,
orijinal `main.cpp` yedeklendi. **Versiyon kontrolü olmadığı için bu önemli.**

---

## 5. Metodoloji dersleri

Bunlar projede tekrar tekrar ortaya çıktı; bir sonraki iş için geçerli.

**Sabit uzunluklu maç yanlış soruyu sorar.** Üç kez "gürültünün içinde" cevabı aldık —
L7 altı oyunda, v3-shelter altmışta, hızlanma kalibrasyonu onda. Sonuncusu en net hataydı:
%39 hızlanma ~+29 Elo eder, 10 oyunluk eşleşmenin standart hatası ~110 Elo. Deney o etkiyi
**başlamadan önce** göremezdi.

**Kesinlik kanıt değildir.** Tamamen berabere biten bir maçın skoru kusursuz kesinliktedir
ve bilgi içeriği sıfırdır.

**Bracket'i veriye göre seçme — ama seçerken de düşün.** Bu iki ayrı hata ve ikisini de
yaptık. Yolun ortasında `[0, 20]`'nin daha hızlı karar vereceğini gördük, dokunmadık, ve
koşu −2 Elo'da bitti; doğru karardı. Ama L8 vs L7'de `[0, 100]` seçtik — tek bir zaman
heuristiğinde farklılaşan iki motor için H0 daha ilk oyundan önce neredeyse kesindi.
Bracket bir *etki büyüklüğü hipotezidir* ve değişikliğin makul olarak ne yaptığına göre
seçilmelidir.

**Reddedilen H0, "daha kötü" demek değildir.** SPRT'nin H0'ı kabul etmesi "elo1 kadar iyi
değil" demektir. L8 vs L7'de nokta tahmini −85'ti ve biz "gerileme" diye raporladık; aralık
[−238, +40] sıfırı kapsıyordu. Doğru test (özelliği kendi yokluğuna karşı koymak) %48.1
verdi — yani teşhis de yanlıştı.

**Ölçtüğün şeyin ölçmek istediğin şey olduğunu varsayma.** Perft'te FEN'leri, taktik
suite'te pozisyonları, hızlanmadan sonra kalibrasyonu, SPRT'de zaman kontrolünü doğruladık.

**Micro-benchmark yalan söyleyebilir.** Piyon yapısını izole ölçtüğümüzde tam değerlendirme
*daha yavaş* okundu — gürültüydü. Sadece arama seviyesindeki tekrarlı ölçüm gerçek kazancı
gösterdi.

**Zaman kontrollü maçlar paralel koşturulabilir — ama sınırlı.** Önce "koşturulamaz"
diye not düştük, sonra ölçtük: 4-6 işçiye kadar çekişme %5-8, 8'den sonra %22+. Tekdüze
bir yavaşlama bir oyunu taraflı yapmaz (iki motor da aynı oranda yavaşlar). 6 işçi ≈ 5.5×
verim, ve ölçüm tabanı ~40 Elo'dan ~17'ye indi.

**Ölçüm setinin bir çözünürlük tabanı var ve bilinmeli.**

| ne ölçülecek | gereken oyun | eldeki verimle |
|---|---:|---|
| ≥100 Elo (merdiven basamağı) | 7-65 | dakikalar |
| ≥40 Elo (belirgin eval değişikliği) | ~350 | ~20 dk |
| ≥20 Elo (tek klasik terim) | ~1500 | ~1.5 saat |
| ≥10 Elo (ince ayar) | ~6000 | ~6 saat |

Bir fikri test etmeden önce "kaç Elo eder?" diye sorup ölçebilir miyim diye bakmak
gerekiyor. ~10 Elo'luk bir fikir için 6 saat planlamak ya da hiç test etmemek — ikisi de
bilinçli seçim; bilmeden 700 oyun harcamak değil.

---

## 6. Sırada ne var

### 6.1 Acil (teknik olmayan)

**Her iki repo da commit'siz.** chess-bot 124 dosya, atropos 16 fazlık iş — ve atropos'un
kendi `.git`'i yok, ev dizinindeki kaza repo'sunda untracked duruyor. Geçmiş yok, bisect
yok, geri dönüş yok. Ben o kod tabanına dokundum (flush düzeltmesi). Bu, şimdi bir
dakikalık iş, sonra imkânsız.

### 6.2 Merdiven ✅ tamamlandı

Yedi eşleşmenin hepsi karara bağlandı (yukarıdaki tablo). Merdiven L7'ye kadar sıralı.

Beklenmedik bulgu: L7'nin avantajı derinlikse ve 0.1sn'de her ikisi de depth 3'te
takılıyorsa, test o avantajı kapalıyken ölçüyordu — **yine de kabul edildi.** Yani
null-move/LMR aynı derinlikte de daha iyi hamle sıralaması sağlıyor.

**Level 8 açık kalıyor.** Ölçülebilir üstünlüğü yok ve olması da beklenmez: L7'nin
araması artı bir zaman heuristiği. Etrafında tasarlandığı öğrenilmiş değerlendirici
eğitilmemiş. Seçenekler:

- `research/minimal_nnue`'nin bulgusu: **doğrusal model bedava** (tabloya katlanıyor),
  ama ortalamayı tahmin etmekten zar zor iyi. Gizli katmanlı her ağ 2-4× pahalı.
- Uyarlanabilir saatin yardım mı zarar mı ettiği hâlâ açık (54 oyun, [−99, +72]).
  Daha dar bir bracket ile (`[0, 20]`) ve daha çok oyunla çözülebilir.

### 6.3 atropos'un kalan fazları (Python'da)

| Faz | Konu | Durum |
|---|---|---|
| 17 | Evaluation v3 | ✅ ölçüldü, reddedildi |
| 18 | Search v2 | ✅ L7'de zaten var (null-move, LMR, aspiration) |
| 19 | Turnuva zaman yönetimi | ✅ `uci/time_manager.py` |
| 20 | Profilleme + NPS | ✅ +%39, devam edilebilir |
| 21-23 | Taktik suite genişletme, benchmark baseline, kalibre release | kısmen |
| 24-31 | NNUE hattı | `research/minimal_nnue` çekirdek soruyu cevapladı |

NNUE hattı için dürüst durum: ölçüm, bu ölçekte Python'da bir NNUE'nin aramanın içinde
kendini ödemediğini söylüyor. Devam edilecekse ya batch'li yaprak değerlendirmesi
(MCTS gibi) ya da inference'ı tabloya katlayan doğrusal modeller mantıklı.

### 6.4 Açık sorular

- **Athena entegrasyonu** — ayrı repo + showcase mı, Athena içinde bir surface mi?
- **Mutlak Elo** — bilinen ratingli bir dış motor (Stockfish skill level) gerekir
- **v3-passers** — 714 oyunda çözülmedi, [−12, +34]; ~+10'luk etki için dar bracket gerek
- **L8'in uyarlanabilir saati** — çözülmedi, dar bracket ile yeniden denenmeli
- **Level 8'e ne koyacağız** — ölçüm, bu ölçekte Python'da NNUE'nin aramanın içinde
  kendini ödemediğini söylüyor

---

## 7. Hızlı referans

```bash
make test           # 712 test, ~45sn
make perft          # hamle üretimini kanıtla (10.7M node)
make run            # Streamlit arayüzü
make uci            # motoru stdin/stdout'ta
make ladder         # merdiven gauntlet'i
make ladder-sprt    # sekans testi durum tablosu
make calibrate ENGINE=/path/to/engine
make sprt A=L6 B=L5
python -m scripts.sprt_match --a L8-uniform --b L8   # özelliği kendi yokluğuna karşı
make notebooks      # beş araştırma notebook'unu çalıştır
```

Ayrıntılı bulgular: [`README.md`](../README.md) ve [`research/README.md`](../research/README.md).
