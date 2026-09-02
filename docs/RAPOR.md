# Atropos — yapılan işler ve son durum

**Repo:** `github.com/ercanholasoglu/Atropos` (private) · **69 commit** · 561 dosya
**Test:** 842 toplanıyor (17 slow ayrılıyor, 5 xfail) · mypy temiz — son tam koşu 2b bitince
**Ölçüm:** 232 koşu, **16.168 oyun**, hepsi commit hash'i ve CPU/RAM telemetrisiyle
**Showcase:** https://claude.ai/code/artifact/4f9ebb66-e882-451a-a152-470a9632e0b3

---

## 1. Verdiğiniz dört iş

### 1.1 Telemetri ✅
Her koşu artık duvar saati, CPU-saniye (tüm işçiler), node sayısı, tepe RAM, commit hash'i, işçi/zaman-kontrolü/max-plies ve sonucu `data/telemetry/` altına yazıyor. `scripts/telemetry.py`, beş araca bağlı.

**Uydurmadığım kısım:** telemetriden önceki 20 kaydın 16'sı `commit: null` + `"commit unknown"` olarak damgalandı. Çalışma ağacı proje boyunca kirliydi; bir dosyayı tarihe bakıp commit'e bağlamak, koşunun kullanmadığı bir commit'i adlandırmak olurdu.

### 1.2 Mutlak Elo çıpası ✅
Stockfish 18, **sabit derinlik** (SkillLevel değil — skill ayarları bilerek hata yaptırıp ölçülen güçle ilgisiz varyans ekler), Level 7'ye karşı, her biri 162 oyun.

| rakip | skor | L7'ye karşı | %95 aralık |
|---|---:|---:|---:|
| depth 1 | %47,5 | −17 | [−48, +13] |
| depth 2 | %58,6 | +61 | [+23, +100] |
| depth 3 | %60,2 | +72 | [+41, +104] |

Üçü 90 Elo'luk bantta toplanıyor: Stockfish'in "depth 1"i zaten quiescence ve NNUE taşıyor. **Bir motorun derinlik sayısı başka bir motorun aynı sayısıyla aynı işi adlandırmıyor.**

**Eşleme koşullu yazıldı:** R(d) = varsayılan mutlak reyting olmak üzere Level 7 = R(1)+17±30 / R(2)−61±39 / R(3)−72±31. R(d) bilinmiyor ve sabit derinlikli Stockfish hiçbir yayınlanmış listede yok — bu belirsizlik istatistiksel değil, oyun sayısıyla küçülmez.

**Asıl bulgu fazladan koyduğum eşleşmeden geldi:** aynı rakip L6'ya karşı −21. Fark → iki basamak 4 Elo arayla, etiketlerin 300 dediği yerde.

### 1.3 Yeniden kalibrasyon ✅
atropos, güncel merdivene karşı **480 oyun** (öncekiler 10-12'ydi). Yeni: **1518** (eval v3-rooks). Eskiler duruyor, etiketli: **1514** ve **1538** (ikisi de eval v2).

Implied rating'ler **361 Elo'ya yayılıyor ve aralıkları örtüşmüyor** — eski "saçılma gürültüdür" açıklaması on katı oyunla düştü.

### 1.4 Hız → Elo ✅
960 oyun, dört yarılanma, parantezler ve tahminler ilk oyundan önce commit'li. Sonuç uzun bir zincire dönüştü (§2.1).

---

## 2. İstenmeden çıkan, daha büyük bulgular

### 2.1 Hız eğrisi kendi aletini ölçüyormuş

Node bütçesi kolu −207 Elo/katlama verdi. Movetime çapraz kontrolü B/8'de ayrıştı. Üçüncü kol (saat yok, yalnızca iterasyon sınırında duran bütçe) **iki ön-kayıtlı tahminin de dışına düştü** ve çürütme şartını tetikledi.

İnceleme tek oyun gerektirmedi: **sert 5000 node'luk bütçe, yumuşak bütçenin 3422'de ulaştığı derinliğe ulaşmak için %46 fazla node harcıyor** — kestiği iterasyonu çöpe attığı için. Yani −207 aynı anda iki şeyi ölçüyormuş: bir node'un değeri ve ortasından kesilmenin bedeli.

| bütçe nasıl uygulanıyor | Elo/katlama | %95 aralık |
|---|---:|---:|
| sert node limiti | −207 | [−251, −164] |
| **saat** (gerçek oyunun durma biçimi) | **−171** | [−194, −149] |
| yumuşak node limiti | −98 | [−126, −69] |

Saat kolunu dört noktaya çıkarmak üç koşu daha aldı. Bir nokta 3,6σ aykırı göründü; **kusur noktada değil hata çubuklarındaydı** — saat kolunun harcaması koşudan koşuya %5,3 kayıyor, bu bir belge önce ölçülmüş ama yanlış büyüklüğe uygulanmıştı. Dahil edilince χ²=7,4 (3 sd), hiçbir nokta atılmadan uydu.

**Doğrulaması:** atropos 2,6 katlama yavaş → saat kolu −445 [−504, −386] öngörüyor, 480 oyunluk bağımsız gauntlet ~−440 ölçtü.

### 2.2 SPRT'nin durma noktasındaki sayı bir şeyin tahmini değil

Projenin kendi `Sprt` sınıfını gerçeği bilinen maçlara karşı koşturdum — nokta başına 3.000 maç, hiç satranç oynamadan.

**Erken durup H1 kabul eden bir koşu, gerçek fark 0 da olsa 100 de olsa ~110 raporluyor.** Yüz Elo'luk gerçek aralık boyunca tahmin beş Elo oynuyor.

- Küçük farkta: yanlılık saçılmanın 1,5 katı → sayı güvenilir biçimde yanlış
- Büyük farkta: yanlılık yok denecek kadar az ama saçılma 130-170 Elo (test bir düzine oyunda duruyor)
- **Reddetme tarafı da aynı:** gerçekten +50 Elo iyileştiren bir değişiklik merdivenin parantezinde yarıdan fazla reddediliyor ve reddedilince ~0 raporluyor

> **Hüküm kanıttır. Yanındaki sayı değildir.**

---

## 3. Bunun merdivene faturası

Her komşu eşleşme **sabit uzunlukta, durma kuralı olmadan** yeniden oynandı (1.960 oyun), sonra 0,1 sn'deki bütün oyunlar birlikte uyduruldu (`elo/joint.py`, Rao-Kupper ML, sentetik veriyle doğrulandı).

| eşleşme | oyun | sekans dedi | **ölçülen** | %95 aralık |
|---|---:|---:|---:|---:|
| L2 vs L1 | 600 | +361 | +420 | [+375, +479] |
| L3 vs L2 | 600 | +800 | +684 | [+603, +833] |
| L4 vs L3 | 240 | +361 | +390 | [+326, +482] |
| L5 vs L4 | 240 | +132 | +149 | [+103, +200] |
| L6 vs L5 | 240 | +361 | +527 | [+443, +682] |
| **L7 vs L6** | **240** | **+93** | **+22** | **[−22, +66]** |
| L8 vs L7 | 240 | −85 | −25 | [−69, +19] |

**Level 7, 0,1 sn/hamlede Level 6'dan ayırt edilemiyor.** Aynı cevaba dört bağımsız yol: ortak uyum +50 [−3, +103], dış motor 4 Elo, yanlılık simülasyonu +66'lık kayma öngörüyor (gözlenen +71), ve bu ölçüm.

### Ölçülmüş merdiven (`MEASURED_ELO`, kodda)

| aralık | ölçülen | %95 aralık | nominal | |
|---|---:|---:|---:|---|
| L1 → L2 | +423 | [+212, +634] | 400 | tutarlı |
| L2 → L3 | +682 | [+486, +877] | 300 | **dışarıda** |
| L3 → L4 | +407 | [+233, +581] | 300 | tutarlı |
| L4 → L5 | +178 | [+20, +336] | 300 | tutarlı |
| L5 → L6 | +637 | [+524, +750] | 300 | **dışarıda** |
| L6 → L7 | **+18** | **[−18, +53]** | 300 | **dışarıda** |
| L7 → L8 | −32 | [−75, +11] | 300 | **dışarıda** |

Gerçek merdiven altta dik çıkıyor, Level 4'te düzleşiyor, quiescence + TT'nin geldiği yerde sıçrıyor, **ve sonra duruyor.** Bir test iki ölçeğin uyuşmadığını iddia ediyor, yani merdiven sessizce "her basamak 300" demeye geri dönemez.

---

## 4. Değerlendirme programı — kapandı

**3.672 A/B oyunu, beş varyant, hepsi sabit uzunlukta.**

| varyant | oyun | v2'ye karşı | nps |
|---|---:|---:|---:|
| `v3-rooks` — **motorda duran** | 600 | −2 [−26, +22] | 60.337 |
| `v3-passers` | 714 | +11 [−12, +34] | — |
| `shelter-only` | 558 | **−53 [−84, −24]** | 58.138 |
| `passers-rooks` | 1.200 | +12 [−8, +31] | 53.556 |
| `v3-shelter` (üçü) | 600 | +21 [−5, +47] | 49.064 |

**Tam olarak bir aralık sıfırı dışlıyor — ve o da negatif tarafta.** Hiçbir şeyin değerlendirmeyi iyileştirdiği gösterilemedi; bir terimin kötüleştirdiği gösterildi.

**Ve proje bunu baştan söylemişti.** Erken ölçülen çözünürlük tabanı: ≥100 Elo 7-65 oyunda, ≥20 ~1.500'de, ≥10 ~6.000'de çözülür. Klasik terimler +10/+25 eder. En iyi adaya 1.200 oyun +12 [−8, +31] döndürdü — **tablo tam olarak bunun olacağını söylüyordu.**

Program terimler değersiz olduğu için başarısız olmadı; bu boyuttaki etkiler harcanandan binlerce oyun fazlasını istiyor. Karşılaştırma: throughput işi **+83 Elo** üretti, oyunların bir kesriyle.

---

## 5. Motorda ters duran iki karar (sizin kararınız)

| | durum | kanıt |
|---|---|---|
| Kale terimi | **AÇIK** | +44 sekans sayısından; 600 sabit oyun **−2 [−26, +22]** diyor, aralık +44'ü dışlıyor |
| SEE budaması | **KAPALI** | **+50 [+30, +70]**, 1.200 sabit oyun — projedeki tek onaylanmış pozitif etki |

Bugünkü kanıta göre ters. **Hiçbirini tek başıma değiştirmedim:** Level 7, mevcut bütün sayıların alındığı ölçüm aleti; birini açmak o sayıların neyi tarif ettiğini yeniden yazar.

### SEE çözüldü: +50 [+30, +70]

1.200 sabit oyun, ön-kayıtlı her ölçüt tuttu (nokta +40..+60 → **+50**; aralık ~[+30,+70] → **[+30,+70]**).

**Asıl kazanılan sayı budamanın bedeli.** Deterministik sayım yalnızca throughput'tan **+65** öngörüyordu; maç **+50** diyor. **Aradaki +15, budamanın doğrulukta maliyeti** — ve bu sayıyı projede başka hiçbir şey üretemez, çünkü aynı değişikliğin hem sayılmış hem oynanmış ölçümünü gerektiriyor.

Ve iki adayın davranışı gerçek etki ile gürültüyü ayırıyor:

| | 240 | 600 | 1.200 |
|---|---:|---:|---:|
| `passers-rooks` | — | +26 [+1, +51] | **+12 [−8, +31]** |
| **SEE** | +48 [+11, +87] | +46 [+20, +73] | **+50 [+30, +70]** |

Biri düştü ve aralığı sıfırı yuttu; diğeri kıpırdamadı ve aralığı sıfırdan uzaklaşarak daraldı. İkisi de **sabit uzunlukta koştuğu için** ayırt edilebiliyor — sekans testi ikisi için de ~+110 raporlardı.

### Bayrağı açmanın faturası (`scripts/see_impact.py`)

Endişe yerine tablo. Ortak uyum `L7-see`'yi zaten aynı ölçeğe yerleştirdiği için hepsi mevcut ölçümlerden türetiliyor — yeni oyun gerekmedi. (Uyum **+62 ± 10** diyor, doğrudan A/B **+50** — iki yol, 12 Elo arayla, örtüşen ama aynı olmayan oyunlardan.)

| ölçüm | şimdi | SEE açıksa |
|---|---:|---:|
| merdiven L6 → L7 | +18 | **+80** |
| merdiven L7 → L8 | −32 | −94 |
| Stockfish d1 vs L7 | −17 | −79 |
| Stockfish d2 vs L7 | +61 | −1 |
| L6 altındaki bütün aralıklar | — | **değişmez** |
| değerlendirme A/B'leri (hepsi L6'da) | — | **değişmez** |
| hız eğrisi | — | **yeniden ölçülmeli** |
| benchmark | — | yeni baseline |

Okunuşu:
- **L6 → L7, +18 [−18, +53]'ten (sıfırdan ayırt edilemiyor) ~+80'e** çıkardı — yani gerçek bir basamak olurdu.
- Çıpanın bütün satırları aynı miktar kayıyor: mutlak Elo eşlemesi **kayar ama belirsizliği değişmez** — R(d) zaten bilinmiyordu, yine bilinmiyor olurdu.
- **Yeniden koşulması gereken tek şey hız eğrisi**, çünkü SEE aramanın *hangi* node'ları ziyaret ettiğini değiştiriyor, yalnızca hızını değil (~960 oyun).
- Geri kalan her şey, ölçtükleri motor için geçerli kalan sayıları **yeniden etiketlemek**.

---

## 6. Araçlar (hepsi yeni)

| araç | ne yapar |
|---|---|
| `scripts/telemetry.py` | her koşuyu commit + kaynak kullanımıyla kaydeder |
| `scripts/anchor.py` | sabit derinlikli dış motora karşı çıpa |
| `scripts/speed_elo.py` | hız → Elo, üç uygulama kolu, parçalı devam |
| `scripts/sprt_bias.py` | durma kuralının kendisini simüle eder |
| `elo/joint.py` + `scripts/rating_fit.py` | bütün oyunları birlikte uydurur, kendi zayıf varsayımını raporlar |
| `engine/search/see.py` | static exchange evaluation (atropos Faz 17'nin tek eksiğiydi) |
| `scripts/bench.py` | **"daha hızlı" ile "farklı"yı ayırır** — node sayısı değiştiyse nps bir hız karşılaştırması değildir, ve öyle der |
| `scripts/build_tactics.py` | taktik pozisyonları Stockfish'le üretip doğrular |
| `scripts/gen_showcase.py` | showcase sayfasını sayılardan üretir |

`calibrate` ve `sprt_match` kesintiye dayanıklı hale getirildi (atomik checkpoint, `--minutes` bütçesi, parça içinden devam, `--fixed` modu).

---

## 7. Sicil

**13 ön-kayıtlı tahmin, 6'sı tutmadı.** Tutmayanlar dahil hepsi kayıtlı ve yayında.

**8 geri alınan iddia**, ikisi bu oturumda benim yayınladıklarım:
1. "Level 8 bir gerileme" — aralık sıfırı içeriyordu
2. Çifte sayma açıklaması — −3'ten çıkarılmıştı, 100 oyun sonra +21'e taşındı
3. "İki aday mekanizma" — bağımsız değillermiş
4. "Merdivenin Elo sütunu tahmindir"
5. "B/2 3,6σ aykırı" — kusur hata çubuklarındaydı
6. "Kral güvenliği en değerli terim" — varyantın adına güvenip ne inşa ettiğini okumamışım
7. "Kale terimi +44 eder"
8. "passers-rooks +26, ilk pozitif sonuç" — doğrulama +12 [−8, +31] döndürdü

Ayrıca bir süreç ihlali kaydettim: zaman kontrollü maç sürerken test süitini çalıştırdım, 13 test düştü — projenin kendi kuralıydı.

---

## 7.5 Tezgâhın kendisi sınandı

On beş bin oyun, sıfırı hiç kontrol edilmemiş bir alette oynanmıştı. **Level 7'ye karşı
Level 7, 600 oyun: %51,50, +10,4 Elo [−17, +38].** Elo dönüşümünden geçmeyen ham skorda
z = +0,73, **p = 0,46**. **Tezgâhın bu çözünürlükte ölçülebilir bir eğimi yok.**

Bu, geri kalanı meşrulaştırıyor: renk sırasında, açılış kitabında, tohumlamada ya da
skorlama yolunda bir yanlılık, bu projenin oyunlarını harcadığı etkilerle *aynı
büyüklükte* burada görünürdü — SEE'nin +50'si, merdivenin tepedeki +18'i, değerlendirme
terimlerinin +10/+25'i. Hiçbiri, bunun dışladığının yarısı kadar eğimli bir tezgâhta
ayakta kalmazdı.

Sertifika değil: aralık ±28, yani 10-15 Elo'luk bir eğim yakalanmazdı — ve burada ölçülen
en küçük etkiler tam o boyutta. Ayrıca **iki kolu eşit etkileyen** bir yanlılığı göremez;
temsili olmayan bir açılış kitabı görünmez, çünkü iki taraf da aynı kitabı oynuyor.

Bu koşu **bir hatam yüzünden var.** İşlevsel olarak aynı iki motor arasında 49 Elo'luk
bir fark gördüm ve hata payına *sonra* baktım: ±51, sıfırı rahatça kapsıyor. İşaret
yanlıştı; kazara sorduğu soru değildi.

## 7.6 Alet v2 — tek kesit (2026-09-01)

Tek commit, `alet-v2` etiketli: **SEE açık, kale terimi çıkarıldı.** Ayrı ayrı değil, çünkü
ayrı ayrı iki yeniden çıpalama ve arada tanımsız bir alet demek. Hiçbir şey silinmedi —
`positional_score_rooks` v1 değerlendirmesini tutuyor, v1 kayıtları `data/v1/`'de.

**Patlama yarıçapı akıl yürütülmedi, ölçüldü:** L1–L4 bit-birebir aynı (benchmark 24
pozisyonun 24'ünde aynı node), L5 yalnız kale teriminden, L6–L8 ikisinden. L7 aynı
derinlikte %38 daha az node arıyor.

### Kesitin doğrudan ölçümü: **600 oyun, +80 Elo [+52, +109]**

L7-v2, süreç içinde yeniden inşa edilmiş L7-v1'e karşı; rekonstrüksiyon oyun oynanmadan
doğrulandı. `see_impact.py` ortak uyumdan **+62** (aralık içinde), doğrudan A/B'den **+50**
(dışında) öngörmüştü. **Kesit, ayrı ölçülmüş parçalarının toplamından fazla** — SEE kale
terimini hâlâ taşıyan bir L7'de, kale terimi ise L6'nın aramasında ölçülmüştü; bu
kombinasyon hiç oynanmamıştı.

| eşleşme | alet v1 | **alet v2** |
|---|---:|---:|
| L5 vs L4 | +149 | **+160** [+125, +206] |
| L6 vs L5 | +527 | **+651** [+644, +1190] |
| L7 vs L6 | +18 [−18, +53] | **+41 [+3, +80]** |
| L8 vs L7 | −32 | **0** [−36, +36] |
| atropos rating | 1518 | 1518 (değişmedi; alet ±65 Elo, göremez) |

### Çıpa uyuşmadı — ve sebebi metodolojik

Üç derinlik havuzlanınca çıpa "L7 **+1 ± 14** değişti" diyor, doğrudan ölçüm +80. **3,3σ.**
İki sorun: (1) kendi içinde tutarsız — d1/d2 zayıfladı, d3 güçlendi diyor; (2) **dönüşümü
beraberlikleri yok sayıyor, eşleşmeler üç oyunun ikisini berabere bitiriyor.** Simülasyon:
%67 beraberlikte gerçek 100 Elo **+52** okunuyor. **Çıpanın yayınladığı her sayı ~iki kat
sıkışmış** (d1 −17→−32, d3 +72→+136). Düzeltmek tutarsızlığı çözmüyor: çıpa bu boyuttaki
farkı 162 oyunla göremiyor. İşi mutlak yerleştirme, fark tespiti değil.

### Hız eğrisi yeniden ölçüldü

960 oyun: **−162 [−198, −127]**, v1'in −171 [−194, −149]'una karşı. Aralıklar örtüşüyor —
**bir katlamanın değeri değişmedi**, motor mutlak olarak hızlanmış olsa da (aynı saatte
4.827 node, v1'de 6.144). Dönüştürdüğü aramada bir değişikliğe rağmen ayakta kaldı.

## 7.7 Uzun zaman kontrolü: 2a — mekanizma derinlikmiş

Ön-kayıt koşudan önce commit'lendi, içindeki her sayı önce ölçüldü.

**Gerekçe:** L7'nin L6'ya derinlik avantajı **0,1 sn'de 0,25 pli**, 1,0 sn'de **1,00 pli**.
Null-move ve LMR derinlik satın alan kumarlar; 0,1 sn'de kumar ölçülüyor, ödülü ölçülmüyordu.

**Sonuç: 300 oyun, 1,0 sn, %67,17, +124 Elo [+84, +168].**

| ölçüt | ilan edilen | ölçülen |
|---|---|---|
| nokta tahmini | +90…+150 | **+124** ✓ |
| aralık | ~[+50, +190] | [+84, +168] ✓ |
| 0,1 sn'deki +41 dışlansın | — | **dışlandı** ✓ |

Tahmin 84 oyundan beri kararlı, aralık daralıyor — gerçek etkinin şekli.

**Projeye faturası:** bu depodaki her maç 0,1 sn'de oynandı, yani L7'yi tanımlayan
tekniklerin neredeyse hiç devreye girmediği bir saatte. Eski sayılar geçersiz değil —
ölçüldükleri saat için doğrular — ama **neye genellendikleri** değişti.

## 7.8 Bileşen loglama (madde 5b)

`engine/evaluation/breakdown.py`: değerlendirme materyal / yerleşim / piyon yapısı / fil
çifti olarak ayrılıyor. **Sözleşme: parçalar motorun hesapladığına birebir eşit.** Test bunu
yüzlerce pozisyonda kontrol ediyor ve hemen işe yaradı — ilk sürümüm kale terimini toplama
katıyordu, 480 pozisyonun 131'i uyuşmadı. Kale terimi ve kral güvenliği artık **toplamın
dışında** raporlanıyor.

`sprt_match --log-components` hamle başına bir JSON satırı. **Bir sıralama hatası çıktıyı
okuyarak bulundu:** maçın hamle kancası hamle *oynandıktan sonra* ateşleniyor, yani
loglanan tahta hamle sonrası — oysa depth/nodes/pv hamle öncesini tarif ediyor. Kayıt artık
ikisini de taşıyor, ayrışım öncekinden alınıyor.

## 8. Açık kalanlar

| konu | durum |
|---|---|
| Mutlak Elo | Dış bağımlılık: CCRL listesindeki motor + gerçek zaman kontrolü, ya da Lichess bot havuzu |
| SEE'nin büyüklüğü | ✅ **+50 [+30, +70]**, ikinci kitapta +62; artık motorda |
| İki ters karar | ✅ **alet v2 kesitiyle çözüldü** (§7.6): SEE açık, kale terimi çıktı |
| v3-passers, L8'in saati | Çözülmedi — ve "çözülmedi" ≠ "reddedildi" |
| Zobrist deneyi | **Başlatmadım** — ön-kaydı sizde |

atropos'un faz listesinde açık teknik boşluk kalmadı.
