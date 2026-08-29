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

#### "Hedef Elo" sütunu bir isim listesi

Basamaklar 300 Elo arayla etiketli. **Bu projede bunu hiçbir ölçüm doğrulamadı, ve
elimizdeki ölçümler aksini söylüyor.**

Yukarıdaki eşleşmelerin hepsi `elo0=0, elo1=100` parantezinde koştu. "Kabul", *bu fark
0'dan çok 100'e benziyor* demek — bir **sıralama** testi. 300'ün testi değil ve öyle
okunamaz. Aralığın sansürlenmediği yerlerde ölçülen fark etiketin çok altında: L7 vs L6
**+93 [+21, +174]**, L5 vs L4 **+132 [+45, +240]** — ikisinde de nominal 300'e karşı.

Sabit derinlikli Stockfish aynı şeyi dışarıdan söylüyor (`docs/ANCHOR.md`): Level 7'ye
karşı −17 Elo, Level 6'ya karşı −21 Elo. Yani iki basamak **4 Elo arayla, aralık
[−47, +40]** — etiketlerin 300 dediği yerde. Biri içeriden biri dışarıdan iki alet, ve
hiçbiri isimlerin iddia ettiği aralığı bulmuyor.

Sayılar `INITIAL_ELO`'dan geliyor; kuruluşta **hedef** olarak atanmışlar. Her seviyenin
*nişan aldığı* şey onlar. "Hedef Elo" sütununu olduğu gibi — bir şartname olarak — okuyun;
"Ölçülen" sütunu ise ortaya atılan tek iddia: **merdiven sıralı, ve sıralama doğrulandı.
Aralıklar doğrulanmadı.**

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

atropos'u kendi merdivenimize karşı oynattık (0.3sn/hamle, sabit zaman kontrolü).
Üç koşu yapıldı; ilk ikisi **evaluation v2** ile (kale terimi benimsenmeden önce),
basamak başına 10-12 oyunla:

```
1. koşu (hızlanma öncesi, eval v2, 72 oyun)   performance rating: 1514
2. koşu (hızlanma sonrası, eval v2, 40 oyun)  performance rating: 1538
```

Üçüncü koşu, kale terimi ship edildikten sonra, **bugünkü merdivene karşı** ve bu sefer
basamak başına **10 değil 120 oyunla** — çünkü öncekilerin standart hatası ~110 Elo'ydu
ve sayılar sanki değilmiş gibi okunuyordu:

| eşleşme | oyun | skor | W-D-L | implied | %95 aralık |
|---|---:|---:|---:|---:|---:|
| atropos vs L4 | 120 | %74.6 | 60-59-1 | 1387 | [1321, 1468] |
| atropos vs L5 | 120 | %61.3 | 45-57-18 | 1580 | [1518, 1647] |
| atropos vs L6 | 120 | %11.2 | 5-17-98 | 1441 | [1309, 1523] |
| atropos vs L7 | 120 | %11.7 | 1-26-93 | 1748 | [1620, 1830] |

**Performance rating: 1518** (eval v3-rooks, 480 oyun). 1538 ve 1514'ün yanında bu
"istikrar" gibi görünüyor — ve öyle okumak bu bölümdeki üçüncü hata olurdu.

Onun yerine implied sütununa bakın. **361 Elo'ya yayılıyorlar**, ve basamak başına 120
oyunda **aralıkları örtüşmüyor**: L4 [1321, 1468] diyor, L5 [1518, 1647] — aralarında
hiçbir şey yok. Eski metin bu saçılmayı örnekleme gürültüsüne bağlıyordu ("12 oyunun
standart hatası ~%14"). **On katı oyun aksini söylüyor.** Saçılma gürültü değil, yapı —
ve anlamı şu: atropos'u bu merdivene karşı tek bir sayı tarif etmiyor.

Bir rating, ancak rakiplerinin rating'i kadar iyidir. Denklemi ters çevirip atropos'u
sabit alalım ve her basamağın ona göre nerede durduğunu soralım:

| aralık | nominal | bu gauntlet (480 oyun) | merdivenin kendi SPRT'si |
|---|---:|---:|---:|
| L4 → L5 | 300 | **+107** [+11, +204] | +132 [+45, +240] |
| L5 → L6 | 300 | **+438** [+319, +557] | +361 [+134, +800] |
| L6 → L7 | 300 | **−7** [−148, +134] | +93 [+21, +174] |

Ortak kod yolu olmayan iki alet birbiriyle uyuşuyor ve etiketlerle **iki yönde birden**
uyuşmuyor. Quiescence, TT, killer ve MVV-LVA'nın hep birlikte geldiği L5 → L6 basamağı
etiketinin bir buçuk katı. L6 → L7 basamağı ise hiç yok. **300, üç aralığın da ölçülen
güven aralığının dışında.**

Sabit derinlikli Stockfish — ikisiyle de bağlantısı olmayan bir motor — son satırı aynı
okuyor: 4 Elo, [−47, +40] (bkz. 3.2).

Yani atropos hakkında dürüst ifade bir rating değil, şu: **Level 5 ile Level 6 arasında,
Level 5'e yakın oynuyor; ve o iki basamağın arası isimlerinin iddia ettiği 300 değil,
yaklaşık 440 Elo.**

**İlginç olan nerede durduğu değil, neden orada durduğu.** atropos'ta L6'nın sahip olduğu
her şey var — quiescence, TT, killer, MVV-LVA — ve 120 oyunda L6'ya karşı %11.2 alıyor.
Sahip olmadığı şey hız: **8.938 node/sn'ye karşı ~54.000**.

> *Özellik paritesi, throughput'a yeniliyor — ve bedeli, artık etiketten değil ölçümden
> okunduğunda, yaklaşık 440 Elo.*

Bu sayılar hâlâ merdivenin birimlerinde. Bu gauntlet merdivenin **aralıklarını** ölçtü;
tüm ölçeğin nerede oturduğunu değil. Onun için bilinen ratingli bir motor gerekir (3.2).

### 3.2 Mutlak çıpa: Stockfish sabit derinlikte

Sabit **derinlik**, `Skill Level` değil: skill ayarları motoru bilerek hata yaptırıyor,
ve kasıtlı hatalar ölçülen güçle ilgisi olmayan varyans ekliyor. Sabit derinlik
tekrarlanabilir bir rakip.

Level 7'ye karşı, her biri 162 oyun, bizim tarafta 0.1sn/hamle:

| rakip | skor | L7'ye karşı Elo | %95 aralık | SPRT |
|---|---:|---:|---:|---|
| Stockfish depth 1 | %47.5 | −17 | [−48, +13] | hüküm yok |
| Stockfish depth 2 | %58.6 | +61 | [+23, +100] | kabul |
| Stockfish depth 3 | %60.2 | +72 | [+41, +104] | kabul |

Depth 1 ile Level 7 eşit. Depth 2 ile 3 birbirinden ayırt edilemiyor. Üçü de 90 Elo'luk
bir bantta, çünkü Stockfish'in "depth 1"i zaten quiescence ve NNUE taşıyor — gücünün
çoğu ilk plide mevcut, sonraki ikisi az şey ekliyor.

> *Bir motorun derinlik sayısı, başka bir motorun aynı sayısıyla aynı işi adlandırmıyor.*

Masrafını çıkaran eşleşme fazladan olanıydı: **aynı rakip Level 6'ya karşı**. Orada −21,
L7'ye karşı −17 — yani iki basamak **4 Elo arayla, aralık [−47, +40]**, etiketlerin 300
dediği yerde. Yukarıdaki 2.1'deki düzeltme buradan çıktı.

**Vermediği şey mutlak reyting.** Sabit derinlikli Stockfish hiçbir yayınlanmış listede
yok — CCRL ve CEGT motorları zaman kontrolünde reytingliyor. Bu yüzden Level 7'nin
mutlak Elo'su ancak koşullu yazılabilir: kullanılan Stockfish yapılandırmasının varsayılan
mutlak reytingi R(d) olmak üzere, Level 7 = R(1) + 17 ± 30, ya da R(2) − 61 ± 39, ya da
R(3) − 72 ± 31. Bu ±'lar istatistiksel kısım, oyun sayısıyla küçülür. R(d) ise buradaki
hiçbir oyunun küçültemeyeceği kısım; onun için CCRL listesindeki bir motora karşı gerçek
zaman kontrolü ya da Lichess bot havuzu gerekir. Ayrıntı: `docs/ANCHOR.md`.

### 3.3 Hız: +%39, bedavaya

Profil tek bir şeyi yüksek sesle söyledi: **199.916 node için 1.318.794 hamle üretimi**
— node başına 6.6, bir tane yeterken. Quiescence tüm legal listeyi kurup alışlara
filtreliyordu, ve quiescence node'ların %69'u.

| | nps |
|---|---:|
| önce | 41.817 |
| forcing hamleleri doğrudan üret | 51.000 |
| + bitboard piyon yapısı | **58.138** |

Aynı ağaç, aynı node sayısı (108.966). Hamle üretimi node başına 6.6'dan 2.1'e düştü.

### 3.4 Hız → Elo: bir katlama kaç Elo?

Bu projedeki her optimizasyon node/sn cinsinden raporlandı — kimsenin umursadığı bir
birim değil. Level 7'yi kasten yavaşlatılmış kopyasına karşı oynattık; node bütçesi dört
kez yarılandı, eşleşme başına 240 oyun, toplam 960. **Parantezler, tahminler ve
çürütülebilir iddia ilk oyundan önce commit'lendi** (`b84fd6e`).

| bütçe | ölçülen | %95 aralık | tahmin |
|---|---:|---:|---:|
| B/2 | **−159** | [−212, −113] | −60 |
| B/4 | **−417** | [−518, −349] | −120 |
| B/8 | **−636** | [−911, −532] | −180 |
| B/16 | **−830** | [−2400, −678] | −240 |

**Katlama başına −207 Elo, aralık [−251, −164].** En küçük kareler fit'i ±5 diyor ama o,
dört noktayı kesin sayıyor; noktaların kendi hataları ±25 ile ±153 arasında. Yayılmış
aralık doğru olanı.

> **Alıntılamadan önce niteliğini okuyun.** Üçüncü bir kol (aşağıda) bu −207'nin *sert*
> node bütçesine özgü olduğunu gösterdi — sert bütçe kestiği iterasyonu çöpe atıyor.
> Kullanılacak sayı saat kolununki: **−171 [−194, −149]**, 0.34-2.04 katlama aralığında
> dört noktadan. Nasıl varıldığı — bir noktanın 3.6σ aykırı görünüp sonra hata
> çubuklarının dar olduğunun anlaşılması dahil — `docs/SPEED_CLOCK2_PREREG.md`'de.

Her nokta tahminini **aynı yönde ve iki buçuk kat** ıskaladı. Tahminler klasik motorlar
için yayınlanmış katlama eğrilerinden geliyordu (50-70 Elo) — ama onlar uzun zaman
kontrollerinde, zaten on beş plilik bir aramaya bir pli eklendiğinde ölçülüyor. Burada
referans bütçe derinlik 3.0'a, B/2 ise 2.0'a ulaşıyor: bir katlama, üç hamlelik taktiği
görmekle görmemek arasındaki fark.

> *Katlama başına Elo motorun sabiti değil; eğrinin hangi bölgesinde ölçtüğünün özelliği.*

Ön-kayıtlı iddia — log2(bütçe)'de doğrusallık — ayakta: artıklar +48, −2, −14, −1, nokta
hataları ±25-±153 iken.

#### Çapraz kontrol uyuşmadı

Aynı yarılanmalar **movetime** bölmesi olarak da koşuldu; ikisinin aynı yavaşlatmanın iki
yazılışı olduğu varsayımıyla. B/2'de uyuşuyorlar. B/8'de hiç örtüşmüyor:
−636 [−911, −532] karşısında **−332 [−409, −273]**.

Her bütçenin gerçekte ne harcadığını ölçünce sebep çıkıyor. **Movetime'ın sekize bölmesi,
node'un dörde bölmesi:** 0.09 sn 6144 node alıyor (node kolunun başladığı 5000 değil), ve
11 ms'de harcama 569 ile 2048 node arasında geziniyor — üst ucu tam olarak bir
`check_interval`. Saat, deneyin değiştirdiği büyüklüğü hiç bölmüyormuş.

Bunu düzeltmek B/2'yi kapatıyor, B/8'de ~90 Elo açıkta kalıyor. Sebebini bulmak için
üçüncü bir kol kuruldu — ve aradığı cevaptan iyisini buldu.

#### Üçüncü kol: aradığı cevabı değil, aletin kendisini buldu

Kol: **yalnızca iterasyonlar arasında** uygulanan node bütçesi; saat hiç yok, yani
zamanlamayla ilgili hiçbir şey işin içinde olamaz. Ön-kayıtta 92 Elo arayla iki sonuç
ilan edildi (`docs/SPEED_ARM3_PREREG.md`). **İkisinin de dışına düştü:** −349 ve −257
tahminlerine karşı **−165 [−213, −122]**. Ön-kaydın çürütme şartı işledi: incelenecek
şey eğrinin kendisi.

İnceleme tek bir oyun gerektirmedi:

| bütçe | uygulama | harcanan node | ulaşılan derinlik |
|---|---|---:|---:|
| 5000 | sert | 5000 | 3.00 |
| 2000 | yumuşak | 3422 | 3.00 |
| 5000 | yumuşak | 13567 | 4.00 |

**Sert 5000'lik bütçe, yumuşak bütçenin 3422 node'da ulaştığı derinliğe ulaşmak için
%46 fazla node harcıyor** — çünkü iterasyonun ortasında kesiliyor ve o iterasyon çöpe
gidiyor. Bu, deneyin yalnızca referansında değil her basamağında geçerli.

Yani −207 aynı anda iki şeyi ölçüyormuş: bir node'un değeri, ve ortasından kesilmenin
bedeli. Ayırınca:

| bütçe nasıl uygulanıyor | gerçek katlama başına Elo | %95 aralık |
|---|---:|---:|
| sert node limiti (4 nokta) | −207 | [−251, −164] |
| **saat** (4 nokta; 0.34-2.04 katlama) | **−171** | [−194, −149] |
| yumuşak node limiti (1 nokta) | −98 | [−126, −69] |

Saat satırını dört noktaya çıkarmak projenin en uzun ipiydi. Üçüncü nokta orijinden
geçme varsayımını reddetti (χ² = 13.8, 2 sd); dördüncüsü sapmanın tamamını B/2'de
yalıttı; B/2'yi hiç oynanmamış oyunlarla tekrarlayınca −201'den −116'ya taşındı —
**aynı eşleşmenin iki koşusu p = 0.015 ile ayrışıyor.**

Kusur noktada değil hata çubuklarındaydı. Her nokta yalnızca binom gürültüsü taşıyordu;
oysa saat kolunun node harcaması koşudan koşuya %5.3'e varan oranda kayıyor — hiçbir
binom aralığının içermediği ±13 Elo daha. Bu kayma bir belge önce **zaten ölçülmüş ve
yazılmıştı**; ama eğim tahminine uygulandı (orada hiçbir şey değiştirmedi), nokta
hatalarına değil — oysa uyum iyiliği testi orada yaşıyor. Dahil edilince: **χ² = 7.4,
3 sd, hiçbir şey reddedilmiyor, hiçbir nokta atılmıyor.**

Sert ile yumuşak örtüşmüyor; saat ikisinin arasında ve sert koldan ayrılamıyor. Yani
**bu ölçümde bütçenin nasıl uygulandığı birinci derecede bir değişken** — uçlar arasında
gösterildi; üçünün kesin sıralaması değil. Sert node bütçesi bir deney aleti; hiçbir şey
öyle oynamıyor.

Bu belgedeki eski "iki aday mekanizma" çerçevesi yanlıştı ve ön-kayıtta düzeltildi:
iterasyon sınırında uygulanan bir bütçe **zorunlu olarak** değişken node harcar, yani
"değişken bütçe" ile "sınırda duruyor" tek mekanizmanın iki adıydı. Bu, veriden değil
aleti kurmaya çalışmaktan çıktı. Tam yazım: `docs/SPEED.md`.

#### Projenin geri kalanına faturası

Saat kolu üzerinden (gerçek oyunun durma biçimi):

| iddia | katlama | dönüşüm | doğrudan ölçülen |
|---|---:|---:|---:|
| atropos bu motora karşı | 2.60 | **−445** [−504, −386] | ≈ −440 ✓ |
| +%39 hızlanma | 0.48 | **+81** [+71, +92] | — |
| SEE budaması | 0.38 | **+66** [+57, +74] | +48 [+11, +87] ✓ |

Bağımsız ölçümü olan iki satır da eğriyle uyuşuyor. atropos'unki daha güçlü kontrol:
480 oyunluk gauntlet L6'ya açığını ~−440 ölçtü, tamamen başka oyunlardan kurulmuş bir
dönüşüm −445 öngörüyor. Özellik paritesi throughput'a yeniliyor, ve bu yenilginin
büyüklüğü artık iddia değil öngörü.

### 3.5 Evaluation v3: demet düştü, içindeki bir terim ship edildi

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

### 3.6 TDLeaf(λ): 10.000 oyun

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

### 3.7 Minimal NNUE: gecikme sütunu tartışmayı bitiriyor

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

### 3.8 AlphaZero-lite: hamle kodlaması tasarımın %96'sı

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

### 6.1 Acil (teknik olmayan) ✅ kapandı

Her iki repo da artık versiyon kontrolünde. chess-bot `Atropos` adıyla
`github.com/ercanholasoglu/Atropos` üzerinde (private), C++ ağacı `cpp/` altında
`cpp/PORTING.md` eşlemesiyle. Her koşu artık commit hash'i ile kaydediliyor
(`data/telemetry/`); telemetriden önceki 16 kayıt `commit unknown` olarak damgalandı —
uydurulmadı, çünkü çalışma ağacı proje boyunca kirliydi.

### 6.2 Merdiven ✅ sıralı, ⚠️ aralıkları değil

Yedi eşleşmenin hepsi karara bağlandı; merdiven L7'ye kadar **sıralı**. Ama 2.1'de
yazıldığı gibi **aralıkları hiç ölçülmemiş** — üç bağımsız alet (merdivenin kendi
SPRT'leri, atropos gauntlet'i, sabit derinlikli Stockfish) nominal 300'ün üç basamakta da
güven aralığının dışında kaldığını söylüyor.

**Level 8 açık kalıyor.** Ölçülebilir üstünlüğü yok ve olması da beklenmez: L7'nin
araması artı bir zaman heuristiği. Uyarlanabilir saatin yardım mı zarar mı ettiği hâlâ
açık (54 oyun, [−99, +72]).

### 6.3 atropos'un fazları (Python'da)

| Faz | Konu | Durum |
|---|---|---|
| 17 | Evaluation v3 | ✅ ölçüldü; demet reddedildi, **v3-rooks +44 ile ship edildi** |
| 17 | Static exchange evaluation | ✅ yazıldı + ölçüldü; **bayrak kapalı**, bkz. `docs/SEE_PREREG.md` |
| 18 | Search v2 | ✅ L7'de zaten var (null-move, LMR, aspiration, check extension) |
| 19 | Turnuva zaman yönetimi | ✅ `uci/time_manager.py` |
| 20 | Profilleme + NPS | ✅ +%39; artık Elo'ya çevrilebiliyor (−207/katlama) |
| 21 | Taktik suite | ⚠️ 8 pozisyon — atropos'un "larger tactical suite" maddesi açık |
| 22 | Benchmark baseline | ⚠️ telemetri var, ayrı bir `bench` komutu yok |
| 23 | Kalibre Elo hattı | ✅ `elo/sprt.py` + `scripts/calibrate.py` + `scripts/anchor.py` |
| 24-31 | NNUE hattı | `research/minimal_nnue` çekirdek soruyu cevapladı: bu ölçekte ödemiyor |

atropos'un kendi durum belgesi ölçüm için **cutechess-cli + Stockfish skill level**
öneriyor. İkisini de kullanmadık, ikisi de gerekçeli: cutechess yerine protokolü doğrudan
konuşmak bir kurulum adımını kaldırdı (2.3), ve skill level yerine **sabit derinlik**
seçildi çünkü skill ayarları kasten hata yaptırıp ölçülen güçle ilgisiz varyans ekliyor
(3.2).

### 6.4 Açık sorular

- **Athena entegrasyonu** — ayrı repo + showcase mı, Athena içinde bir surface mi?
- **Mutlak Elo** — hâlâ açık. Sabit derinlikli Stockfish merdivenin *aralıklarını* ölçtü
  ama ölçeğin nerede oturduğunu değil; onun için CCRL listesindeki bir motora karşı
  gerçek zaman kontrolü ya da Lichess bot havuzu gerekir (`docs/ANCHOR.md`).
- **SEE'nin büyüklüğü** — çözülmedi, [+11, +87]. Pozitif olduğu iki koşuda da kesin;
  ne kadar olduğu değil.
- **SEE ship edilsin mi** — veri sorusu değil: L7, bu haftaki çıpanın ve gauntlet'in
  ölçüm aleti. Açılırsa mevcut bütün sayıların "SEE öncesi" diye etiketlenmesi gerekir.
- **v3-passers** — 714 oyunda çözülmedi, [−12, +34]; ~+10'luk etki için dar bracket gerek
- **L8'in uyarlanabilir saati** — çözülmedi, dar bracket ile yeniden denenmeli
- **Hız → Elo'nun açık ucu** ✅ kapandı — üçüncü kol sapmanın saatte değil, bütçenin
  *nasıl uygulandığında* olduğunu gösterdi. Sert node limiti kestiği iterasyonu çöpe
  atıyor ve %46 fazla node harcıyor; −207 bunu da ölçüyormuş. Gerçek dönüşüm sayısı
  **−174 [−203, −144]** (`docs/SPEED_ARM3_PREREG.md`).
- **Üç kolun kesin sıralaması** — sert ile yumuşak ayrıştı, saat ikisinden de
  ayrılamadı. Saat kolu iki noktadan geliyor; daha çok nokta aralığı daraltır.

---

## 7. Hızlı referans

```bash
make test           # 724 test, ~45sn
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
