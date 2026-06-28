# AGENTS.md

## 文档语言

项目内面向人阅读的文档默认使用中文，包括：

- `docs/**/*.md`
- `codex/**/*.md`
- 路线图、计划、规格、runbook、研究笔记、总结说明

专业术语可以保留英文原词，但要在旁边加一句短解释，避免只堆砌术语。例如：

- OOS（out-of-sample，样本外检验）
- walk-forward（滚动前推验证）
- RankIC（因子排序和未来收益排序的相关性）
- registry（注册表，用来追踪通过验收的候选因子）
- lineage（来源链路，记录因子来自哪些候选和运行结果）

写文档时优先解释“它解决什么问题、为什么现在要做、验收标准是什么”，不要只罗列名词。

## 代码风格入口

改动项目代码前，先阅读 `docs/architecture/factor-autoresearch-code-style.md`，并把以下内容作为验收项。适用范围包括 `factor_autoresearch/**/*.py`、`scripts/**/*.py`、`tests/**/*.py` 等所有 Python 代码，不只限于计算链路：

- 模块开头有中文职责说明，说明负责什么、不负责什么。
- 复杂模块用 `# ============== 分区名称 ==============` 做分区。
- 新增函数、类、公共方法使用短中文 docstring，说明用途。
- 风格整理不改变公开函数签名和计算行为。

## Plan 执行前立项规则

当按照 `docs/**/plans/*.md`、roadmap、区块计划或较大的工程任务执行时，动手前先对齐一张任务卡：

- 目标：
- 工作目录 / 分支：
- 本轮要不要 commit：
- 验收命令：
- 哪些文件不能碰：
- 完成后给用户什么结论：

若信息能从上下文和仓库状态判断，agent 应主动补齐；只有存在高风险歧义时才向用户确认。任务卡用于减少跑错 worktree、漏验收、误提交运行产物或最后结论不清楚的问题，不是要求用户每次手动填写。

## 验证护栏

改动代码后，按影响范围选择验证命令，不只依赖肉眼检查：

- 普通 Python 代码改动：至少运行相关 `pytest` 用例和 `ruff check`。
- 改动 `factor_autoresearch/compute_v1/**`、`factor_autoresearch/evaluate.py` 或 compute v1 测试时，必须运行 `python scripts/run_compute_v1_guardrails.py`。
- 改动 compute engine 核心计算、预处理、指标或并发路径时，还要运行 compute v1 定向测试套件。
- guardrails（护栏测试，用来防止关键行为回归）已接入 `.github/workflows/compute-v1-guardrails.yml`，本地脚本入口是 `scripts/run_compute_v1_guardrails.py`。

## Worktree 合并收口规则

多 worktree / 多分支任务收口时，先确认最终版本已进入目标分支。

- 合并或同步前，检查是否还有相关未合并分支，例如 `git branch --no-merged main`。
- 同步 `main` 到其他 worktree 前，确认功能、风格整理、文档规则和验证护栏都已进入 `main`。
- `AGENTS.md`、验证脚本、风格文档冲突时按完整并集合并，不能只取一边。
- 如发现相关分支未合并，先停下说明风险，不继续同步下游 worktree。

## 数据与样本规则

涉及数据与样本协议时，先看治理文档，并补充方便人复核的说明。

- 新 dataset profile、`source_universe_key`、sample protocol、forward return 定义
- dataset / run manifest 追溯字段变化
- `data quality report` 出现结构性 `warning` 或 `fail`

参考文档：`docs/governance/block2-data-sample-protocol-governance.md`

## 数据来源审查规则

`source pipeline review` 是数据来源审查材料，不是每次 run 都重写的日志。

- 新数据来源、dataset profile、上游 pipeline / 过滤逻辑变化时，检查是否需要更新 `docs/data/source-pipeline-review-*.md`。
- 只记录触发条件、异常和未确认项；不要代替人做最终业务判断。

参考文档：`docs/governance/source-pipeline-review-governance.md`

## 命名约定

文件名和代码标识可以继续使用英文，保证路径稳定、工具友好。

正文内容默认中文；确有行业通用英文术语时，第一次出现时补中文解释。
