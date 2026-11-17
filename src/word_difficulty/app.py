"""Run with: python -m streamlit run src/word_difficulty/app.py"""

import hashlib
from pathlib import Path

import streamlit as st

from word_difficulty.cache import PredictionCache
from word_difficulty.classifier import ContextClassifier
from word_difficulty.export import csv_bytes, json_bytes, rows, txt_bytes, xlsx_bytes
from word_difficulty.lexicon import Lexicon
from word_difficulty.models import LEVELS
from word_difficulty.nlp import EnglishAnalyzer
from word_difficulty.parsers import SUPPORTED, parse_document
from word_difficulty.paths import data_dir
from word_difficulty.pipeline import analyze

st.set_page_config(page_title="词阶 · 英文词汇分级", page_icon="📖", layout="wide")
st.markdown(
    """
<style>
 .stApp { background: #f7f8f3; }
 h1, h2, h3 { color: #174f4a; letter-spacing: -.025em; }
 [data-testid="stSidebar"] { background: #eaf0e9; }
 [data-testid="stMetric"] { background: white; border: 1px solid #e3e8de;
   padding: 16px; border-radius: 12px; }
 .book-label { color: #658178; font-size: .8rem; letter-spacing: .16em; }
</style>
""",
    unsafe_allow_html=True,
)


@st.cache_resource
def load_analyzer():
    return EnglishAnalyzer()


@st.cache_resource
def load_lexicon(path: str, modified: int):
    return Lexicon(Path(path))


@st.cache_resource
def load_classifier(path: str, device: str):
    return ContextClassifier(Path(path), device)


@st.cache_data
def parse_upload(name: str, content: bytes):
    return parse_document(name, content)


def main():
    root = data_dir()
    wordlist = root / "words.csv"
    model_ready = (root / "model" / "model.safetensors").exists()
    with st.sidebar:
        st.markdown("### 词阶 / WORD LEVELS")
        st.caption("把一本书，整理成你的词汇清单。")
        st.divider()
        minimum = st.selectbox("最低显示等级", LEVELS, index=2)
        include_uncertain = st.checkbox("显示待确认词", value=True)
        include_proper = st.checkbox("显示专有名词", value=False)
        st.divider()
        use_model = st.toggle("使用上下文模型", value=model_ready, disabled=not model_ready)
        if model_ready:
            st.caption("词表优先；未收录或有歧义的词交由模型判断。")
        else:
            st.caption("当前使用词表分级。模型安装后可进一步补充未评级词。")
        with st.expander("分析设置与本地配置"):
            threshold = st.slider(
                "最低模型概率", 0.0, 1.0, 0.6, 0.05, help="低于阈值时进入待确认；概率不代表准确率。"
            )
            device = st.selectbox("模型运行设备", ("cpu", "cuda"))
            st.caption(f"数据目录：{root}")
            if not model_ready:
                st.code(".\\setup.ps1 -WithModel", language="powershell")
            st.caption("首次配置需要联网；分析时文件和推理保留在本机。")
        st.divider()
        st.caption("A1–A2 初学者 · B1–B2 独立使用者 · C1–C2 熟练使用者")

    st.markdown(
        '<div class="book-label">READ MORE · LEARN WITH CONTEXT</div>', unsafe_allow_html=True
    )
    st.title("读懂故事，也读懂生词。")
    st.write("上传英文书籍或字幕，按难度整理词汇，连同原句一起带走。")
    if not wordlist.exists():
        st.info("请先配置 CEFR 词表，然后刷新页面。")
        st.code(".\\setup.ps1", language="powershell")
        return
    upload = st.file_uploader(
        "选择书籍或字幕",
        type=list(SUPPORTED),
        help="支持 TXT、EPUB、SRT、VTT、DOCX、文本 PDF、ASS/SSA；单文件最多 100 MB。",
    )
    if st.button("使用示例文本", type="secondary"):
        st.session_state["demo"] = True
    if upload:
        name, content = upload.name, upload.getvalue()
    elif st.session_state.get("demo"):
        demo = Path(__file__).resolve().parents[2] / "examples" / "demo.txt"
        name, content = demo.name, demo.read_bytes()
    else:
        st.markdown("#### 从原文到词汇表")
        columns = st.columns(3)
        for column, title, text in zip(
            columns,
            ["01 · 保留上下文", "02 · 按 CEFR 分组", "03 · 导出学习清单"],
            [
                "每个词保留原句和出处。",
                "默认展示 B1–C2，未知词保留待确认。",
                "支持逐行 TXT、CSV、Excel 和完整 JSON。",
            ],
            strict=True,
        ):
            column.markdown(f"**{title}**")
            column.caption(text)
        return
    identity = hashlib.sha256(name.encode() + content).hexdigest()
    if st.session_state.get("file_identity") != identity:
        st.session_state.pop("analysis", None)
        st.session_state["file_identity"] = identity
    try:
        document = parse_upload(name, content)
    except ValueError as exc:
        st.error(str(exc))
        return
    with st.expander(f"文本预览 · {name} · {len(document.segments):,} 个片段"):
        st.text("\n\n".join(f"[{s.location}]\n{s.text}" for s in document.segments[:8]))
        for warning in document.warnings:
            st.warning(warning)
    configuration = (use_model, threshold, device)
    if st.button("开始分析", type="primary"):
        bar = st.progress(0.0, text="准备分析…")
        try:
            analyzer = load_analyzer()
            lexicon = load_lexicon(str(wordlist), wordlist.stat().st_mtime_ns)
            classifier = load_classifier(str(root / "model"), device) if use_model else None
            result = analyze(
                document,
                analyzer,
                lexicon,
                classifier,
                PredictionCache(root / "predictions.sqlite3") if classifier else None,
                threshold,
                progress=lambda fraction, message: bar.progress(fraction, text=message),
            )
            st.session_state["analysis"] = result
            st.session_state["analysis_configuration"] = configuration
        except Exception as exc:
            st.session_state.pop("analysis", None)
            st.error(f"分析未完成：{exc}")
        finally:
            bar.empty()
    result = st.session_state.get("analysis")
    if result is None:
        return
    if st.session_state.get("analysis_configuration") != configuration:
        st.info("分析设置已变更。下面仍为上次结果，点击“开始分析”可应用新设置。")
    st.divider()
    a, b, c, d = st.columns(4)
    a.metric("英文词语出现次数", f"{result.summary['occurrences']:,}")
    b.metric("已分级词条", f"{result.summary['graded_entries']:,}")
    c.metric("待确认词条", f"{result.summary['uncertain_entries']:,}")
    d.metric("默认隐藏的专有名词", f"{result.summary['proper_entries']:,}")
    st.caption("词条按词形原型、词性和等级合并；同一词的不同词性可分成多条。统计覆盖完整文件。")
    for warning in result.warnings:
        st.info(warning)
    query_col, sort_col = st.columns([3, 1])
    query = query_col.text_input("搜索单词", placeholder="输入单词或原始词形…")
    sort = sort_col.selectbox("排序", ("难度 → 词频", "词频从高到低", "字母顺序"))
    entries = result.filtered(minimum, include_uncertain, include_proper, query)
    if sort == "词频从高到低":
        entries.sort(key=lambda entry: (-entry.count, entry.lemma))
    elif sort == "字母顺序":
        entries.sort(key=lambda entry: (entry.lemma, entry.pos))
    st.caption(
        f"当前显示 {len(entries):,} 个词条。模型概率列为该词条内最低模型概率；查表结果留空。"
    )
    if entries:
        labels = ["全部"] + list(LEVELS[LEVELS.index(minimum) :]) + ["待确认"]
        subsets = (
            [entries]
            + [
                [e for e in entries if e.level == level]
                for level in LEVELS[LEVELS.index(minimum) :]
            ]
            + [[e for e in entries if e.level is None and not e.proper]]
        )
        if include_proper:
            labels.append("专有名词")
            subsets.append([e for e in entries if e.proper])
        tabs = st.tabs(labels)
        for tab, subset in zip(tabs, subsets, strict=True):
            with tab:
                st.dataframe(
                    rows(subset),
                    hide_index=True,
                    width="stretch",
                    column_config={"最低模型概率": st.column_config.NumberColumn(format="%.2f")},
                )
    else:
        st.info("当前筛选条件下没有词条，可以降低等级门槛或显示待确认词。")
    st.markdown("#### 导出词汇表")
    scope = st.radio(
        "导出范围", ("当前筛选结果", "完整结果（含初学者词和专有名词）"), horizontal=True
    )
    selected = entries if scope == "当前筛选结果" else result.entries
    prefix = Path(name).stem
    txt_col, csv_col, xlsx_col, json_col = st.columns(4)
    txt_col.download_button("下载 TXT", txt_bytes(selected), f"{prefix}.txt", "text/plain")
    csv_col.download_button("下载 CSV", csv_bytes(selected), f"{prefix}.csv", "text/csv")
    xlsx_col.download_button(
        "下载 Excel",
        xlsx_bytes(result, selected),
        f"{prefix}.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    json_col.download_button(
        "下载 JSON",
        json_bytes(result, entries if scope == "当前筛选结果" else None),
        f"{prefix}.json",
        "application/json",
    )
    st.caption("TXT 每行一个词形原型，无标题、无等级；同名单词去重，顺序与导出范围一致。")


if __name__ == "__main__":
    main()
