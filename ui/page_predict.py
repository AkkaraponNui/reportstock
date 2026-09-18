"""Growth prediction: fitted fade, Monte Carlo distribution, and sensitivity."""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

from shared import (
    C_ACCENT,
    C_MUTED,
    C_NEGATIVE,
    C_POSITIVE,
    C_PRIMARY,
    fmt_num,
    fmt_pct,
    tickers_on_disk,
)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from common import latest_snapshot, read_json, today, write_json  # noqa: E402

PREDICTIONS = ROOT / "data" / "predictions"


@st.cache_data(ttl=600, show_spinner=False)
def cached_fit():
    from predict import fit_fade

    return fit_fade()


def run_prediction(ticker, runs, years, terminal, write_md=True):
    """Run one ticker and persist both the JSON and, by default, a readable report."""
    from predict import fit_fade, predict_ticker
    from predict_report import write_report

    res = predict_ticker(ticker, fit=fit_fade(), years=years, runs=runs, terminal=terminal)
    write_json(PREDICTIONS / ticker.upper() / "{}.json".format(today()), res)
    report_path = write_report(res) if write_md else None
    return res, report_path


def run_batch(tickers, runs, years, terminal, name, progress=None):
    """Run several tickers and write one comparison report covering all of them."""
    from predict import fit_fade, predict_ticker
    from predict_report import write_report

    fit = fit_fade()
    results = []
    for i, tk in enumerate(tickers):
        if progress:
            progress((i) / len(tickers), "กำลังจำลอง {} ...".format(tk))
        try:
            res = predict_ticker(tk, fit=fit, years=years, runs=runs, terminal=terminal)
            write_json(PREDICTIONS / tk.upper() / "{}.json".format(today()), res)
            results.append(res)
        except Exception as e:
            results.append(
                {
                    "ticker": tk.upper(),
                    "simulation": {"ok": False, "reason": "{}: {}".format(type(e).__name__, e)},
                }
            )
    if progress:
        progress(1.0, "กำลังเขียนรายงาน ...")
    path = write_report(results, name=name) if results else None
    return results, path


def load_prediction(ticker):
    return read_json(latest_snapshot(PREDICTIONS / ticker.upper()) or Path("/nonexistent"))


def fade_panel(fit):
    st.subheader("เส้นการชะลอตัวที่ประมาณจากข้อมูลจริง")

    if not fit.get("fitted"):
        st.warning(fit.get("reason", "ประมาณค่าไม่ได้"))
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("ความคงทนของการเติบโต", "{:.0%}".format(fit["b"]),
              "ของปีก่อนที่ส่งต่อมาปีนี้", delta_color="off")
    c2.metric("R-squared", "{:.2f}".format(fit["r2"]),
              "อธิบายความผันแปรได้เท่านี้", delta_color="off")
    c3.metric("จำนวนข้อมูล", "{} ปี-บริษัท".format(fit["n"]),
              "จาก {} บริษัท".format(fit["n_companies"]), delta_color="off")
    c4.metric("ค่าเบี่ยงเบนที่เหลือ", "{:.1%}".format(fit["resid_sd"]),
              "ความคลาดเคลื่อนต่อปี", delta_color="off")

    st.info(fit.get("interpretation", ""), icon=":material/functions:")

    if fit.get("r2", 0) < 0.4:
        st.caption(
            "R-squared ต่ำเป็นเรื่องปกติและเป็นเรื่องจริงของข้อมูลชุดนี้ "
            "อัตราการเติบโตของปีหน้าส่วนใหญ่ไม่ได้ถูกกำหนดโดยปีนี้ "
            "เส้นนี้จึงเป็นแนวโน้มกลางที่อ่อน ไม่ใช่กฎ และการจำลองข้างล่างสุ่มความชันนี้แทนที่จะตรึงไว้"
        )

    _fade_chart(fit)

    with st.expander("รายละเอียดการประมาณค่า"):
        st.write("สมการ: next_growth = {:.4f} + {:.4f} × current_growth".format(fit["a"], fit["b"]))
        st.write("ใช้ผลจากชุดที่ตัดค่าสุดขั้วออก:", fit.get("basis") == "trimmed")
        st.write("ตัดปีที่โตเกิน {:.0%} ออกไป {} จุด".format(
            fit.get("trim_at", 0.5), fit.get("n_excluded_by_trim", 0)))
        cc1, cc2 = st.columns(2)
        cc1.write("**ใช้ทุกจุด**")
        cc1.json(fit.get("full_fit") or {})
        cc2.write("**ตัดค่าสุดขั้ว**")
        cc2.json(fit.get("trimmed_fit") or {})
        st.caption(
            "ในชุดข้อมูลเล็กแบบนี้ จุดที่โตผิดปกติไม่กี่จุดจะดึงเส้นถดถอยเข้าหาตัวเองและดัน R-squared ให้สูงเกินจริง "
            "ระบบจึงประมาณสองครั้งแล้วใช้เวอร์ชันที่ไม่ได้ถูกจุดไม่กี่จุดควบคุม "
            "ส่วนความต่างระหว่างสองเส้นถูกนับเป็นความไม่แน่นอนของความชันเพิ่มเข้าไป"
        )
        st.write("บริษัทที่เข้าร่วมประมาณค่า:")
        st.dataframe(fit.get("companies") or [], width="stretch", hide_index=True)


def _fade_chart(fit):
    import plotly.graph_objects as go

    xs = [i / 100.0 for i in range(-20, 81)]
    ys = [fit["a"] + fit["b"] * x for x in xs]

    fig = go.Figure()
    fig.add_scatter(x=xs, y=ys, mode="lines", name="เส้นที่ประมาณได้",
                    line=dict(color=C_PRIMARY, width=3))
    fig.add_scatter(x=xs, y=xs, mode="lines", name="ถ้าโตเท่าเดิมทุกปี",
                    line=dict(color=C_MUTED, width=2, dash="dash"))
    band_hi = [y + fit["resid_sd"] for y in ys]
    band_lo = [y - fit["resid_sd"] for y in ys]
    fig.add_scatter(x=xs + xs[::-1], y=band_hi + band_lo[::-1], fill="toself",
                    fillcolor="rgba(37,99,235,0.12)", line=dict(width=0),
                    name="ช่วงความคลาดเคลื่อน", hoverinfo="skip")
    fig.update_layout(
        height=340, margin=dict(l=10, r=10, t=30, b=10),
        xaxis=dict(title="การเติบโตปีนี้", tickformat=".0%"),
        yaxis=dict(title="การเติบโตปีหน้า", tickformat=".0%"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        hovermode="x unified",
    )
    st.plotly_chart(fig, width="stretch")
    st.caption(
        "เส้นทึบอยู่ต่ำกว่าเส้นประเสมอ นั่นคือการชะลอตัว บริษัทที่โตเร็วมากปีนี้มักโตช้าลงปีหน้า "
        "ส่วนบริษัทที่โตช้าจะค่อยๆ ขยับเข้าหาค่ากลาง"
    )


def distribution_chart(sim):
    import plotly.graph_objects as go

    dist = sim.get("distribution") or []
    r = sim["annualized_return"]
    if not dist:
        return

    fig = go.Figure()
    fig.add_histogram(x=[d * 100 for d in dist], nbinsx=45,
                      marker_color=C_PRIMARY, opacity=0.75, name="ผลจำลอง")
    for key, label, color in (("p05", "แย่สุด 5%", C_NEGATIVE),
                              ("p50", "ค่ากลาง", C_ACCENT),
                              ("p95", "ดีสุด 5%", C_POSITIVE)):
        fig.add_vline(x=r[key] * 100, line=dict(color=color, width=2, dash="dash"),
                      annotation_text="{} {:.0f}%".format(label, r[key] * 100),
                      annotation_position="top")
    fig.add_vline(x=0, line=dict(color=C_MUTED, width=1))
    fig.update_layout(
        height=340, margin=dict(l=10, r=10, t=40, b=10), showlegend=False,
        xaxis=dict(title="ผลตอบแทนต่อปีที่จำลองได้", ticksuffix="%"),
        yaxis=dict(title="จำนวนรอบจำลอง"),
    )
    st.plotly_chart(fig, width="stretch")


def sensitivity_chart(sens):
    import plotly.graph_objects as go

    levers = sens.get("levers") or []
    if not levers:
        return
    base = sens.get("base_median") or 0.0

    labels = [r["lever"] for r in levers][::-1]
    lows = [(r["low_median"] - base) * 100 for r in levers][::-1]
    highs = [(r["high_median"] - base) * 100 for r in levers][::-1]

    fig = go.Figure()
    fig.add_bar(y=labels, x=lows, orientation="h", name="สมมติฐานฝั่งต่ำ",
                marker_color=C_NEGATIVE, opacity=0.85)
    fig.add_bar(y=labels, x=highs, orientation="h", name="สมมติฐานฝั่งสูง",
                marker_color=C_POSITIVE, opacity=0.85)
    fig.update_layout(
        barmode="overlay", height=300, margin=dict(l=10, r=10, t=30, b=10),
        xaxis=dict(title="ผลตอบแทนต่อปีเปลี่ยนไปกี่จุด เทียบกับกรณีฐาน", ticksuffix=" จุด"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    fig.add_vline(x=0, line=dict(color=C_MUTED, width=2))
    st.plotly_chart(fig, width="stretch")


def _report_panel():
    """Show the report the last run produced, for reading or downloading."""
    path_str = st.session_state.get("last_prediction_report")
    if not path_str:
        return
    path = Path(path_str)
    if not path.exists():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        st.warning("อ่านไฟล์รายงานไม่ได้: {}".format(e))
        return

    c1, c2 = st.columns([1, 3])
    c1.download_button("ดาวน์โหลดรายงาน", text, file_name=path.name,
                       mime="text/markdown", width="stretch")
    c2.caption("รายงานล่าสุด: `{}` · {:.0f} KB · เก็บถาวรไว้ในเมนูรายงานที่สร้างไว้".format(
        path.name, path.stat().st_size / 1024))
    with st.expander("อ่านรายงาน"):
        st.markdown(text)


def render():
    st.title("โมเดลพยากรณ์การเติบโต")
    st.caption(
        "โมเดลนี้ทำสามอย่าง ประมาณว่าการเติบโตชะลอตัวเร็วแค่ไหนจากข้อมูลจริง "
        "จำลองผลลัพธ์หลายพันรอบเพื่อดูช่วงของความเป็นไปได้ "
        "และจัดอันดับว่าสมมติฐานไหนมีผลต่อคำตอบมากที่สุด"
    )

    st.error(
        "อ่านก่อนใช้ นี่ไม่ใช่การพยากรณ์ราคา และไม่เคยถูกตรวจสอบกับผลลัพธ์จริงที่อยู่นอกชุดข้อมูล "
        "เพราะ Yahoo Finance ให้ข้อมูลปัจจุบันโดยไม่มีประวัติย้อนหลังแบบ point-in-time "
        "การทำ backtest อย่างซื่อสัตย์จึงเป็นไปไม่ได้ด้วยแหล่งข้อมูลนี้ "
        "ช่วงตัวเลขที่เห็นคือช่วงของสมมติฐาน ไม่ใช่ความน่าจะเป็นของสิ่งที่จะเกิดขึ้นจริง",
        icon=":material/science:",
    )

    fit = cached_fit()
    fade_panel(fit)

    st.divider()

    known = tickers_on_disk()
    if not known:
        st.info("ยังไม่มีหุ้นในระบบ ไปที่หน้าค้นหาหุ้นเพื่อเพิ่มตัวแรก")
        return

    default = st.session_state.get("selected_ticker")
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    ticker = c1.selectbox("เลือกหุ้น", known,
                          index=known.index(default) if default in known else 0)
    runs = c2.select_slider("จำนวนรอบจำลอง", [2000, 5000, 10000, 20000, 50000], value=10000)
    years = c3.slider("มองไปข้างหน้า (ปี)", 3, 10, 5)
    terminal = c4.slider("อัตราโตปลายทาง", 0.0, 0.08, 0.04, step=0.005, format="%.3f")

    b1, b2 = st.columns([1, 1])
    if b1.button("รันโมเดลและเขียนรายงาน", type="primary", width="stretch"):
        with st.spinner("กำลังจำลอง {:,} รอบ...".format(runs)):
            try:
                _, report_path = run_prediction(ticker, runs, years, terminal)
                st.cache_data.clear()
                st.session_state["last_prediction_report"] = str(report_path) if report_path else None
                st.success("รันเสร็จแล้ว และเขียนรายงานไว้ที่ {}".format(
                    Path(report_path).name if report_path else "-"))
            except Exception as e:
                st.error("รันไม่สำเร็จ {}: {}".format(type(e).__name__, e))

    with b2.popover("รันหลายตัวแล้วเขียนรายงานเปรียบเทียบ", width="stretch"):
        picked = st.multiselect("เลือกหุ้น", known, default=known[: min(5, len(known))],
                                key="batch_predict_pick")
        slug = st.text_input("ชื่อไฟล์รายงาน", value="compare",
                             help="ไฟล์จะชื่อ <วันที่>-<ชื่อนี้>-prediction.md")
        if st.button("เริ่มรัน", type="primary", key="batch_predict_go"):
            if not picked:
                st.warning("ยังไม่ได้เลือกหุ้น")
            else:
                bar = st.progress(0.0, text="เริ่ม...")
                try:
                    results, path = run_batch(
                        picked, runs, years, terminal, slug.strip() or "compare",
                        progress=lambda p, m: bar.progress(p, text=m),
                    )
                    bar.empty()
                    st.cache_data.clear()
                    ok = sum(1 for r in results if (r.get("simulation") or {}).get("ok"))
                    st.session_state["last_prediction_report"] = str(path) if path else None
                    st.success("รันสำเร็จ {} จาก {} ตัว · รายงาน {}".format(
                        ok, len(picked), Path(path).name if path else "-"))
                except Exception as e:
                    bar.empty()
                    st.error("รันไม่สำเร็จ {}: {}".format(type(e).__name__, e))

    _report_panel()

    res = load_prediction(ticker)
    if not res:
        st.info("ยังไม่มีผลสำหรับ {} กดปุ่มรันโมเดลด้านบน".format(ticker))
        return

    sim = res.get("simulation") or {}
    if not sim.get("ok"):
        st.warning("จำลองไม่ได้: {}".format(sim.get("reason", "ไม่ทราบสาเหตุ")))
        return

    st.divider()
    st.subheader("{} · {}".format(res["ticker"], res.get("company") or ""))
    st.caption("ใช้ข้อมูลจาก {} · จำลอง {:,} รอบ · มองไปข้างหน้า {} ปี".format(
        res.get("source_snapshot", "?"), sim.get("runs", 0), sim.get("years", 5)))

    r = sim["annualized_return"]
    cols = st.columns(5)
    for col, (key, label) in zip(cols, [("p05", "แย่สุด 5%"), ("p25", "ค่อนข้างแย่"),
                                        ("p50", "ค่ากลาง"), ("p75", "ค่อนข้างดี"),
                                        ("p95", "ดีสุด 5%")]):
        col.metric(label, "{:+.1f}%".format(r[key] * 100), "ต่อปี", delta_color="off")

    p = sim["probabilities"]
    st.markdown("**สัดส่วนของรอบจำลองที่ให้ผลแต่ละแบบ**")
    pc = st.columns(5)
    for col, (key, label) in zip(pc, [("loses_money", "ขาดทุน"), ("beats_4pct", "ชนะ 4% ต่อปี"),
                                      ("beats_8pct", "ชนะ 8% ต่อปี"), ("beats_15pct", "ชนะ 15% ต่อปี"),
                                      ("doubles_in_5y", "เงินเป็นสองเท่า")]):
        col.metric(label, "{:.0f}%".format(p[key] * 100))
    st.caption(
        "ตัวเลขเหล่านี้คือสัดส่วนของรอบจำลอง ไม่ใช่ความน่าจะเป็นในโลกจริง "
        "มันบอกว่าสมมติฐานชุดนี้ให้ผลกระจายตัวอย่างไร ถ้าสมมติฐานผิด ตัวเลขทุกตัวก็ผิดตาม"
    )

    tabs = st.tabs(["การกระจายตัว", "ปัจจัยที่มีผลมากที่สุด", "สมมติฐานที่ใช้", "ประวัติการเติบโต"])

    with tabs[0]:
        distribution_chart(sim)
        end = sim.get("ending_state_median") or {}
        cc = st.columns(3)
        cc[0].metric("การเติบโตในปีสุดท้าย", fmt_pct(end.get("growth_year5")))
        cc[1].metric("มาร์จิ้นสุทธิปลายทาง", fmt_pct(end.get("net_margin")))
        cc[2].metric("P/E ตอนขาย", fmt_num(end.get("exit_pe")))
        st.caption("ทั้งสามค่าเป็นค่ากลางของรอบจำลองทั้งหมด")

    with tabs[1]:
        sens = res.get("sensitivity") or {}
        if not sens.get("ok"):
            st.info("วิเคราะห์ความอ่อนไหวไม่ได้")
        else:
            st.caption(
                "แต่ละแท่งคือการขยับสมมติฐานหนึ่งตัวขึ้นและลง แล้ววัดว่าค่ากลางเปลี่ยนไปกี่จุด "
                "ลำดับสำคัญกว่าขนาด เพราะมันบอกว่าควรไปเถียงกันเรื่องตัวเลขไหน"
            )
            sensitivity_chart(sens)
            rows = [
                {
                    "ปัจจัย": x["lever"],
                    "ค่าปัจจุบัน": x.get("description", ""),
                    "ถ้าแย่กว่าที่คิด": "{:+.1f}%".format(x["low_median"] * 100),
                    "ถ้าดีกว่าที่คิด": "{:+.1f}%".format(x["high_median"] * 100),
                    "ช่วงกว้าง": "{:.1f} จุด".format(x["swing"] * 100),
                }
                for x in sens["levers"]
            ]
            st.dataframe(rows, width="stretch", hide_index=True)
            if sens["levers"]:
                st.info(
                    "ปัจจัยที่มีผลมากที่สุดคือ {} ".format(sens["levers"][0]["lever"])
                    + "ซึ่งหมายความว่าคำตอบของโมเดลขึ้นกับสมมติฐานตัวนี้มากที่สุด "
                    "ถ้าจะตรวจสอบอะไรสักอย่างก่อนเชื่อผลลัพธ์ ให้ตรวจตัวนี้",
                    icon=":material/priority_high:",
                )

    with tabs[2]:
        inp = sim.get("inputs") or {}
        cc1, cc2 = st.columns(2)
        with cc1:
            st.markdown("**จุดเริ่มต้น**")
            st.write("อัตราโตเริ่มต้น", fmt_pct(inp.get("start_growth")))
            st.write("ความผันผวนของการเติบโต", fmt_pct(inp.get("growth_volatility")))
            st.write("มาร์จิ้นสุทธิปัจจุบัน", fmt_pct(inp.get("start_net_margin")))
            st.write("ทิศทางมาร์จิ้นต่อปี", fmt_pct(inp.get("margin_trend_per_year"), 2))
        with cc2:
            st.markdown("**การประเมินมูลค่า**")
            st.write("P/E ข้างหน้า", fmt_num(inp.get("forward_pe")))
            st.write("ตัวคูณยอดขายปัจจุบัน", fmt_num(inp.get("current_sales_multiple"), 2))
            st.write("ฐานที่ใช้คำนวณ", inp.get("sales_multiple_basis") or "-")
            st.write("อัตราโตปลายทาง", fmt_pct(inp.get("terminal_growth")))
        if inp.get("assumed_margin_for_loss_maker"):
            st.warning(
                "บริษัทนี้ยังขาดทุน โมเดลจึงสมมติว่าจะทำมาร์จิ้นได้ 8% ในอนาคต "
                "และให้น้ำหนัก 25% กับกรณีที่ไม่มีวันทำกำไรได้จริง ผลลัพธ์จึงขึ้นกับสมมติฐานนี้มาก",
                icon=":material/warning:",
            )
        if inp.get("sales_multiple_basis", "").startswith("trailing_pe"):
            st.caption(
                "ตัวคูณยอดขายคำนวณจาก P/E คูณมาร์จิ้นสุทธิ ซึ่งเป็นหน่วยที่สอดคล้องกันเสมอ "
                "ต่างจาก P/S ที่ Yahoo ให้มา ซึ่งผิดหน่วยเมื่อหุ้นซื้อขายคนละสกุลกับที่รายงานงบ"
            )

    with tabs[3]:
        _history(res)


def _history(res):
    import plotly.graph_objects as go

    hist = res.get("historical_growth") or []
    periods = res.get("historical_periods") or []
    if not hist or not periods:
        st.info("ไม่มีประวัติการเติบโตเพียงพอ")
        return
    n = min(len(hist), len(periods))
    fig = go.Figure(
        go.Bar(
            x=periods[:n],
            y=[None if h is None else h * 100 for h in hist[:n]],
            marker_color=[C_POSITIVE if (h or 0) >= 0 else C_NEGATIVE for h in hist[:n]],
            text=["n/a" if h is None else "{:.0f}%".format(h * 100) for h in hist[:n]],
            textposition="outside",
        )
    )
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=20, b=10),
                      yaxis=dict(title="การเติบโตของรายได้", ticksuffix="%"))
    st.plotly_chart(fig, width="stretch")
    st.caption(
        "ความผันผวนของแท่งเหล่านี้คือสิ่งที่โมเดลใช้เป็นขนาดของความไม่แน่นอน "
        "บริษัทที่การเติบโตเหวี่ยงมากในอดีตจะได้ช่วงผลลัพธ์ที่กว้างกว่า"
    )
