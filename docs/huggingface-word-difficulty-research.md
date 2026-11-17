# Hugging Face resources for English word-level CEFR difficulty

_Researched 2026-11-17. Sources are limited to Hugging Face model/dataset cards and files, official project pages, and the authors' paper._

## Executive conclusion

**A directly loadable English target-word CEFR classifier does exist:** [`star092304/cefr-level-deberta-v3-base`](https://huggingface.co/star092304/cefr-level-deberta-v3-base). It returns one of `A1`, `A2`, `B1`, `B2`, `C1`, or `C2` for a target word. It is a standard Transformers `DebertaV2ForSequenceClassification` checkpoint, MIT-licensed, and can run locally from its safetensors files.

It is not a token-classification model that labels every token in a book in one pass. The application must identify words first and invoke the classifier for each target (preferably batched and cached). More importantly, the repository's training notebook uses **two input segments—`tokenizer(sentence, target_word)`—even though the model card demonstrates a bare word**. The contextual pair is the only interface matching training. The model card also leaves its performance sections empty. Treat this checkpoint as a useful fallback requiring local evaluation, not established ground truth ([model card](https://huggingface.co/star092304/cefr-level-deberta-v3-base), [training notebook](https://huggingface.co/star092304/cefr-level-deberta-v3-base/blob/main/src/cefr-level-deberta-v3-base-v1.ipynb)).

For an MVP, use a **lookup-first hybrid**:

1. tokenize and sentence-split books/subtitles, normalize case, lemmatize, and retain part of speech and original surface forms;
2. look up lemma + POS in [`w3nabil/english-cefr-wordlist`](https://huggingface.co/datasets/w3nabil/english-cefr-wordlist), which has 9,984 compact A1–C2 entries;
3. use the contextual DeBERTa pair classifier for missing or ambiguous items;
4. exclude the configured learner-known band (recommended default: exclude A1 and A2, so “non-beginner” means B1+), then group by predicted CEFR level and retain provenance, confidence, count, and example sentence.

This is faster and more interpretable than running a 738 MB neural model for every occurrence. It also follows the authors' own finding that a lexical knowledge base plus a contextual classifier was more accurate and efficient than a classifier alone ([paper, §5.2–5.3](https://arxiv.org/html/2510.18466v2)).

## Candidate comparison

| Resource | Actual unit and output | Language / coverage | License | Local deployment and dependencies | Fit for this product |
|---|---|---|---|---|---|
| [`star092304/cefr-level-deberta-v3-base`](https://huggingface.co/star092304/cefr-level-deberta-v3-base) | Target word in context → six-class logits / `A1`–`C2`. Correct trained input is `(sentence, target_word)`, not the card's bare word. | English; single-word lexical items | MIT | Standard PyTorch + Transformers; DeBERTa tokenizer assets; 184.4M parameters in the notebook, 738 MB F32 weights / 772 MB repository. CPU-capable but GPU is preferable for bulk analysis. No HF Inference Provider. | **Best neural fallback.** Directly usable, but not one-pass token labeling and not adequately validated for unseen book/subtitle vocabulary. |
| [`AbdulSami/bert-base-cased-cefr`](https://huggingface.co/AbdulSami/bert-base-cased-cefr) | Isolated word/text → six-class logits / `A1`–`C2` | English; trained from an approximately 19k-row word/POS dataset | Apache-2.0 | Standard BERT sequence classifier with Transformers + PyTorch; local checkpoint, no HF Inference Provider. | Directly usable isolated-word alternative, but weaker provenance and reporting: its training dataset card is effectively empty, reported metrics vary across card revisions, and config says `multi_label_classification` despite six-way single-label data. Not recommended over the contextual model. |
| [`w3nabil/english-cefr-wordlist`](https://huggingface.co/datasets/w3nabil/english-cefr-wordlist) | `word` + POS → `A1`–`C2` lookup | English; 9,984 rows; headwords only | HF card says MIT; upstream resources impose attribution/use terms (see licensing note below) | ~956 KB; JSONL/CSV via `datasets` or pandas, or bundle a local map. Requires the application to lemmatize and POS-tag. | **Best MVP primary path.** Fast, deterministic, inspectable; limited OOV and sense handling. |
| [`star092304/CEFR-Annotated-WordNet`](https://huggingface.co/datasets/star092304/CEFR-Annotated-WordNet) | WordNet sense key → CEFR; or `(sentence, target_word, lemma)` training rows → label | English; 10,644 annotated WordNet senses / 5,645 lemmas and 116,294 SemCor instances in the paper | CEFR annotations CC BY 4.0 plus WordNet and SemCor licenses | ~115 MB dataset; TSV/CSV/JSONL via pandas/`datasets`. Direct lookup needs WordNet sense disambiguation. | Best retraining/evaluation resource and possible sense-aware lookup; too complex as the first MVP lookup. |
| [`cstr/grundwortschatz-voc-en`](https://huggingface.co/datasets/cstr/grundwortschatz-voc-en) | Lemma record → CEFR metadata, grade estimate, frequency and enrichment | English; 11,539 lemmas, but CEFR-J level only for 6,879 entries and only A1–B2 | CC BY-SA 4.0 | Parquet/SQLite; pandas or DuckDB. Offline-friendly. | Strong secondary enrichment/frequency signal; insufficient as the sole six-level classifier. |
| [`Fristail27/vocab-bloom-hub-en`](https://huggingface.co/datasets/Fristail27/vocab-bloom-hub-en) | Word/POS and sense records → CEFR, inflections, definitions, translations | English headwords plus seven translation languages; 88,783 word entries, 211,808 inflected forms, 161,343 senses | CC BY 4.0 plus a required visible AI-generated-content notice | JSONL/`datasets`; about 1 GB for the whole revision, while individual subsets can be loaded. | Broad fallback/enrichment, but **not difficulty ground truth**: all content is model-generated and unreviewed, with no frequency evidence. |
| [`dksysd/cefr-classifier`](https://huggingface.co/dksysd/cefr-classifier) | Whole text → `A1`–`C2` | English text/passages | CC BY-NC-SA 4.0 | Standard Transformers; DeBERTa-v3-large, 0.4B parameters, 1.74 GB weights; no HF Inference Provider. | Wrong granularity, large, non-commercial restriction. A one-word input would be outside its documented task. |
| [`SNALYF/CEFR_Bert_Fine-tuned`](https://huggingface.co/SNALYF/CEFR_Bert_Fine-tuned) | Short passage → continuous `1.0`–`6.0`, optionally rounded to CEFR | English short passages | Apache-2.0 | 45.7M parameters, but custom `modeling.py` must be downloaded and executed; PyTorch + Transformers. | Lightweight passage baseline, not a word classifier. Exact rounded accuracy on its 445-row test split is only 51.5%. |
| [`UniversalCEFR/cefr_sp_en`](https://huggingface.co/datasets/UniversalCEFR/cefr_sp_en) | Sentence text + sentence-level CEFR label | English; 10,004 rows | CC BY-NC-SA 4.0 | JSON via `datasets`/pandas | Useful only for sentence-difficulty training/evaluation; cannot supervise which individual word is difficult. |

## Direct classifier: verified contract and caveats

### Input and output

The checkpoint configuration maps IDs exactly as `0:A1`, `1:A2`, `2:B1`, `3:B2`, `4:C1`, and `5:C2`, with the inverse mapping also embedded in `config.json` ([configuration](https://huggingface.co/star092304/cefr-level-deberta-v3-base/blob/main/config.json)). It is a six-way **sequence classifier**, not a token classifier.

Although the card tokenizes only `word = "investigation"`, the repository notebook constructs examples from `sentence` and `target_word` and tokenizes them as a pair, with `max_length=256` ([model card usage](https://huggingface.co/star092304/cefr-level-deberta-v3-base#usage), [training notebook](https://huggingface.co/star092304/cefr-level-deberta-v3-base/blob/main/src/cefr-level-deberta-v3-base-v1.ipynb)). Production inference should therefore mirror training:

```python
encoded = tokenizer(
    sentences,
    target_words,
    padding=True,
    truncation="only_first",
    max_length=256,
    return_tensors="pt",
)
logits = model(**encoded).logits
probabilities = logits.softmax(dim=-1)
levels = [model.config.id2label[i.item()] for i in probabilities.argmax(-1)]
```

The book/subtitle parser must retain the target surface form and its containing sentence. Sending an entire sentence alone asks for sentence difficulty; sending only the word discards the context the model saw during training.

### License, language, and local operation

The model card declares English and MIT, identifies `microsoft/deberta-v3-base` as the base model, and provides standard `AutoTokenizer` / `AutoModelForSequenceClassification` loading code ([card metadata and usage](https://huggingface.co/star092304/cefr-level-deberta-v3-base/blob/main/README.md)). The repository contains `model.safetensors` (738 MB), tokenizer files, and config files; its total is about 772 MB ([files](https://huggingface.co/star092304/cefr-level-deberta-v3-base/tree/main)). This makes it fully local and offline after download. Required model-inference packages are PyTorch and Transformers; `accelerate` is needed only for the card's `device_map="auto"` route, while the notebook also uses NLTK for preprocessing. The training notebook installed `transformers==4.53.3`, `datasets==4.0.0`, `accelerate==1.10.1`, `scikit-learn==1.7.1`, and `nltk==3.9.1`; inference does not require the training-only packages if parsing is supplied elsewhere. No standalone requirements lockfile is published, so pin and test the application's chosen versions. DeBERTa's tokenizer is backed by the included SentencePiece vocabulary/tokenizer assets ([official Transformers DeBERTa documentation](https://huggingface.co/docs/transformers/model_doc/deberta-v2)).

The Hub states that no hosted Inference Provider serves this model, so deployment is self-hosted unless another service is arranged ([model page](https://huggingface.co/star092304/cefr-level-deberta-v3-base)).

### Evaluation and generalization risk

The notebook reports a 11,392-item test set, accuracy `0.9310`, and macro-F1 `0.9149`. However, it makes a random stratified 80/10/10 split over **instances**, not a grouped split by lemma or WordNet sense. Repeated uses of a lemma/sense can therefore appear in both train and test. Those numbers measure same-corpus random-split performance and may substantially overstate generalization to unseen vocabulary, senses, literary prose, dialogue, OCR errors, and subtitle fragments ([training notebook](https://huggingface.co/star092304/cefr-level-deberta-v3-base/blob/main/src/cefr-level-deberta-v3-base-v1.ipynb)).

Do not confuse that checkpoint result with the paper's best reported macro-F1 of `0.81`. The paper evaluated different contextual systems on an EVP-based test and obtained `0.81` from a fine-tuned GPT-4.1-mini plus a knowledge base; its fine-tuned model trained only on SemCor-CEFR had lower performance. The paper also warns that same-source EVP results can reflect dataset-specific cues and reports only moderate cross-domain correlation with CompLex 2.0 ([paper results and transfer analysis](https://arxiv.org/html/2510.18466v2)).

## Dataset findings

### `w3nabil/english-cefr-wordlist`

The dataset has one `train` split with 9,984 entries. JSONL rows contain `value.word`, `value.type`, and `value.level`; the parallel CSV uses `word`, `type`, and `CEFR`. Levels cover A1–C2 and the same spelling can have different levels by POS—for example, the viewer shows `address` as A1 noun and B1 verb ([card and viewer](https://huggingface.co/datasets/w3nabil/english-cefr-wordlist)).

Its limitations are explicit:

- it stores headwords, not arbitrary inflections, so the application needs lemmatization;
- where duplicate word/POS entries existed, construction retained the **highest** CEFR level, which can overestimate easier senses;
- case variants can survive as separate entries;
- it has no sentence context or sense ID.

The HF metadata declares MIT, but the dataset is derived from CEFR-J and the Octanove C1/C2 profile. The official CEFR-J page says its wordlist copyright belongs to Tono Laboratory, allows research and commercial use with proper acknowledgement, and includes additional disclaimer/use language ([official CEFR-J download page](https://cefr-j.org/download_eng)). The HF card does not document how its blanket MIT declaration interacts with both upstream sources. **Preserve upstream attribution and resolve redistribution terms before shipping the data in a commercial product; do not rely on the HF metadata alone.** This does not prevent prototyping or local evaluation, but it is a release checklist item.

### `CEFR-Annotated-WordNet`

The useful artifacts are:

- `wordnet_sensekey_cefr.tsv`: WordNet sense key → one or occasionally several CEFR levels;
- `semcor_instance_cefr.tsv`: SemCor instance → CEFR;
- `semcor_mapped.csv`: `instance_id`, full `sentence`, `target_word`, `lemma`, and `cefr_level` for contextual classification;
- chat-format train/validation JSONL for LLM tuning ([dataset card](https://huggingface.co/datasets/star092304/CEFR-Annotated-WordNet)).

The paper is more precise than the card's claim of “complete WordNet 3.0 sense coverage”: it reports 10,644 annotated WordNet senses across 5,645 lemmas, created by GPT-4o gloss alignment against EVP, plus 116,294 labeled SemCor instances. No manual expert spot-check of the transferred labels was performed. About 3.16% of annotated sense keys have two or three labels because WordNet and EVP sense granularity differs ([paper methodology, coverage, and limitations](https://arxiv.org/html/2510.18466v2)).

Licensing is composite: novel CEFR labels and splits are CC BY 4.0, while WordNet identifiers and SemCor text retain their respective Princeton licenses; the repository requires compliance with all three and attribution ([dataset license section](https://huggingface.co/datasets/star092304/CEFR-Annotated-WordNet#licenses)).

### Enrichment alternatives

[`cstr/grundwortschatz-voc-en`](https://huggingface.co/datasets/cstr/grundwortschatz-voc-en) is valuable for frequency-aware ranking after CEFR assignment: it exposes Zipf/per-million frequency, inflections, CEFR-J A1–B2 data, and curriculum metadata. Its card states 11,539 lemmas but only 6,879 CEFR-tagged entries and no C1/C2; the effective license is CC BY-SA 4.0. It should augment—not replace—the six-level source.

[`Fristail27/vocab-bloom-hub-en`](https://huggingface.co/datasets/Fristail27/vocab-bloom-hub-en) offers unusually broad coverage and explicit inflected forms, but the card states that all definitions, examples, CEFR levels, translations, and links are AI-generated and unreviewed; the levels are model judgments, not corpus-derived, and content shown to users must be visibly identified as AI-generated. This makes it unsuitable as authoritative difficulty truth, though it may help with coverage experiments.

## Recommended MVP design

### Pipeline

1. **Ingest** EPUB/plain text/SRT/VTT. Preserve sentence/subtitle boundaries; remove timestamps, markup, and speaker labels without losing the original sentence.
2. **Analyze words** using an English tokenizer, lemmatizer, and POS tagger. Reject punctuation, numbers, URLs, obvious proper names, and non-English tokens. Preserve contractions and phrasal/multi-word expressions for a later phase; the chosen model was trained on single-word items only ([model training-data construction](https://huggingface.co/star092304/cefr-level-deberta-v3-base#training-data-construction)).
3. **Cache a deterministic lookup** keyed by normalized lemma + coarse POS from `w3nabil`. When POS is unavailable, return all matching levels and mark the result ambiguous rather than silently choosing one.
4. **Classify fallback items contextually** in batches using `(containing_sentence, target_surface_or_lemma)`. Cache by normalized sentence hash + target span (or, as a cheaper approximation, lemma + short context hash). Keep all six probabilities and the chosen label.
5. **Apply a learner threshold.** “Non-beginner” is a product rule, not a model output. Recommended default is B1–C2, with a user setting such as “show above A2/B1/B2.”
6. **Aggregate for output** by lemma and assigned level. Include surface forms, POS, frequency/count, one or more example occurrences, confidence, and provenance (`wordlist`, `model`, or `ambiguous`). Sort by CEFR, then corpus frequency or first occurrence.
7. **Use confidence defensively.** Send low-margin predictions and lookup/model disagreements to an `uncertain` bucket instead of presenting false precision. Calibrate thresholds on a small manually reviewed sample from representative books and subtitle genres.

### Why this MVP

- Most common vocabulary is answered in constant time with explainable source data.
- Neural cost is limited to OOV/ambiguous unique items rather than every occurrence.
- Context is retained for polysemy, which both the model card and underlying paper identify as a core limitation of bare word ratings.
- Provenance makes model regressions and licensing boundaries auditable.
- The system can later replace either component without changing the parser or output contract.

### Minimum acceptance test before release

Create a manually reviewed, lemma-disjoint evaluation set drawn from at least one novel, one nonfiction book, and conversational subtitles. Measure macro-F1 and adjacent-level accuracy, plus precision/recall for the actual displayed set (for example B1+). Include inflections, POS ambiguity, proper names, compounds, phrasal verbs, archaic/literary vocabulary, slang, OCR noise, and sentence fragments. Compare wordlist-only, model-only, and hybrid results. The published random-instance checkpoint score is not a substitute for this test.

## Decision

Use `w3nabil/english-cefr-wordlist` as the MVP's fast primary lookup and `star092304/cefr-level-deberta-v3-base` as a **context-pair** fallback. Record a release blocker for upstream wordlist licensing/attribution review and a quality blocker for lemma-disjoint, domain-specific evaluation. Do not use whole-text CEFR classifiers to assign word levels, and do not present model confidence as a pedagogical certainty.
