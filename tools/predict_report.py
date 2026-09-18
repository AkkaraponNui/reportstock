"""Turn a prediction run into a markdown report a person can read.

`predict.py` writes JSON, which is right for machines and useless for thinking.
This renders the same run as prose and tables: what the model says, how much of it
to believe, which assumption is carrying the answer, and what would change it.

Used by `tools/predict.py` after every run and by the prediction page in the app.
Reports land in data/reports/<YYYY-MM-DD>-<slug>-prediction.md.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import REPORTS, today  # noqa: E402

BLOCKS = "▁▂▃▄▅▆▇█"


# ---------------------------------------------------------------------------
# formatting helpers
# ---------------------------------------------------------------------------

def _pct(v, digits=1, sign=False):
    if v is None:
        return "n/a"
    fmt = "{:+." + str(digits) + "f}%" if sign else "{:." + str(digits) + "f}%"
    return fmt.format(v * 100)


def _num(v, digits=2):
    return "n/a" if v is None else "{:,.{d}f}".format(v, d=digits)


def histogram(values, bins=24):
    """A text histogram. Markdown has no charts and a shape still beats a table."""
    vals = [v for v in (values or []) if v is not None]
    if len(vals) < 5:
        return ""
    lo, hi = min(vals), max(vals)
    if hi <= lo:
        return ""
    counts = [0] * bins
    for v in vals:
        idx = int((v - lo) / (hi - lo) * (bins - 1))
        counts[idx] += 1
    peak = max(counts) or 1
    line = "".join(BLOCKS[min(len(BLOCKS) - 1, int(c / peak * (len(BLOCKS) - 1)))] for c in counts)
    return "```text\n{}\n{:<{w}}{}\n```".format(
        line, _pct(lo, 0, sign=True), _pct(hi, 0, sign=True), w=max(1, bins - 6)
    )


def verdict_line(sim):
    """The one sentence a reader who stops here should take away."""
    r = sim["annualized_return"]
    p = sim["probabilities"]
    med, lo, hi = r["p50"], r["p05"], r["p95"]
    loss = p["loses_money"]

    if med >= 0.12 and loss < 0.20:
        shape = "สมมติฐานชุดนี้ให้ผลตอบแทนที่ดีและกระจายตัวไปทางบวกเป็นส่วนใหญ่"
    elif med >= 0.08:
        shape = "สมมติฐานชุดนี้ให้ผลตอบแทนพอใช้ แต่มีรอบที่ขาดทุนอยู่ไม่น้อย"
    elif med >= 0.0:
        shape = "สมมติฐานชุดนี้แทบไม่เหลือผลตอบแทน หลังหักความเสี่ยงแล้วถือว่าไม่คุ้ม"
    else:
        shape = "สมมติฐานชุดนี้ให้ผลติดลบที่ค่ากลาง ซึ่งแปลว่าราคาปัจจุบันเรียกร้องมากกว่าที่ธุรกิจน่าจะทำได้"

    return (
        "{} ค่ากลางอยู่ที่ {} ต่อปี ช่วงกลาง 90% กินตั้งแต่ {} ถึง {} "
        "และ {} ของรอบจำลองจบด้วยการขาดทุน".format(
            shape, _pct(med, 1, sign=True), _pct(lo, 1, sign=True),
            _pct(hi, 1, sign=True), _pct(loss, 0)
        )
    )


def trust_line(fit):
    """How much weight the fitted curve can carry, said plainly."""
    if not fit.get("fitted"):
        return "ประมาณเส้นชะลอตัวไม่ได้ ระบบจึงใช้ค่าตั้งต้นแทน ผลลัพธ์ทุกตัวจึงอ่อนกว่าปกติ"
    r2, n = fit.get("r2", 0), fit.get("n", 0)
    if r2 >= 0.5 and n >= 60:
        strength = "เส้นนี้พอเชื่อถือได้ในระดับหนึ่ง"
    elif r2 >= 0.25:
        strength = "เส้นนี้เป็นแนวโน้มกลางที่อ่อน ไม่ใช่กฎ"
    else:
        strength = "เส้นนี้แทบไม่มีพลังอธิบาย ใช้เป็นเพียงจุดตั้งต้นเท่านั้น"
    return "{} ประมาณจาก {} ปี-บริษัท จาก {} บริษัท ได้ R-squared {:.2f}".format(
        strength, n, fit.get("n_companies", "?"), r2
    )


# ---------------------------------------------------------------------------
# single-ticker report
# ---------------------------------------------------------------------------

def render_single(res):
    ticker = res.get("ticker", "?")
    company = res.get("company") or "ไม่ทราบชื่อ"
    sim = res.get("simulation") or {}
    fit = res.get("fade_fit") or {}
    sens = res.get("sensitivity") or {}

    out = [
        "# รายงานโมเดลพยากรณ์การเติบโต: {} {}".format(ticker, company),
        "",
        "สร้างเมื่อ {} · ใช้ข้อมูลจาก `{}` · กลุ่ม {}".format(
            today(), res.get("source_snapshot", "?"), res.get("sector") or "ไม่ระบุ"
        ),
        "",
    ]

    if not sim.get("ok"):
        out += [
            "## จำลองไม่สำเร็จ",
            "",
            sim.get("reason", "ไม่ทราบสาเหตุ"),
            "",
            "ข้อมูลที่จำเป็นไม่ครบ ลองดึงงบการเงินใหม่แล้วรันอีกครั้ง",
            "",
        ]
        return "\n".join(out)

    r = sim["annualized_return"]
    p = sim["probabilities"]
    inp = sim.get("inputs") or {}
    end = sim.get("ending_state_median") or {}

    # --- the answer, first ---
    out += [
        "## สรุป",
        "",
        verdict_line(sim),
        "",
        trust_line(fit),
        "",
        "ก่อนอ่านต่อ ตัวเลขทุกตัวในรายงานนี้เป็นผลทางคณิตศาสตร์ของสมมติฐานที่ระบุไว้ ไม่ใช่การพยากรณ์ราคา "
        "และไม่เคยถูกตรวจสอบกับผลลัพธ์จริงนอกชุดข้อมูล ช่วงที่เห็นคือช่วงของสมมติฐาน "
        "ไม่ใช่ความน่าจะเป็นของสิ่งที่จะเกิดขึ้นในโลกจริง",
        "",
    ]

    # --- distribution ---
    out += [
        "## ช่วงผลตอบแทนที่จำลองได้",
        "",
        "จำลอง {:,} รอบ มองไปข้างหน้า {} ปี".format(sim.get("runs", 0), sim.get("years", 5)),
        "",
        "| เปอร์เซ็นไทล์ | ผลตอบแทนต่อปี | อ่านว่าอย่างไร |",
        "|---|---:|---|",
        "| แย่สุด 5% | {} | เลวร้ายกว่านี้เกิดขึ้นได้ 1 ใน 20 รอบ |".format(_pct(r["p05"], 1, True)),
        "| 25% | {} | หนึ่งในสี่ของรอบแย่กว่านี้ |".format(_pct(r["p25"], 1, True)),
        "| **ค่ากลาง** | **{}** | **ครึ่งหนึ่งดีกว่านี้ ครึ่งหนึ่งแย่กว่า** |".format(_pct(r["p50"], 1, True)),
        "| 75% | {} | หนึ่งในสี่ของรอบดีกว่านี้ |".format(_pct(r["p75"], 1, True)),
        "| ดีสุด 5% | {} | ดีกว่านี้เกิดขึ้นได้ 1 ใน 20 รอบ |".format(_pct(r["p95"], 1, True)),
        "",
    ]

    hist = histogram(sim.get("distribution"))
    if hist:
        out += ["รูปร่างการกระจายตัวของผลตอบแทนต่อปี", "", hist, ""]

    out += [
        "| เกณฑ์ | สัดส่วนของรอบจำลอง |",
        "|---|---:|",
        "| ขาดทุน | {} |".format(_pct(p["loses_money"], 0)),
        "| ชนะ 4% ต่อปี | {} |".format(_pct(p["beats_4pct"], 0)),
        "| ชนะ 8% ต่อปี | {} |".format(_pct(p["beats_8pct"], 0)),
        "| ชนะ 15% ต่อปี | {} |".format(_pct(p["beats_15pct"], 0)),
        "| เงินเป็นสองเท่าใน 5 ปี | {} |".format(_pct(p["doubles_in_5y"], 0)),
        "",
        "ตัวเลขเหล่านี้คือสัดส่วนของรอบจำลอง ไม่ใช่ความน่าจะเป็นในโลกจริง",
        "",
    ]

    # --- what matters most ---
    if sens.get("ok") and sens.get("levers"):
        top = sens["levers"][0]
        out += [
            "## สมมติฐานไหนเป็นตัวตัดสิน",
            "",
            "ปัจจัยที่มีผลมากที่สุดคือ **{}** ซึ่งขยับค่ากลางได้ {} จุดเมื่อเปลี่ยนจากฝั่งต่ำไปฝั่งสูง "
            "ถ้าจะตรวจสอบอะไรสักอย่างก่อนเชื่อผลลัพธ์ทั้งหมดนี้ ให้ตรวจตัวนี้ก่อน".format(
                top["lever"], _num(top["swing"] * 100, 1)
            ),
            "",
            "| ปัจจัย | ค่าปัจจุบัน | ถ้าแย่กว่าที่คิด | ถ้าดีกว่าที่คิด | ช่วงกว้าง |",
            "|---|---|---:|---:|---:|",
        ]
        for x in sens["levers"]:
            out.append(
                "| {} | {} | {} | {} | {} จุด |".format(
                    x["lever"], x.get("description", ""),
                    _pct(x["low_median"], 1, True), _pct(x["high_median"], 1, True),
                    _num(x["swing"] * 100, 1),
                )
            )
        out += [
            "",
            "แต่ละแถวคือการขยับสมมติฐานหนึ่งตัวขึ้นและลงโดยตรึงตัวอื่นไว้ ลำดับสำคัญกว่าขนาด",
            "",
        ]
        if "ตัวคูณ" in top["lever"]:
            out += [
                "ข้อสังเกตที่ควรอึดอัด ปัจจัยที่กำหนดคำตอบมากที่สุดคือตัวคูณตอนขาย "
                "ซึ่งเป็นสิ่งที่ไม่มีใครพยากรณ์ได้ มันสะท้อนอารมณ์ตลาดในอีกห้าปีข้างหน้า ไม่ใช่ผลงานของธุรกิจ "
                "แปลว่าผลลัพธ์ของโมเดลนี้ขึ้นกับสิ่งที่ควบคุมไม่ได้มากกว่าสิ่งที่วิเคราะห์ได้",
                "",
            ]

    # --- assumptions ---
    out += [
        "## สมมติฐานที่ใช้",
        "",
        "| รายการ | ค่า |",
        "|---|---:|",
        "| อัตราเติบโตเริ่มต้น | {} |".format(_pct(inp.get("start_growth"))),
        "| ความผันผวนของการเติบโต | {} |".format(_pct(inp.get("growth_volatility"))),
        "| ความคงทนของการเติบโต | {} ต่อปี |".format(_pct(inp.get("persistence_slope"), 0)),
        "| ความไม่แน่นอนของความคงทน | ±{} |".format(_pct(inp.get("persistence_slope_se"), 0)),
        "| มาร์จิ้นสุทธิปัจจุบัน | {} |".format(_pct(inp.get("start_net_margin"))),
        "| ทิศทางมาร์จิ้นต่อปี | {} |".format(_pct(inp.get("margin_trend_per_year"), 2)),
        "| P/E ข้างหน้า | {} |".format(_num(inp.get("forward_pe"), 1)),
        "| ตัวคูณยอดขายปัจจุบัน | {} |".format(_num(inp.get("current_sales_multiple"))),
        "| ฐานที่ใช้คำนวณตัวคูณ | {} |".format(inp.get("sales_multiple_basis") or "-"),
        "| อัตราเติบโตปลายทาง | {} |".format(_pct(inp.get("terminal_growth"))),
        "",
        "สภาพปลายทางที่ค่ากลางของรอบจำลอง: เติบโต {} ต่อปี มาร์จิ้นสุทธิ {} และ P/E ตอนขาย {}".format(
            _pct(end.get("growth_year5")), _pct(end.get("net_margin")), _num(end.get("exit_pe"), 1)
        ),
        "",
    ]

    if inp.get("assumed_margin_for_loss_maker"):
        out += [
            "> บริษัทนี้ยังขาดทุน โมเดลจึงสมมติว่าจะทำมาร์จิ้นสุทธิได้ 8% ในอนาคต "
            "และให้น้ำหนัก 25% กับกรณีที่ไม่มีวันทำกำไรได้จริง "
            "ผลลัพธ์ทั้งหมดจึงขึ้นกับสมมติฐานที่ตั้งขึ้นเองมากกว่าปกติ",
            "",
        ]
    if str(inp.get("sales_multiple_basis", "")).startswith("trailing_pe"):
        out += [
            "> ตัวคูณยอดขายคำนวณจาก P/E คูณมาร์จิ้นสุทธิ ซึ่งเป็นหน่วยที่สอดคล้องกันเสมอ "
            "ต่างจาก P/S ที่แหล่งข้อมูลให้มา ซึ่งผิดหน่วยเมื่อหุ้นซื้อขายคนละสกุลเงินกับที่รายงานงบ",
            "",
        ]

    # --- the fitted curve ---
    out += ["## เส้นการชะลอตัวที่ประมาณได้", ""]
    if fit.get("fitted"):
        out += [
            "```text",
            "การเติบโตปีหน้า = {:.4f} + {:.4f} × การเติบโตปีนี้".format(fit["a"], fit["b"]),
            "```",
            "",
            fit.get("interpretation", ""),
            "",
            "| รายการ | ค่า |",
            "|---|---:|",
            "| ความชัน | {:.3f} |".format(fit["b"]),
            "| จุดตัด | {:.3f} |".format(fit["a"]),
            "| R-squared | {:.3f} |".format(fit["r2"]),
            "| ค่าเบี่ยงเบนที่เหลือ | {} |".format(_pct(fit["resid_sd"])),
            "| จำนวนข้อมูล | {} ปี-บริษัท |".format(fit["n"]),
            "| จำนวนบริษัท | {} |".format(fit.get("n_companies", "?")),
            "| ใช้ชุดที่ตัดค่าสุดขั้ว | {} |".format("ใช่" if fit.get("basis") == "trimmed" else "ไม่"),
            "| จุดที่ถูกตัดออก | {} |".format(fit.get("n_excluded_by_trim", 0)),
            "",
        ]
        if fit.get("trimmed_fit") and fit.get("full_fit"):
            out += [
                "ประมาณสองครั้งโดยตั้งใจ เพราะในชุดข้อมูลเล็กแบบนี้ ปีที่โตผิดปกติไม่กี่จุด "
                "จะดึงเส้นถดถอยเข้าหาตัวเองและดัน R-squared ให้สูงเกินจริง",
                "",
                "| ชุด | ความชัน | R-squared | จำนวนข้อมูล |",
                "|---|---:|---:|---:|",
                "| ใช้ทุกจุด | {:.3f} | {:.3f} | {} |".format(
                    fit["full_fit"]["b"], fit["full_fit"]["r2"], fit["full_fit"]["n"]),
                "| ตัดค่าสุดขั้ว | {:.3f} | {:.3f} | {} |".format(
                    fit["trimmed_fit"]["b"], fit["trimmed_fit"]["r2"], fit["trimmed_fit"]["n"]),
                "",
                "ความต่างของความชัน {:.3f} ถูกนับเป็นความไม่แน่นอนเพิ่มเข้าไปในการจำลอง "
                "แทนที่จะเลือกเส้นใดเส้นหนึ่งแล้วทำเป็นว่ามันถูก".format(fit.get("slope_disagreement", 0)),
                "",
            ]
    else:
        out += [fit.get("reason", "ประมาณค่าไม่ได้"), ""]

    # --- history ---
    hist_vals = res.get("historical_growth") or []
    periods = res.get("historical_periods") or []
    if hist_vals and periods:
        n = min(len(hist_vals), len(periods))
        out += [
            "## ประวัติการเติบโตของรายได้",
            "",
            "| รอบบัญชี | " + " | ".join(periods[:n]) + " |",
            "|---|" + "---:|" * n,
            "| เติบโต | " + " | ".join(_pct(v) for v in hist_vals[:n]) + " |",
            "",
            "ความผันผวนของตัวเลขชุดนี้คือสิ่งที่โมเดลใช้เป็นขนาดของความไม่แน่นอน "
            "บริษัทที่การเติบโตเหวี่ยงมากในอดีตจะได้ช่วงผลลัพธ์ที่กว้างกว่า",
            "",
        ]

    out += _limitations()
    return "\n".join(out)


def _limitations():
    return [
        "## ข้อจำกัดของรายงานนี้",
        "",
        "**ไม่เคยถูกตรวจสอบย้อนหลัง** Yahoo Finance ให้ข้อมูลปัจจุบันโดยไม่มีประวัติแบบ point-in-time "
        "การทำ backtest อย่างซื่อสัตย์จึงเป็นไปไม่ได้ด้วยแหล่งข้อมูลนี้ "
        "ไม่มีหลักฐานว่าโมเดลนี้เคยทำนายอะไรได้ถูก",
        "",
        "**ช่วงที่เห็นคือช่วงของสมมติฐาน** ไม่ใช่ความน่าจะเป็นในโลกจริง "
        "ถ้าสมมติฐานตั้งไว้ผิด ตัวเลขทุกตัวก็ผิดตามไปด้วยโดยที่ความกว้างของช่วงไม่ได้บอกอะไร",
        "",
        "**โมเดลมองไม่เห็นธุรกิจที่กำลังเปลี่ยนรูป** มันอ่านอดีตแล้วสมมติว่ารูปแบบเดิมดำเนินต่อ "
        "ซึ่งในช่วงห้าปีมักเป็นสิ่งที่ตัดสินผลลัพธ์จริง คู่แข่งรายใหม่ กฎเกณฑ์ที่เปลี่ยน "
        "หรือสินค้าที่ยังไม่มีใครต้องการวันนี้ ไม่มีอยู่ในสมการใดเลย",
        "",
        "**ข้อมูลตั้งต้นมีข้อจำกัดของตัวเอง** ข้อมูลดีเลย์และมีการแก้ย้อนหลัง "
        "หุ้นกลุ่มธนาคารทำให้อัตราส่วนหลายตัวไม่มีความหมาย "
        "และจำนวนบริษัทที่ใช้ประมาณเส้นชะลอตัวยังน้อยเกินกว่าจะเรียกว่าเป็นค่าทางสถิติที่มั่นคง",
        "",
        "เครื่องมือวิจัย ไม่ใช่คำแนะนำการลงทุน การตัดสินใจและความเสี่ยงทั้งหมดเป็นของผู้ใช้",
        "",
    ]


# ---------------------------------------------------------------------------
# comparison report
# ---------------------------------------------------------------------------

def render_comparison(results):
    runnable = [r for r in results if (r.get("simulation") or {}).get("ok")]
    failed = [r for r in results if not (r.get("simulation") or {}).get("ok")]

    out = [
        "# รายงานโมเดลพยากรณ์: เปรียบเทียบ {} ตัว".format(len(results)),
        "",
        "สร้างเมื่อ {} · จำลองด้วยสมมติฐานและเส้นชะลอตัวชุดเดียวกันทุกตัว".format(today()),
        "",
    ]

    if not runnable:
        out += ["จำลองไม่สำเร็จสักตัว", ""]
        return "\n".join(out)

    runnable.sort(key=lambda r: -(r["simulation"]["annualized_return"]["p50"]))

    out += [
        "## อันดับตามค่ากลาง",
        "",
        "| อันดับ | หุ้น | บริษัท | แย่สุด 5% | ค่ากลาง | ดีสุด 5% | โอกาสขาดทุน | ปัจจัยที่เป็นตัวตัดสิน |",
        "|---:|---|---|---:|---:|---:|---:|---|",
    ]
    for i, res in enumerate(runnable, 1):
        sim = res["simulation"]
        r = sim["annualized_return"]
        sens = res.get("sensitivity") or {}
        top = (sens.get("levers") or [{}])[0].get("lever", "-") if sens.get("ok") else "-"
        out.append(
            "| {} | {} | {} | {} | **{}** | {} | {} | {} |".format(
                i, res["ticker"], (res.get("company") or "?")[:24],
                _pct(r["p05"], 1, True), _pct(r["p50"], 1, True), _pct(r["p95"], 1, True),
                _pct(sim["probabilities"]["loses_money"], 0), top,
            )
        )
    out.append("")

    # A spread this wide usually says more than the ranking does.
    widest = max(runnable, key=lambda r: r["simulation"]["annualized_return"]["p95"]
                 - r["simulation"]["annualized_return"]["p05"])
    narrowest = min(runnable, key=lambda r: r["simulation"]["annualized_return"]["p95"]
                    - r["simulation"]["annualized_return"]["p05"])
    w = widest["simulation"]["annualized_return"]
    nw = narrowest["simulation"]["annualized_return"]
    out += [
        "## ความกว้างของช่วงบอกอะไร",
        "",
        "อันดับข้างบนเรียงตามค่ากลาง ซึ่งเป็นตัวเลขเดียวและซ่อนความไม่แน่นอนไว้ "
        "ช่วงที่กว้างกว่าแปลว่าคำตอบขึ้นกับสมมติฐานมากกว่า ไม่ได้แปลว่าแย่กว่า",
        "",
        "- **{}** มีช่วงกว้างที่สุด {} จุด ตั้งแต่ {} ถึง {}".format(
            widest["ticker"], _num((w["p95"] - w["p05"]) * 100, 0),
            _pct(w["p05"], 0, True), _pct(w["p95"], 0, True)),
        "- **{}** มีช่วงแคบที่สุด {} จุด ตั้งแต่ {} ถึง {}".format(
            narrowest["ticker"], _num((nw["p95"] - nw["p05"]) * 100, 0),
            _pct(nw["p05"], 0, True), _pct(nw["p95"], 0, True)),
        "",
    ]

    sectors = {}
    for res in runnable:
        s = res.get("sector") or "ไม่ระบุ"
        sectors.setdefault(s, []).append(res["ticker"])
    concentrated = {k: v for k, v in sectors.items() if len(v) > 1}
    if concentrated:
        out += [
            "## ความกระจุกตัว",
            "",
            "หุ้นหลายตัวที่ดูกระจายความเสี่ยงอาจเป็นตำแหน่งเดียวกันในชื่อที่ต่างกัน",
            "",
        ]
        for sector, tks in concentrated.items():
            out.append("- กลุ่ม {} มี {} ตัว: {}".format(sector, len(tks), ", ".join(tks)))
        out += [
            "",
            "ถ้าการเติบโตของหุ้นเหล่านี้พึ่งพาแรงขับเดียวกัน เช่น วัฏจักรการลงทุนรอบเดียวกัน "
            "การถือหลายตัวไม่ได้ลดความเสี่ยงอย่างที่จำนวนตัวบ่งบอก",
            "",
        ]

    out += ["## รายละเอียดแต่ละตัว", ""]
    for res in runnable:
        sim = res["simulation"]
        inp = sim.get("inputs") or {}
        out += [
            "### {} · {}".format(res["ticker"], res.get("company") or "?"),
            "",
            verdict_line(sim),
            "",
            "เริ่มจากอัตราเติบโต {} มาร์จิ้นสุทธิ {} และ P/E ข้างหน้า {}".format(
                _pct(inp.get("start_growth")), _pct(inp.get("start_net_margin")),
                _num(inp.get("forward_pe"), 1)),
            "",
        ]
        h = histogram(sim.get("distribution"), bins=20)
        if h:
            out += [h, ""]

    if failed:
        out += ["## จำลองไม่สำเร็จ", ""]
        for res in failed:
            out.append("- {}: {}".format(
                res.get("ticker", "?"), (res.get("simulation") or {}).get("reason", "ไม่ทราบสาเหตุ")))
        out.append("")

    fit = runnable[0].get("fade_fit") or {}
    if fit.get("fitted"):
        out += [
            "## เส้นชะลอตัวที่ใช้ร่วมกัน",
            "",
            "```text",
            "การเติบโตปีหน้า = {:.4f} + {:.4f} × การเติบโตปีนี้".format(fit["a"], fit["b"]),
            "```",
            "",
            fit.get("interpretation", ""),
            "",
        ]

    out += _limitations()
    return "\n".join(out)


# ---------------------------------------------------------------------------
# writing
# ---------------------------------------------------------------------------

def write_report(results, name=None, out_date=None):
    """Write one report for one result, or a comparison for several.

    Returns the path written.
    """
    if isinstance(results, dict):
        results = [results]
    if not results:
        raise ValueError("Nothing to report on.")

    stamp = out_date or today()
    if len(results) == 1:
        slug = name or results[0].get("ticker", "unknown").lower().replace(".", "-")
        body = render_single(results[0])
    else:
        slug = name or "compare-{}".format(len(results))
        body = render_comparison(results)

    path = REPORTS / "{}-{}-prediction.md".format(stamp, slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path
