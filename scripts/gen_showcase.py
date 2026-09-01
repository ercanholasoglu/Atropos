"""Generate the Atropos measurement showcase.

Interval-bar positions are computed here rather than in the page so the
published file needs no script to draw its main visual device.
"""

from pathlib import Path

OUT = Path.home() / "Projects/chess-bot/docs/showcase.html"


def bar(lo, est, hi, scale_lo, scale_hi, pred=None, zero=True):
    """One confidence-interval bar as markup, positioned on a shared scale."""
    span = scale_hi - scale_lo

    def pct(v):
        return max(0.0, min(100.0, (v - scale_lo) / span * 100))

    parts = [
        f'<span class="ivl-range" style="left:{pct(lo):.2f}%;'
        f'width:{pct(hi) - pct(lo):.2f}%"></span>',
        f'<span class="ivl-est" style="left:{pct(est):.2f}%"></span>',
    ]
    if zero and scale_lo < 0 < scale_hi:
        parts.insert(0, f'<span class="ivl-zero" style="left:{pct(0):.2f}%"></span>')
    if pred is not None:
        parts.append(f'<span class="ivl-pred" style="left:{pct(pred):.2f}%"></span>')
    return f'<span class="ivl">{"".join(parts)}</span>'


def num(v, plus=True):
    return f"{v:+.0f}" if plus else f"{v:.0f}"


# ---------------------------------------------------------------- content
# (pairing, fixed games, sequential figure, measured, lo, hi)
LADDER = [
    ("L2 vs L1", 600, 361, 420, 375, 479),
    ("L3 vs L2", 600, 800, 684, 603, 833),
    ("L4 vs L3", 240, 361, 390, 326, 482),
    ("L5 vs L4", 240, 132, 149, 103, 200),
    ("L6 vs L5", 240, 361, 527, 443, 682),
    ("L7 vs L6", 240, 93, 22, -22, 66),
    ("L8 vs L7", 240, -85, -25, -69, 19),
]

# (gap, measured, lo, hi) — the joint fit over all 5,375 games at 0.1s
GAPS = [
    ("L1 → L2", 444, 229, 660),
    ("L2 → L3", 703, 505, 902),
    ("L3 → L4", 427, 251, 604),
    ("L4 → L5", 193, 33, 352),
    ("L5 → L6", 660, 546, 773),
    ("L6 → L7", 19, -17, 55),
    ("L7 → L8", -35, -79, 9),
]

# (variant, what it is, games, elo, lo, hi, nps)
EVAL = [
    ("v2", "temel", None, None, None, None, 64794),
    ("v3-rooks", "+ kale hattı — <strong>ship edilen</strong>", 600, -2, -26, 22, 60337),
    ("v3-passers", "+ geçer piyon", 714, 11, -12, 34, None),
    ("shelter-only", "+ kral güvenliği", 558, -53, -84, -24, 58138),
    ("passers-rooks", "+ geçer piyon ve kale hattı", 1200, 12, -8, 31, 53556),
    ("v3-shelter", "+ üçü birden", 600, 21, -5, 47, 49064),
]

# (true difference, games to stop, reported, bias, bias over its own sd)
BIAS = [
    (22, 96, 88, 66, 1.54),
    (149, 41, 139, -10, 0.18),
    (390, 14, 368, -22, 0.17),
    (527, 12, 507, -20, 0.12),
]

ANCHOR = [
    ("Stockfish depth 1", 162, "%47,5", -17, -48, 13, "hüküm yok"),
    ("Stockfish depth 2", 162, "%58,6", 61, 23, 100, "kabul"),
    ("Stockfish depth 3", 162, "%60,2", 72, 41, 104, "kabul"),
]

CALIB = [
    ("L4", 120, "%74,6", "60-59-1", 1387, 1321, 1468),
    ("L5", 120, "%61,3", "45-57-18", 1580, 1518, 1647),
    ("L6", 120, "%11,2", "5-17-98", 1441, 1309, 1523),
    ("L7", 120, "%11,7", "1-26-93", 1748, 1620, 1830),
]

SPEED = [
    ("B/2", 240, -159, -212, -113, -60),
    ("B/4", 240, -417, -518, -349, -120),
    ("B/8", 240, -636, -911, -532, -180),
    ("B/16", 240, -830, -2400, -678, -240),
]

ENFORCE = [
    (
        "sert node limiti",
        "4 nokta",
        -207,
        -251,
        -164,
        "Kestiği iterasyonu çöpe atar. Deney aleti; hiçbir motor böyle durmaz.",
    ),
    (
        "saat",
        "4 nokta",
        -171,
        -194,
        -149,
        "Gerçek oyunun durma biçimi. Dönüşüm için kullanılan sayı.",
    ),
    (
        "yumuşak node limiti",
        "1 nokta",
        -98,
        -126,
        -69,
        "Yalnızca iterasyon sınırında durur; saat yok.",
    ),
]

PREREG = [
    (
        "Hız eğrisi: dört yarılanma",
        "−60 / −120 / −180 / −240",
        "−159 / −417 / −636 / −830",
        "fail",
        "Dördü de aynı yönde, 2,5 kat ıskalandı. Tahminler uzun zaman kontrollerinde "
        "ölçülmüş literatürden geliyordu. Ön-kayıtlı <em>doğrusallık</em> iddiası ayakta.",
    ),
    (
        "Movetime çapraz kontrolü",
        "B/2'de örtüşür, B/8'de ayrışır",
        "öyle oldu",
        "pass",
        "Kaynak koddan türetilmişti: <code>check_interval</code> 2048, yani B/8 bütçesi "
        "onu uygulayan aletin çözünürlüğünün altında.",
    ),
    (
        "Üçüncü kol: saat mi, sınırda durma mı?",
        "−349 ya da −257",
        "−165",
        "fail",
        "İkisinin de dışında. Çürütme şartı işledi ve incelenecek şeyin eğrinin kendisi "
        "olduğunu söyledi — öyle çıktı.",
    ),
    (
        "B/1,5: ofset modeli",
        "−58 (çizgi) ya da −174 (ofset)",
        "−83",
        "pass",
        "Çizgi desteklendi, ofset reddedildi.",
    ),
    (
        "B/2 tekrarı",
        "−98 (fluke) ya da −201 (tekrarlanır)",
        "−116",
        "pass",
        "Aynı eşleşmenin iki koşusu p = 0,015 ile ayrıştı. Asıl bulgu buydu.",
    ),
    (
        "x'i yeniden örneklemek aralığı genişletir",
        "genişler",
        "46 → 47 Elo",
        "fail",
        "Genişlemedi. Yazılı olduğu için raporlandı.",
    ),
    (
        "Sabit uzunlukta merdiven",
        "hepsi sekans sayısının altında",
        "altısının dördü <em>üstünde</em>",
        "fail",
        "Yanlılık gerçek fark ~100'ün üstünde tersine dönüyor — kendi simülasyonum bunu "
        "raporlamıştı, tahmini yazarken tablomu taşımamışım.",
    ),
    (
        "SEE budaması",
        "+79, sonra +66'ya düzeltildi",
        "+48 [+11, +87]",
        "null",
        "Aralık hem +79'u hem +20'yi kapsayınca <em>büyüklük sorusunda null</em> ilan "
        "edilecekti. Öyle raporlandı.",
    ),
    (
        "Ship edilen kale terimi yeniden ölçülür",
        "+50, sıfırı dışlayan aralık",
        "−2 [−26, +22]",
        "fail",
        "«Sıfırın altı» çürütme ölçütüydü. Aralık ship edilmesini gerekçelendiren +44'ü "
        "dışlıyor.",
    ),
    (
        "Reddedilen demet yeniden ölçülür",
        "−15 ile +25 arası",
        "+21 [−5, +47]",
        "pass",
        "Reddi hiçbir aşamada kanıt desteklemiyormuş. (Varyantın adı beni yanılttı: üç "
        "terimlik demetmiş, tek terim değil — ayrı bir düzeltme.)",
    ),
    (
        "Kral güvenliği tek başına",
        "+12 (parçaların toplamından)",
        "−53 [−84, −24]",
        "fail",
        "Çürütme aralığının ([−40, +65]) dışında. Projede temelden belirgin kötü ölçülen "
        "ilk varyant.",
    ),
    (
        "Terimler toplanıyor mu?",
        "+9 (toplanır) ya da +75 (etkileşir)",
        "+26",
        "pass",
        "+9 içeride, +75 dışarıda. Etkileşim açıklaması reddedildi.",
    ),
    (
        "Doğrulama: +26 kalır",
        "aralık [+6, +46]'ya daralır",
        "+12 [−8, +31]",
        "fail",
        "Aralık sıfırı kapsadı. Ön-kayıt bu duruma «gürültünün ince ucu» diyecekti; "
        "dedi. Üçüncü uzatma yok.",
    ),
]

CORRECTIONS = [
    (
        "«Level 8 bir gerileme»",
        "−85'lik nokta tahmininden söylenmişti; %95 aralığı [−238, +40] <em>sıfırı "
        "içeriyordu.</em> Asıl hata parantezteydi.",
    ),
    (
        "«Terimler PST'yi tekrarlıyor, o yüzden işe yaramıyor»",
        "−3 Elo'luk bir okumadan çıkarılmıştı; yüz oyun sonra +21'e taşındı. Yapısal "
        "gözlem doğru, ondan çıkarılan sonuç desteklenmiyordu.",
    ),
    (
        "«İki aday mekanizma var, bu tasarım ayırmıyor»",
        "İkisi bağımsız değilmiş: sınırda uygulanan bir bütçe <em>zorunlu olarak</em> "
        "değişken node harcar. Veriden değil, aleti kurmaya çalışmaktan çıktı.",
    ),
    (
        "«Merdivenin Elo sütunu farkların tahmini»",
        "Erken duran bir sekans testi gerçek fark ne olursa olsun ~110 raporluyor. "
        "Hükümler ayakta, büyüklükler hiç ölçülmemişti — sonradan sabit uzunlukta ölçüldü.",
    ),
    (
        "«B/2 3,6σ aykırı bir nokta»",
        "Kusur noktada değil hata çubuklarındaydı. Saat kolunun harcaması koşudan koşuya "
        "%5,3 kayıyor; kayma bir belge önce ölçülmüş ama yanlış büyüklüğe uygulanmıştı.",
    ),
    (
        "«Kral güvenliği buradaki en değerli pozisyonel terim»",
        "Varyantın adına güvenip ne inşa ettiğini okumamışım. <code>v3-shelter</code> üç "
        "terimlik bir demet. Tek başına ölçülünce −53 [−84, −24] çıktı — tam tersi.",
    ),
    (
        "«Kale terimi +44 Elo ediyor»",
        "Sekans testinin durma noktasındaki sayıydı. 600 sabit oyun −2 [−26, +22] diyor; "
        "aralık +44'ü dışlıyor. Motorda hâlâ o terim var.",
    ),
    (
        "«passers-rooks +26, ilk pozitif sonuç»",
        "600 oyunda öyleydi, alt sınır +1. Önceden ilan edilen doğrulama 1.200 oyunda "
        "+12 [−8, +31] döndürdü. Gürültünün ince ucu.",
    ),
]

NOT_MEASURED = [
    (
        "Mutlak Elo",
        "Sabit derinlikli Stockfish hiçbir yayınlanmış listede yok. "
        "Eşleme koşullu yazıldı: R(d) varsayılan reyting olmak üzere Level 7 = "
        "R(1) + 17 ± 30. Bu belirsizlik istatistiksel değil — oyun sayısıyla küçülmez.",
    ),
    (
        "Merdivenin aralıkları",
        "Sıralama doğrulandı, aralıklar değil. Nominal 300, "
        "üç aralığın da güven aralığının dışında. Sayılar <code>INITIAL_ELO</code>'da "
        "kuruluşta <em>hedef</em> olarak atanmış.",
    ),
    (
        "SEE'nin büyüklüğü",
        "İki koşuda da pozitif olduğu kesin (aralıklar sıfırı "
        "dışlıyor). Ne kadar olduğu değil: [+11, +87], sekiz kat.",
    ),
    ("v3-passers ve L8'in saati", "714 ve 54 oyunda çözülmedi. " "«Çözülmedi» ≠ «reddedildi»."),
]

# ---------------------------------------------------------------- markup
KEY_ROW = ' class="row-key"'
OUT_CLASS = "out"
OUT_LABEL = "300 dışarıda"
BIAS_NOTE = {
    True: "yanlılık baskın — sayı güvenilir biçimde yanlış",
    False: "gürültü baskın — sayı, sistematik değil ama çok belirsiz",
}

ladder_rows = "\n".join(
    f"<tr{KEY_ROW if n == 'L7 vs L6' else ''}>"
    f'<td class="mono">{n}</td><td class="mono num">{g}</td>'
    f'<td class="mono num pred">{num(sq)}</td>'
    f'<td class="mono num strong">{num(e)}</td>'
    f'<td class="ivl-cell">{bar(lo, e, hi, -120, 900, pred=sq)}</td>'
    f'<td class="mono small">[{num(lo)}, {num(hi)}]</td></tr>'
    for n, g, sq, e, lo, hi in LADDER
)

gap_rows = "\n".join(
    f"<tr{KEY_ROW if 'L6 → L7' in n else ''}>"
    f'<td class="mono">{n}</td><td class="mono num strong">{num(e)}</td>'
    f'<td class="ivl-cell">{bar(lo, e, hi, -120, 950, pred=300)}</td>'
    f'<td class="mono small">[{num(lo)}, {num(hi)}]</td>'
    f'<td class="mono num small {OUT_CLASS if not (lo <= 300 <= hi) else "pred"}">'
    f'{OUT_LABEL if not (lo <= 300 <= hi) else "300 içeride"}</td></tr>'
    for n, e, lo, hi in GAPS
)

eval_rows = "\n".join(
    f"<tr{KEY_ROW if n == 'shelter-only' else ''}>"
    f'<td class="mono">{n}</td><td>{what}</td>'
    f'<td class="mono num">{g if g else "—"}</td>'
    f'<td class="mono num strong">{num(e) if e is not None else "—"}</td>'
    f'<td class="ivl-cell">{bar(lo, e, hi, -100, 60) if e is not None else ""}</td>'
    f'<td class="mono small">{f"[{num(lo)}, {num(hi)}]" if e is not None else "—"}</td>'
    f'<td class="mono num pred">{f"{nps:,}" if nps else "—"}</td></tr>'
    for n, what, g, e, lo, hi, nps in EVAL
)

bias_rows = "\n".join(
    f'<tr><td class="mono num">{t}</td><td class="mono num">{g}</td>'
    f'<td class="mono num">{num(r)}</td><td class="mono num strong">{num(b)}</td>'
    f'<td class="mono num">{ratio:.2f}</td>'
    f'<td class="note">{BIAS_NOTE[ratio > 1]}</td></tr>'
    for t, g, r, b, ratio in BIAS
)

anchor_rows = "\n".join(
    f'<tr><td>{n}</td><td class="mono num">{g}</td><td class="mono num">{s}</td>'
    f'<td class="ivl-cell">{bar(lo, e, hi, -70, 130)}</td>'
    f'<td class="mono small">[{num(lo)}, {num(hi)}]</td>'
    f'<td class="verdict {"v-null" if v == "hüküm yok" else "v-yes"}">{v}</td></tr>'
    for n, g, s, e, lo, hi, v in ANCHOR
)

calib_rows = "\n".join(
    f'<tr><td class="mono">{n}</td><td class="mono num">{g}</td>'
    f'<td class="mono num">{s}</td><td class="mono num small">{w}</td>'
    f'<td class="mono num">{num(e, False)}</td>'
    f'<td class="ivl-cell">{bar(lo, e, hi, 1250, 1900, zero=False)}</td>'
    f'<td class="mono small">[{num(lo, False)}, {num(hi, False)}]</td></tr>'
    for n, g, s, w, e, lo, hi in CALIB
)

speed_rows = "\n".join(
    f'<tr><td class="mono">{n}</td><td class="mono num">{g}</td>'
    f'<td class="mono num">{num(e)}</td>'
    f'<td class="ivl-cell">{bar(max(lo, -1000), e, hi, -1000, 60, pred=p)}</td>'
    f'<td class="mono num small pred">{num(p)}</td></tr>'
    for n, g, e, lo, hi, p in SPEED
)

enforce_rows = "\n".join(
    f'<tr class="{"row-key" if k == "saat" else ""}">'
    f'<td>{k}<span class="sub">{pts}</span></td>'
    f'<td class="mono num">{num(e)}</td>'
    f'<td class="ivl-cell">{bar(lo, e, hi, -280, 0, zero=False)}</td>'
    f'<td class="mono small">[{num(lo)}, {num(hi)}]</td>'
    f'<td class="note">{note}</td></tr>'
    for k, pts, e, lo, hi, note in ENFORCE
)

BADGE = {"pass": ("tuttu", "b-pass"), "fail": ("tutmadı", "b-fail"), "null": ("null", "b-null")}
prereg_rows = "\n".join(
    f'<article class="pr"><header><h3>{t}</h3>'
    f'<span class="badge {BADGE[k][1]}">{BADGE[k][0]}</span></header>'
    f'<dl><div><dt>tahmin</dt><dd class="mono">{p}</dd></div>'
    f'<div><dt>ölçülen</dt><dd class="mono strong">{m}</dd></div></dl>'
    f"<p>{note}</p></article>"
    for t, p, m, k, note in PREREG
)

corr_items = "\n".join(f"<li><h3>{t}</h3><p>{b}</p></li>" for t, b in CORRECTIONS)

nm_items = "\n".join(f'<div class="nm"><h3>{t}</h3><p>{b}</p></div>' for t, b in NOT_MEASURED)

HTML = f"""<title>Atropos Ölçüm Kaydı</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>
:root {{
  --ground: #F2F3F7;
  --panel: #FBFBFD;
  --rule: #D6D9E4;
  --rule-soft: #E4E7F0;
  --ink: #171A26;
  --ink-soft: #4A5068;
  --ink-faint: #767D96;
  --accent: #2C3A6B;
  --accent-soft: #6D7CB8;
  --grid: rgba(44, 58, 107, 0.055);
  --yes: #2F6B4F;
  --no: #9C3B2E;
  --null: #7A6320;
  --yes-bg: rgba(47, 107, 79, 0.10);
  --no-bg: rgba(156, 59, 46, 0.10);
  --null-bg: rgba(122, 99, 32, 0.12);
  --range: rgba(44, 58, 107, 0.22);
  --shadow: 0 1px 2px rgba(23, 26, 38, .05), 0 8px 24px -16px rgba(23, 26, 38, .28);
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --ground: #0F111A;
    --panel: #161926;
    --rule: #2B3044;
    --rule-soft: #232838;
    --ink: #E8EAF2;
    --ink-soft: #A8AEC4;
    --ink-faint: #767D96;
    --accent: #A9B6EA;
    --accent-soft: #6D7CB8;
    --grid: rgba(169, 182, 234, 0.06);
    --yes: #7FC9A2;
    --no: #E4907F;
    --null: #D6BC6A;
    --yes-bg: rgba(127, 201, 162, 0.13);
    --no-bg: rgba(228, 144, 127, 0.13);
    --null-bg: rgba(214, 188, 106, 0.13);
    --range: rgba(169, 182, 234, 0.26);
    --shadow: 0 1px 2px rgba(0, 0, 0, .4), 0 8px 24px -16px rgba(0, 0, 0, .7);
  }}
}}
:root[data-theme="dark"] {{
  --ground: #0F111A;
  --panel: #161926;
  --rule: #2B3044;
  --rule-soft: #232838;
  --ink: #E8EAF2;
  --ink-soft: #A8AEC4;
  --ink-faint: #767D96;
  --accent: #A9B6EA;
  --accent-soft: #6D7CB8;
  --grid: rgba(169, 182, 234, 0.06);
  --yes: #7FC9A2;
  --no: #E4907F;
  --null: #D6BC6A;
  --yes-bg: rgba(127, 201, 162, 0.13);
  --no-bg: rgba(228, 144, 127, 0.13);
  --null-bg: rgba(214, 188, 106, 0.13);
  --range: rgba(169, 182, 234, 0.26);
  --shadow: 0 1px 2px rgba(0, 0, 0, .4), 0 8px 24px -16px rgba(0, 0, 0, .7);
}}

* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background-color: var(--ground);
  background-image:
    linear-gradient(var(--grid) 1px, transparent 1px),
    linear-gradient(90deg, var(--grid) 1px, transparent 1px);
  background-size: 28px 28px;
  color: var(--ink);
  font-family: "IBM Plex Sans", system-ui, -apple-system, sans-serif;
  font-size: 16px;
  line-height: 1.65;
  -webkit-font-smoothing: antialiased;
}}
.wrap {{ max-width: 68rem; margin: 0 auto; padding: 0 1.5rem 6rem; }}
.mono {{ font-family: "IBM Plex Mono", ui-monospace, SFMono-Regular, monospace; }}
.num {{ font-variant-numeric: tabular-nums; text-align: right; }}
.small {{ font-size: .8125rem; }}
.strong {{ font-weight: 600; }}
code {{
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: .875em; background: var(--rule-soft);
  padding: .1em .35em; border-radius: 3px;
}}

/* ---- hero ---- */
header.hero {{ padding: 5.5rem 0 3rem; border-bottom: 1px solid var(--rule); }}
.eyebrow {{
  font-family: "IBM Plex Mono", monospace; font-size: .75rem;
  letter-spacing: .14em; text-transform: uppercase; color: var(--accent-soft);
  margin: 0 0 1.5rem;
}}
h1 {{
  font-family: "Instrument Serif", Georgia, serif; font-weight: 400;
  font-size: clamp(2.9rem, 7vw, 5rem); line-height: 1.02;
  letter-spacing: -.015em; margin: 0 0 1.5rem; text-wrap: balance;
}}
h1 em {{ font-style: italic; color: var(--accent); }}
.lede {{
  font-size: clamp(1.075rem, 1.8vw, 1.3rem); color: var(--ink-soft);
  max-width: 40ch; margin: 0 0 3rem;
}}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(9rem, 1fr)); gap: 1.75rem; }}
.stat .v {{
  font-family: "Instrument Serif", Georgia, serif; font-size: 2.4rem;
  line-height: 1; color: var(--accent); font-variant-numeric: tabular-nums;
}}
.stat .k {{
  font-family: "IBM Plex Mono", monospace; font-size: .7rem;
  letter-spacing: .1em; text-transform: uppercase; color: var(--ink-faint);
  margin-top: .55rem;
}}

/* ---- sections ---- */
section {{ padding-top: 4.5rem; }}
h2 {{
  font-family: "Instrument Serif", Georgia, serif; font-weight: 400;
  font-size: clamp(1.9rem, 3.6vw, 2.7rem); line-height: 1.12;
  letter-spacing: -.01em; margin: 0 0 .5rem; text-wrap: balance;
}}
.sub-h {{
  font-family: "Instrument Serif", Georgia, serif; font-weight: 400;
  font-size: 1.5rem; margin: 3rem 0 .35rem; line-height: 1.2;
}}
.sec-sub {{
  font-family: "IBM Plex Mono", monospace; font-size: .72rem;
  letter-spacing: .12em; text-transform: uppercase; color: var(--accent-soft);
  margin: 0 0 1.5rem;
}}
p {{ max-width: 68ch; }}
section > p {{ color: var(--ink-soft); }}
section > p strong, .panel p strong {{ color: var(--ink); font-weight: 600; }}

.panel {{
  background: var(--panel); border: 1px solid var(--rule);
  border-radius: 10px; padding: 1.5rem; margin: 2rem 0;
  box-shadow: var(--shadow);
}}
.panel > :first-child {{ margin-top: 0; }}
.panel > :last-child {{ margin-bottom: 0; }}
.panel.flag {{ border-left: 3px solid var(--accent); }}

.scroll {{ overflow-x: auto; margin: 1.75rem 0; }}
table {{ width: 100%; border-collapse: collapse; font-size: .9rem; min-width: 34rem; }}
th {{
  font-family: "IBM Plex Mono", monospace; font-size: .68rem;
  letter-spacing: .1em; text-transform: uppercase; color: var(--ink-faint);
  font-weight: 500; text-align: left; padding: 0 .85rem .6rem 0;
  border-bottom: 1px solid var(--rule); white-space: nowrap;
}}
th.num {{ text-align: right; }}
td {{ padding: .6rem .85rem .6rem 0; border-bottom: 1px solid var(--rule-soft); vertical-align: middle; }}
tr:last-child td {{ border-bottom: none; }}
tr.row-key td {{ background: var(--rule-soft); font-weight: 500; }}
td .sub {{ display: block; font-family: "IBM Plex Mono", monospace;
  font-size: .7rem; color: var(--ink-faint); }}
td.note {{ font-size: .8125rem; color: var(--ink-soft); min-width: 15rem; }}
td.pred {{ color: var(--ink-faint); }}
td.out {{ color: var(--no); font-weight: 500; }}

/* ---- interval bars ---- */
.ivl-cell {{ width: 40%; min-width: 9rem; padding-right: .85rem; }}
.ivl {{ position: relative; display: block; height: 1.5rem; }}
.ivl::before {{
  content: ""; position: absolute; left: 0; right: 0; top: 50%;
  height: 1px; background: var(--rule); transform: translateY(-50%);
}}
.ivl-range {{
  position: absolute; top: 50%; height: 7px; background: var(--range);
  border-radius: 4px; transform: translateY(-50%); min-width: 2px;
}}
.ivl-est {{
  position: absolute; top: 50%; width: 3px; height: 15px;
  background: var(--accent); border-radius: 2px;
  transform: translate(-50%, -50%);
}}
.ivl-zero {{
  position: absolute; top: 50%; width: 1px; height: 20px;
  background: var(--ink-faint); opacity: .55;
  transform: translate(-50%, -50%);
}}
.ivl-pred {{
  position: absolute; top: 50%; width: 0; height: 17px;
  border-left: 2px dashed var(--no);
  transform: translate(-50%, -50%);
}}
.legend {{
  display: flex; flex-wrap: wrap; gap: 1.25rem; margin: 1rem 0 0;
  font-family: "IBM Plex Mono", monospace; font-size: .72rem; color: var(--ink-faint);
}}
.legend span {{ display: inline-flex; align-items: center; gap: .45rem; }}
.key {{ display: inline-block; width: 16px; height: 7px; border-radius: 4px; }}
.key.range {{ background: var(--range); }}
.key.est {{ width: 3px; height: 14px; background: var(--accent); border-radius: 2px; }}
.key.pred {{ width: 0; height: 14px; border-left: 2px dashed var(--no); }}

/* ---- pre-registration cards ---- */
.pr-grid {{ display: grid; gap: 1rem; margin: 2rem 0; }}
@media (min-width: 52rem) {{ .pr-grid {{ grid-template-columns: 1fr 1fr; }} }}
.pr {{
  background: var(--panel); border: 1px solid var(--rule);
  border-radius: 10px; padding: 1.25rem; box-shadow: var(--shadow);
}}
.pr header {{ display: flex; gap: .75rem; align-items: flex-start;
  justify-content: space-between; margin-bottom: .9rem; }}
.pr h3 {{ font-size: .975rem; font-weight: 600; margin: 0; line-height: 1.35; }}
.badge {{
  font-family: "IBM Plex Mono", monospace; font-size: .66rem;
  letter-spacing: .09em; text-transform: uppercase; padding: .2rem .5rem;
  border-radius: 999px; white-space: nowrap; font-weight: 500;
}}
.b-pass {{ background: var(--yes-bg); color: var(--yes); }}
.b-fail {{ background: var(--no-bg); color: var(--no); }}
.b-null {{ background: var(--null-bg); color: var(--null); }}
.pr dl {{ margin: 0 0 .9rem; display: grid; gap: .35rem; }}
.pr dl div {{ display: grid; grid-template-columns: 5.5rem 1fr; gap: .5rem; align-items: baseline; }}
.pr dt {{
  font-family: "IBM Plex Mono", monospace; font-size: .68rem;
  letter-spacing: .09em; text-transform: uppercase; color: var(--ink-faint);
}}
.pr dd {{ margin: 0; font-size: .875rem; }}
.pr p {{ margin: 0; font-size: .8375rem; color: var(--ink-soft); }}

/* ---- corrections ---- */
ol.corr {{ list-style: none; counter-reset: c; padding: 0; margin: 2rem 0 0; }}
ol.corr li {{
  counter-increment: c; position: relative;
  padding: 1.25rem 0 1.25rem 3.25rem; border-top: 1px solid var(--rule-soft);
}}
ol.corr li::before {{
  content: counter(c, decimal-leading-zero); position: absolute; left: 0; top: 1.3rem;
  font-family: "IBM Plex Mono", monospace; font-size: .75rem;
  color: var(--no); font-weight: 500;
}}
ol.corr h3 {{ margin: 0 0 .4rem; font-size: 1rem; font-weight: 600; }}
ol.corr p {{ margin: 0; color: var(--ink-soft); font-size: .9rem; }}

/* ---- not measured ---- */
.nm-grid {{ display: grid; gap: 1rem; margin-top: 2rem; }}
@media (min-width: 52rem) {{ .nm-grid {{ grid-template-columns: 1fr 1fr; }} }}
.nm {{ border-top: 2px solid var(--rule); padding-top: .9rem; }}
.nm h3 {{ margin: 0 0 .4rem; font-size: .95rem; font-weight: 600; }}
.nm p {{ margin: 0; font-size: .8625rem; color: var(--ink-soft); }}

blockquote {{
  margin: 2rem 0; padding-left: 1.25rem; border-left: 2px solid var(--accent);
  font-family: "Instrument Serif", Georgia, serif; font-style: italic;
  font-size: 1.3rem; line-height: 1.4; color: var(--ink); max-width: 42ch;
}}
footer {{
  margin-top: 5rem; padding-top: 2rem; border-top: 1px solid var(--rule);
  font-size: .8125rem; color: var(--ink-faint);
}}
footer p {{ max-width: 60ch; }}
hr.rule {{ border: 0; border-top: 1px solid var(--rule); margin: 4rem 0 0; }}
</style>

<div class="wrap">

<header class="hero">
  <p class="eyebrow">Atropos · satranç motoru · ölçüm kaydı</p>
  <h1>Ölçülen ne,<br><em>varsayılan</em> ne</h1>
  <p class="lede">Sekiz seviyeli bir satranç motoru. Asıl ürün motor değil:
    her sayının nereden geldiğinin, hangi tahminin tutmadığının ve neyin hâlâ
    bilinmediğinin kaydı.</p>
  <div class="stats">
    <div class="stat"><div class="v">10.864</div><div class="k">telemetrili oyun</div></div>
    <div class="stat"><div class="v">14</div><div class="k">ön-kayıtlı tahmin</div></div>
    <div class="stat"><div class="v">6</div><div class="k">tutmadı</div></div>
    <div class="stat"><div class="v">8</div><div class="k">geri alınan iddia</div></div>
    <div class="stat"><div class="v">732</div><div class="k">test</div></div>
  </div>
</header>

<section>
  <h2>Bir merdivenin sıralaması ucuz, ölçeği değil</h2>
  <p class="sec-sub">Her eşleşme sabit uzunlukta · 1.960 oyun · 0,1 sn/hamle</p>
  <p>Merdivenin yedi eşleşmesi sekans testiyle doğrulanmıştı ve her sonuç yanında bir Elo
    sayısıyla alıntılanıyordu. <strong>Hükümler ayaktaydı; sayılar değildi.</strong></p>
  <div class="scroll">
    <table>
      <thead><tr><th>eşleşme</th><th class="num">oyun</th><th class="num">sekans dedi</th>
        <th class="num">ölçülen</th><th>aralık ve sekans sayısı</th><th></th></tr></thead>
      <tbody>{ladder_rows}</tbody>
    </table>
  </div>
  <div class="legend">
    <span><i class="key range"></i>%95 aralık</span>
    <span><i class="key est"></i>sabit uzunlukta ölçülen</span>
    <span><i class="key pred"></i>sekans testinin raporladığı</span>
  </div>

  <div class="panel flag">
    <p><strong>Level 7, 0,1 sn/hamlede Level 6'dan ayırt edilemiyor.</strong>
      Sekans testi +93 deyip «en az 100 Elo daha iyi» hükmü vermişti; sabit uzunlukta
      240 oyun <strong>+22 [−22, +66]</strong> diyor — aralık sıfırı kapsıyor.</p>
    <p>Aynı cevaba <em>dört bağımsız yol</em>: ortak uyum +50 [−3, +103], iki basamağa da
      oynayan dış motor 4 Elo arayla, yanlılık simülasyonu +66'lık kayma öngörüyor
      (gözlenen +71), ve bu ölçüm. Level 8 ise düzeltmenin bıraktığı yerde:
      −25 [−69, +19], aralık hâlâ sıfırı kapsıyor — artık 25 değil 240 oyunla.</p>
  </div>

  <h3 class="sub-h">Neden sayılar atıldı</h3>
  <p>Sekans testi kanıt bir sınırı geçtiği <em>anda</em> durur, ve geçiş uygun bir seri
    üzerine olur. Durma noktasındaki tahmin, aynı oyunların tamamı oynansa çıkacak
    tahmin değildir. Bu ders kitabı bilgisi; ölçülmemiş olan <strong>büyüklüğü</strong>.
    Projenin kendi <code>Sprt</code> sınıfını gerçeği bilinen maçlara karşı koşturdum —
    nokta başına 3.000 maç, hiç satranç oynamadan:</p>
  <div class="scroll">
    <table>
      <thead><tr><th class="num">gerçek fark</th><th class="num">duruş oyunu</th>
        <th class="num">raporlanan</th><th class="num">yanlılık</th>
        <th class="num">÷ saçılma</th><th></th></tr></thead>
      <tbody>{bias_rows}</tbody>
    </table>
  </div>
  <p>Erken durmaya koşullandığında raporlanan sayı <strong>gerçek fark 0 da olsa 100 de
    olsa ~110</strong>. Yüz Elo'luk bir gerçek aralık boyunca tahmin beş Elo oynuyor.</p>
  <blockquote>Hüküm kanıttır. Yanındaki sayı değildir.</blockquote>

  <h3 class="sub-h">Ölçülmüş merdiven</h3>
  <p>0,1 sn'deki 5.375 oyunun tamamı birlikte uydurulunca sekiz basamağın hepsi ilk kez
    yerleşti. Nominal her aralık için 300:</p>
  <div class="scroll">
    <table>
      <thead><tr><th>aralık</th><th class="num">ölçülen</th>
        <th>%95 aralık ve nominal 300</th><th></th><th></th></tr></thead>
      <tbody>{gap_rows}</tbody>
    </table>
  </div>
  <p><strong>Yedi aralığın dördünde 300 güven aralığının dışında.</strong> Gerçek
    merdiven altta dik çıkıyor, Level 4'te düzleşiyor, quiescence ve transposition
    table'ın geldiği yerde tekrar sıçrıyor — ve sonra duruyor. Sayılar
    <code>INITIAL_ELO</code>'da kuruluşta <em>hedef</em> olarak atanmıştı; hiçbir ölçüm
    onları doğrulamadı.</p>
</section>

<section>
  <h2>Dış çıpa</h2>
  <p class="sec-sub">Stockfish 18, sabit derinlik · Level 7'ye karşı · 162 oyun</p>
  <p>Sabit <strong>derinlik</strong>, <code>SkillLevel</code> değil: skill ayarları
    motoru bilerek hata yaptırır ve ölçülen güçle ilgisi olmayan varyans ekler.</p>
  <div class="scroll">
    <table>
      <thead><tr><th>rakip</th><th class="num">oyun</th><th class="num">skor</th>
        <th>L7'ye karşı Elo</th><th></th><th>SPRT</th></tr></thead>
      <tbody>{anchor_rows}</tbody>
    </table>
  </div>
  <p>Üçü de 90 Elo'luk bir bantta toplanıyor, çünkü Stockfish'in «depth 1»i zaten
    quiescence ve NNUE taşıyor.</p>
  <blockquote>Bir motorun derinlik sayısı, başka bir motorun aynı sayısıyla aynı işi
    adlandırmıyor.</blockquote>
</section>

<section>
  <h2>Tek sayı yetmediğinde</h2>
  <p class="sec-sub">atropos, güncel merdivene karşı · 480 oyun</p>
  <p>Performance rating <strong>1518</strong>. Önceki iki koşunun 1514 ve 1538'i
    yanında bu istikrar gibi görünüyor — ve öyle okumak hata olurdu.</p>
  <div class="scroll">
    <table>
      <thead><tr><th>rakip</th><th class="num">oyun</th><th class="num">skor</th>
        <th class="num">W-D-L</th><th class="num">implied</th>
        <th>%95 aralık</th><th></th></tr></thead>
      <tbody>{calib_rows}</tbody>
    </table>
  </div>
  <p>Implied reytingler <strong>361 Elo'ya yayılıyor ve aralıkları örtüşmüyor.</strong>
    Eski metin bu saçılmayı örnekleme gürültüsüne bağlıyordu; on katı oyun aksini
    söyledi. Saçılma gürültü değil, yapı — ve anlamı şu: atropos'u bu merdivene karşı
    tek bir sayı tarif etmiyor.</p>
</section>

<section>
  <h2>Bir katlama kaç Elo?</h2>
  <p class="sec-sub">Level 7, yavaşlatılmış kopyasına karşı · eşleşme başına 240 oyun</p>
  <p>Bu projedeki her optimizasyon node/sn cinsinden raporlandı — kimsenin umursadığı
    bir birim değil. Parantezler, tahminler ve çürütülebilir iddia <strong>ilk oyundan
    önce commit'lendi.</strong></p>
  <div class="scroll">
    <table>
      <thead><tr><th>bütçe</th><th class="num">oyun</th><th class="num">ölçülen</th>
        <th>aralık ve tahmin</th><th class="num">tahmin</th></tr></thead>
      <tbody>{speed_rows}</tbody>
    </table>
  </div>
  <div class="legend">
    <span><i class="key range"></i>%95 aralık</span>
    <span><i class="key est"></i>ölçülen</span>
    <span><i class="key pred"></i>ön-kayıtlı tahmin</span>
  </div>
  <p>Dört tahminin dördü de <strong>aynı yönde ve iki buçuk kat</strong> ıskalandı.
    Tahminler klasik motorlar için yayınlanmış eğrilerden geliyordu — ama onlar uzun
    zaman kontrollerinde, zaten on beş plilik bir aramaya bir pli eklendiğinde ölçülür.
    Burada referans bütçe derinlik 3,0'a ulaşıyor: bir katlama, üç hamlelik taktiği
    görmekle görmemek arasındaki fark.</p>
  <blockquote>Katlama başına Elo motorun sabiti değil; eğrinin hangi bölgesinde
    ölçtüğünün özelliği.</blockquote>

  <h3 class="sub-h">Ve eğri, aletin kendisini ölçüyormuş</h3>
  <p>Bütçenin <em>nasıl uygulandığı</em> birinci derecede bir değişken çıktı. Sert node
    limiti kestiği iterasyonu çöpe atıyor: aynı derinliğe ulaşmak için %46 fazla node
    harcıyor.</p>
  <div class="scroll">
    <table>
      <thead><tr><th>uygulama</th><th class="num">Elo/katlama</th><th></th>
        <th>%95 aralık</th><th></th></tr></thead>
      <tbody>{enforce_rows}</tbody>
    </table>
  </div>
  <div class="panel">
    <p><strong>Dönüşümün sınandığı yer.</strong> atropos bu motordan 2,6 katlama yavaş.
      Saat kolu bundan <strong>−445 Elo</strong> [−504, −386] öngörüyor; 480 oyunluk
      bağımsız gauntlet <strong>≈ −440</strong> ölçtü. Tamamen başka oyunlardan kurulmuş
      iki sayı. Özellik paritesi throughput'a yeniliyor, ve büyüklüğü artık iddia değil
      öngörü.</p>
  </div>
</section>

<section>
  <h2>3.672 oyun, ve hiçbir şey iyileştirmedi</h2>
  <p class="sec-sub">Değerlendirme programı · beş varyant · hepsi sabit uzunlukta</p>
  <p>Değerlendirmeye terim eklemek klasik yol. Bu proje beş varyantı ölçtü ve programı
    kapattı.</p>
  <div class="scroll">
    <table>
      <thead><tr><th>varyant</th><th>ne olduğu</th><th class="num">oyun</th>
        <th class="num">Elo</th><th>%95 aralık</th><th></th><th class="num">nps</th></tr></thead>
      <tbody>{eval_rows}</tbody>
    </table>
  </div>
  <p><strong>Tam olarak bir aralık sıfırı dışlıyor — ve o da negatif tarafta.</strong>
    Hiçbir şeyin değerlendirmeyi iyileştirdiği gösterilemedi; bir terimin
    kötüleştirdiği gösterildi.</p>

  <div class="panel flag">
    <p><strong>Ve proje bunu baştan söylemişti.</strong> Erken bir ölçüm çözünürlük
      tabanını kurmuştu: ≥100 Elo 7-65 oyunda çözülür, ≥40 ~350'de, ≥20 ~1.500'de,
      ≥10 ~6.000'de. Klasik değerlendirme terimleri +10 ile +25 arası eder.</p>
    <p>En iyi adaya <strong>1.200 oyun +12 [−8, +31]</strong> döndürdü — makul aralığın
      dibinde bir etki, çözünürlüğü ona az kala biten bir aletle ölçüldü. Program
      terimler değersiz olduğu için başarısız olmadı; bu boyuttaki etkiler harcanandan
      binlerce oyun fazlasını istediği için — ve tablo bunu hiçbiri oynanmadan önce
      söylemişti.</p>
  </div>

  <p>Çabanın nereye gittiğinin gerekçesi de bu: throughput işi <strong>+83 Elo</strong>
    üretti, ölçülmüş ve dönüştürülmüş halde, oyunların bir kesriyle — çünkü %39'luk bir
    hız değişimi 100-Elo sınıfı bir etki ve bu kurulumun rahatça çözdüğü bölgeye düşüyor.</p>
  <blockquote>Bir terimin değersiz olduğunu göstermek ile ölçemediğini göstermek aynı
    şey değil.</blockquote>

  <h3 class="sub-h">Ölçülebilen tek iyileştirme bir arama değişikliği</h3>
  <p>Değerlendirme tarafı boş dönerken <strong>SEE budaması</strong> — alışı geri-alışa
    kaybeden hamleleri quiescence'ta atlamak — 1.200 sabit oyunda
    <strong>+50 Elo [+30, +70]</strong> ölçtü. Projede aralığı pozitif tarafta sıfırdan
    uzak duran tek değişiklik.</p>
  <div class="scroll">
    <table>
      <thead><tr><th>aday</th><th class="num">240</th><th class="num">600</th>
        <th class="num">1.200</th><th></th></tr></thead>
      <tbody>
        <tr><td class="mono">passers-rooks</td><td class="mono num">—</td>
          <td class="mono num">+26 [+1, +51]</td>
          <td class="mono num strong">+12 [−8, +31]</td>
          <td class="note">düştü, aralık sıfırı yuttu</td></tr>
        <tr class="row-key"><td class="mono">SEE budaması</td>
          <td class="mono num">+48 [+11, +87]</td><td class="mono num">+46 [+20, +73]</td>
          <td class="mono num strong">+50 [+30, +70]</td>
          <td class="note">kıpırdamadı, aralık sıfırdan uzaklaşarak daraldı</td></tr>
      </tbody>
    </table>
  </div>
  <p><strong>Gerçek bir etkinin ve gürültünün ince ucunun görüntüsü bu</strong> — ve ikisi
    yalnızca <em>ikisi de sabit uzunlukta koştuğu için</em> ayırt edilebiliyor. Sekans
    testi ikisini de erken durdurup her biri için ~+110 raporlardı.</p>
  <div class="panel">
    <p><strong>Ve mekanizmanın veremediği sayı.</strong> Deterministik sayım SEE'nin
      belirli bir derinliğe ulaşma süresinin %23,3'ünü kaldırdığını söylüyordu —
      ölçülmüş dönüşümle <strong>+65</strong>, ama bu yalnızca throughput. Maç
      <strong>+50</strong> diyor. <strong>Aradaki +15 Elo, budamanın bedeli:</strong>
      atılan hatlardan sonradan önemli çıkanların maliyeti. Bu sayıyı projede başka
      hiçbir şey üretemez — aynı değişikliğin hem sayılmış hem oynanmış ölçümünü
      gerektiriyor ve ikisinin farkı.</p>
  </div>
</section>

<section>
  <h2>Ön-kayıt sicili</h2>
  <p class="sec-sub">Her tahmin, ilk oyundan önce commit'lendi</p>
  <p>Veriye bakıldıktan sonra seçilen parantez, parantez değildir. Tahminlerin
    tutmadığı üç durum da burada — çıkarıldıkları için değil, kayıtlı oldukları için.</p>
  <div class="pr-grid">{prereg_rows}</div>
</section>

<section>
  <h2>Geri alınan iddialar</h2>
  <p class="sec-sub">Sonradan düzeltildi, silinmedi</p>
  <ol class="corr">{corr_items}</ol>
</section>

<section>
  <h2>Ölçülmeyen ne</h2>
  <p class="sec-sub">«Çözülmedi» ≠ «reddedildi»</p>
  <div class="nm-grid">{nm_items}</div>
  <hr class="rule">
</section>

<footer>
  <p><strong>Atropos</strong> — Python 3.11, python-chess, Streamlit. Negamax +
    alpha-beta, quiescence, transposition table, null-move, LMR, aspiration windows,
    static exchange evaluation. UCI protokolü, perft doğrulaması, SPRT tabanlı Elo hattı.
    724 test, mypy temiz.</p>
  <p>Her koşu duvar saati, CPU-saniye, node sayısı, tepe RAM ve commit hash'i ile
    kaydedilir. Telemetriden önceki kayıtlar <code>commit unknown</code> olarak
    damgalandı — çalışma ağacı proje boyunca kirliydi, dolayısıyla bir dosyayı tarihe
    bakıp commit'e bağlamak koşunun kullanmadığı bir commit'i adlandırmak olurdu.</p>
</footer>

</div>
"""

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(HTML, encoding="utf-8")
print(f"wrote {OUT} ({len(HTML):,} bytes)")
