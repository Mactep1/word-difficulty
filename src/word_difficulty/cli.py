import argparse
import json
import sys
from pathlib import Path

from .models import LEVELS


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="英文书籍与字幕 → CEFR 分级词汇表")
    subparsers = parser.add_subparsers(dest="command", required=True)
    setup = subparsers.add_parser("setup", help="下载词表，可选下载本地上下文模型")
    setup.add_argument("--with-model", action="store_true")
    analyze = subparsers.add_parser("analyze", help="分析文件并导出 TXT、CSV、XLSX 和 JSON")
    analyze.add_argument("input", type=Path)
    analyze.add_argument("--output", "-o", type=Path, default=Path("output"))
    analyze.add_argument("--min-level", choices=LEVELS, default="B1")
    analyze.add_argument("--include-proper", action="store_true")
    analyze.add_argument("--exclude-uncertain", action="store_true")
    analyze.add_argument("--model", action="store_true", help="启用已下载的上下文模型")
    analyze.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    analyze.add_argument("--min-confidence", type=float, default=0.6)
    analyze.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args(argv)
    try:
        from .paths import data_dir

        root = data_dir()
        if args.command == "setup":
            from .setup_data import setup_data

            metadata = setup_data(root, args.with_model)
            print(json.dumps(metadata, ensure_ascii=False, indent=2))
            return 0
        from .cache import PredictionCache
        from .classifier import ContextClassifier
        from .export import csv_bytes, json_bytes, txt_bytes, xlsx_bytes
        from .lexicon import Lexicon
        from .nlp import EnglishAnalyzer
        from .parsers import parse_document
        from .pipeline import analyze as run_analysis

        document = parse_document(args.input.name, args.input.read_bytes())
        classifier = ContextClassifier(root / "model", args.device) if args.model else None
        analysis = run_analysis(
            document,
            EnglishAnalyzer(),
            Lexicon(root / "words.csv"),
            classifier,
            PredictionCache(root / "predictions.sqlite3") if classifier else None,
            args.min_confidence,
            args.batch_size,
            progress=lambda fraction, message: print(message, file=sys.stderr, flush=True),
        )
        entries = analysis.filtered(args.min_level, not args.exclude_uncertain, args.include_proper)
        args.output.mkdir(parents=True, exist_ok=True)
        # Keep source format in output names so book.txt and book.srt do not collide.
        stem = args.input.name
        (args.output / f"{stem}.txt").write_bytes(txt_bytes(entries))
        (args.output / f"{stem}.csv").write_bytes(csv_bytes(entries))
        (args.output / f"{stem}.xlsx").write_bytes(xlsx_bytes(analysis, entries))
        (args.output / f"{stem}.json").write_bytes(json_bytes(analysis, entries))
        (args.output / f"{stem}.complete.json").write_bytes(json_bytes(analysis))
        print(json.dumps(analysis.summary, ensure_ascii=False, indent=2))
        for warning in analysis.warnings:
            print(f"提示：{warning}", file=sys.stderr)
        print(f"已导出 {len(entries)} 个词条到 {args.output.resolve()}")
        return 0
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
