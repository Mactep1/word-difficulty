# 词阶 · 英文书籍与字幕词汇分级

English books and subtitles → CEFR vocabulary lists, processed locally with optional contextual model inference.

在本机上传英文书籍或字幕，提取词汇、合并屈折词形，按 CEFR A1–C2 分类。默认显示 B1–C2；未知词保留在“待确认”，每个词条保留原句、位置和频次。

支持 TXT、EPUB、SRT、VTT、DOCX、文本型 PDF、ASS/SSA。可导出逐行 TXT、CSV、分工作表的 Excel 和 JSON。

TXT 导出遵循所选导出范围，每行一个词形原型，无标题或等级，同名单词跨词性/等级去重，保留所选结果的顺序，使用 UTF-8 编码。界面中点击“下载 TXT”；命令行分析时自动生成相应的 `.txt` 文件。

## 输入与输出

| 输入格式 | 支持范围 |
| --- | --- |
| TXT | 纯文本，优先识别 UTF-8，也支持编码检测 |
| EPUB | 按正文阅读顺序提取；需要可读取、无 DRM 的电子书 |
| SRT、VTT | 清理时间轴和格式标签，保留字幕时间 |
| ASS、SSA | 清理样式和注释，保留字幕时间 |
| DOCX | 正文段落与表格 |
| PDF | 可提取文字的 PDF；扫描件需要先做 OCR |

| 输出格式 | 内容 |
| --- | --- |
| TXT | 每行一个单词原型，无标题或等级，自动去重，UTF-8 编码 |
| CSV | 单词、词形、词性、CEFR、频次、例句、出处和判定来源，兼容中文 Excel |
| XLSX | 按等级、待确认和专有名词分工作表，另有分析摘要 |
| JSON | 结构化词条、统计、处理版本及导出范围，供其他程序使用 |

TXT 示例：

```text
investigate
mechanism
hypothesis
```

## Windows 快速开始

当前已在 **Windows + Python 3.12 + CPU** 上验证。需要 [Git](https://git-scm.com/downloads) 和 [uv](https://docs.astral.sh/uv/getting-started/installation/)；uv 可自动安装所需 Python 并创建独立环境。

先在 PowerShell 中获取项目：

```powershell
git clone https://github.com/Mactep1/word-difficulty.git
cd word-difficulty
```

再执行：

```powershell
# 安装锁定依赖、英文语言模型，下载 CEFR 词表
.\setup.ps1

# 启动中文界面
.\start.ps1
```

浏览器打开 http://127.0.0.1:8501。点击“使用示例文本”可以直接体验，也可上传自己的文件。关闭应用时，在启动它的终端按 Ctrl+C。

更新代码后，如果页面提示 `cannot import name ...`，请先在启动终端按 Ctrl+C 停止服务，再运行 `.\start.ps1` 并刷新页面。仅刷新浏览器可能无法清除服务进程里缓存的旧 Python 模块。

如果系统不允许直接执行本地 PowerShell 脚本，可在终端逐条执行下面的等效命令，无需修改系统执行策略：

```powershell
uv sync --frozen --python 3.12
.\.venv\Scripts\python.exe -X utf8 -m word_difficulty setup
.\.venv\Scripts\python.exe -m streamlit run src/word_difficulty/app.py
```

基础安装无需下载大分类模型，使用 CEFR 词表分级；未匹配的词保留在待确认列表。

## 界面使用步骤

1. 上传文件，展开“文本预览”检查正文是否正常。
2. 在侧边栏选择最低等级，默认 B1，即显示 B1–C2。
3. 选择是否显示待确认词、专有名词，以及是否启用已配置的模型，点击“开始分析”。
4. 查看分级结果、频次和原句，按等级、词频或字母排序，也可以搜索单词。
5. 选择“当前筛选结果”或“完整结果”，下载需要的格式。

更改显示门槛或搜索词可以直接筛选。切换模型、运行设备或概率阈值后，需要重新点击“开始分析”。

## 启用 Hugging Face 上下文模型

```powershell
.\setup.ps1 -WithModel
```

或者执行：

```powershell
uv sync --frozen --python 3.12 --extra model
.\.venv\Scripts\python.exe -X utf8 -m word_difficulty setup --with-model
```

模型资源约 772 MB，另需 PyTorch 等推理依赖，无需 API Key。下载中断后可重试。下载完成后，界面默认启用上下文模型，也可以关闭。CPU 默认可运行；CUDA 需要与显卡匹配的 PyTorch 安装，尚未验证 GPU 环境。

以后再次执行 `uv sync` 时，如果需要保留模型依赖，请继续带上 `--extra model`。

首次配置联网下载数据；之后解析与模型推理不访问外部服务。上传文件不保存到服务器文件目录，文本解析与分析结果会在本机进程中缓存。推理缓存位于本地 SQLite；它包含用于审计的模型概率，缓存键使用上下文哈希，不保存原句。

## 命令行分析

```powershell
# 默认 B1+，保留待确认词，导出四种格式和额外的完整 JSON
.\.venv\Scripts\python.exe -X utf8 -m word_difficulty analyze examples/demo.txt -o output

# 启用上下文模型
.\.venv\Scripts\python.exe -X utf8 -m word_difficulty analyze examples/demo.srt -o output --model

# 只显示 B2+ 已评级词
.\.venv\Scripts\python.exe -X utf8 -m word_difficulty analyze examples/demo.txt --min-level B2 --exclude-uncertain
```

默认数据目录是项目下 `.data`，可以通过 `WORD_DIFFICULTY_DATA` 环境变量指定其他位置。输出保留输入扩展名，例如 `demo.txt.csv`、`demo.srt.csv`，避免不同格式同名文件互相覆盖；重复分析同一个文件仍会覆盖对应结果。

分析 `examples/demo.txt` 后，输出目录包含：

```text
output/
  demo.txt.txt
  demo.txt.csv
  demo.txt.xlsx
  demo.txt.json
  demo.txt.complete.json
```

最后一个文件始终保留全部结果，其他文件遵循命令行筛选条件。自己的文件路径含空格时，请加引号，例如 `analyze "C:\Books\My Book.epub" -o output`。

| 参数 | 默认值 | 作用 |
| --- | --- | --- |
| `--output` / `-o` | `output` | 输出目录 |
| `--min-level` | `B1` | 最低等级，可选 A1–C2 |
| `--model` | 关闭 | 启用已下载的上下文模型 |
| `--min-confidence` | `0.6` | 低于此模型概率时进入待确认 |
| `--include-proper` | 关闭 | 包含专有名词 |
| `--exclude-uncertain` | 关闭 | 不导出待确认词 |
| `--batch-size` | `16` | 模型推理批量大小 |
| `--device` | `cpu` | 运行设备，可选 cpu、cuda |

## macOS / Linux

对应命令如下，尚未在这两个系统完成验证：

```bash
git clone https://github.com/Mactep1/word-difficulty.git
cd word-difficulty
uv sync --frozen --python 3.12
.venv/bin/python -m word_difficulty setup
.venv/bin/python -m streamlit run src/word_difficulty/app.py
```

配置模型时，安装命令增加 `--extra model`，配置命令增加 `--with-model`。命令行分析同样把 Windows 的 Python 路径替换成 `.venv/bin/python`。

## 分级与词频规则

- 使用 spaCy 英文语言模型提取 lemma 和词性，查询 `w3nabil/english-cefr-wordlist`。
- 查询不到或出现多等级匹配时，使用 `star092304/cefr-level-deberta-v3-base`。模型输入与训练一致，是“原句 + 目标词”；长句截取保留目标词的窗口。
- 未配置模型、推理失败或概率低于阈值时，词语保留为“待确认”；不会静默删掉。
- 模型概率阈值默认 0.60，是待校准的产品设置，不能解释为真实准确率。
- 按 lemma + 词性 + 等级聚合。例如 `investigate` 和 `investigated` 可合并；不同词性或不同预测等级分开统计。每条最多展示三个代表出处，全部出现次数都计入词频。
- 词表覆盖的词直接查表，不会逐一用模型重新消歧。词表保留较高等级的构建规则可能高估简单词义；分级仍需结合原句判断。
- 专有名词默认隐藏，完整结果可以查看。语言模型可能把罕见词误标为专名，请检查专有名词列表。
- 字幕按出现顺序分析，合并相邻未完成句子；相同且连续重叠的字幕去重，较晚重复出现的同一句仍计数。复杂滚动字幕和多说话人片段可能需要预清洗。

当前重点是单词，尚未进行习语、短语动词和多词表达识别。带重音字母的借词、复杂连字符词、混合语言文本可能影响提取。扫描 PDF 需要先 OCR；DRM 书籍需要先提供可读取的正文。PDF 的分栏和页眉页脚请在预览里检查。

文件大小上限为 100 MB。服务默认仅绑定本机 `127.0.0.1`；源文件、模型、完整词表、分析结果、虚拟环境和本地缓存不包含在 Git 提交中。

## 常见问题

| 问题 | 处理方式 |
| --- | --- |
| 缺少词表 | 执行上文配置命令 `python -m word_difficulty setup`，使用虚拟环境 Python 路径 |
| 缺少英文语言模型 | 重新执行安装命令；英文模型已列入依赖 |
| 缺少分类模型或依赖 | 按“启用 Hugging Face 上下文模型”一节安装 |
| 下载超时 | 检查对 Hugging Face 的访问，重新执行配置命令；也可以先使用词表模式 |
| 页面报 `cannot import name ...` | 停止旧服务，重新启动并刷新页面 |
| 页面打不开 | 确认启动终端没有关闭，并访问 `http://127.0.0.1:8501` |
| PDF 没有正文 | 扫描件先 OCR；加密文件先移除密码 |

## 开发与验证

```powershell
uv sync --frozen --python 3.12 --extra dev --extra model
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests scripts
```

服务运行时，可额外检查真实页面是否能执行，避免只有健康接口正常而页面报错：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/check_live_app.py
```

该检查通过本机 WebSocket 建立新的应用会话；页面出现脚本异常会返回失败，不读取已有用户会话中的上传文件。

测试覆盖词形合并、等级门槛、未知词保留、专名显示、模型失败恢复、缓存版本与上下文隔离，以及多格式解析、导出和 Streamlit 示例操作。有本地模型及推理依赖时额外运行两项真实模型测试；未配置时自动跳过。功能测试不能代替教学难度的人工评估，当前没有经过人工标注的小说/非虚构/字幕准确率基准。

## 数据与模型来源

- [CEFR 词表](https://huggingface.co/datasets/w3nabil/english-cefr-wordlist)，固定版本 `e25277c3caf04b938de7b99f191ec86ed92abbcc`。其原始来源为 Tono Laboratory 的 CEFR-J Vocabulary Profile 1.5 与 Octanove Labs 的 Vocabulary Profile C1/C2 1.0。下载时保存上游数据说明。
- [上下文 CEFR 模型](https://huggingface.co/star092304/cefr-level-deberta-v3-base)，固定版本 `895fabc45879f4ce6dd435b11e1bbc39fd9ee4b5`，模型卡声明 MIT。
- [spaCy 英文语言模型](https://spacy.io/models/en#en_core_web_sm)，固定为 `en_core_web_sm 3.8.0`，MIT。

词表元数据标注 MIT，但不代表上游归属与再分发条件已经全部解决；发布包含数据的产品前需复核。软件只在首次配置时下载词表与模型，源码中不附带权重或完整词表。

[开发计划](docs/implementation-plan.md) · [模型调研](docs/huggingface-word-difficulty-research.md) · [开发状态](docs/development-status.md)
