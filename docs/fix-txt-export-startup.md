# TXT 导出更新后的页面导入错误

日期：2026-11-17

## 复现

用户报告页面打不开。HTTP 页面和健康接口仍返回 200，但应用日志记录：

```text
ImportError: cannot import name 'txt_bytes' from 'word_difficulty.export'
```

新建 Python 进程可以从同一源码路径导入 `txt_bytes`，排除了函数未保存和模块路径错误。故障发生在长时间运行的 Streamlit 服务：页面入口已引用新函数，进程中导出模块仍是更新前的版本。

新增 `scripts/check_live_app.py`，通过运行中的服务创建新会话并检查脚本异常。修复前实际输出：

```text
FAIL: ImportError: cannot import name 'txt_bytes' from 'word_difficulty.export' (.../export.py)
```

## 处理

重启该项目的 Streamlit 服务，重新加载更新后的 Python 模块。不修改导出逻辑，也不加入强制 reload 之类的运行时代码。

README 增加更新后的重启方式及真实服务检查命令。今后新增模块接口后，需要在运行中的服务上完成此检查，不能只依赖新进程测试或健康接口。

重启后运行同一检查，实际输出 `PASS: live app rendered without script exceptions`；源码、测试及检查脚本的静态检查通过。
