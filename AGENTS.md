# AGENTS.md

## 称呼

每轮对话从 `[夏董，羊羊，羊仔，肠娃]` 中随机选一个称呼用户；同一轮固定一个称呼即可。

## 沟通风格

沟通时，遵守系统级长期表达习惯：优先使用外行也能看懂的短句、分块排版和清晰扫读结构。

解释管理、系统、流程等抽象内容时，可以使用少量有逻辑提示作用的 emoji 作为标题标签，例如：

- 📌 结论
- 🧩 拆解
- ⚠️ 风险
- 🔧 要补
- 📊 进度
- 👀 待拍板

列点处也应使用轻量符号或小 emoji 帮助扫读，例如：

- ✅ 已有
- ➡️ 下一步
- 普通列点
- `1. 2. 3.` 顺序事项

emoji 和符号服务逻辑，不做满屏装饰；重点是让用户不费脑子看懂结构、判断、风险和下一步。

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

## 区块二协议规则

区块二主要是数据与样本协议的整理层。

agent 遇到以下任务时，先检查：

- 是否需要看 `docs/governance/block2-data-sample-protocol-governance.md`
- 是否需要补文档，方便人复核，而不是只改代码

典型触发场景：

- 新 dataset profile
- 新 `source_universe_key`
- `sample protocol` 改动
- `forward return` 定义改动
- `data quality report` 出现结构性 `warning` 或 `fail`
- dataset / run manifest 追溯字段改动

普通小型开发任务如果不碰这些对象，不需要展开阅读全部规则。

## Source Pipeline Review 规则

`source pipeline review` 主要是给人看的数据来源审查材料，不是每次 run 都写的新日志。

agent 遇到以下场景时，检查是否需要更新 `docs/data/source-pipeline-review-*.md`：

- 新 `source_universe_key`
- 新 dataset profile
- 新 `industry_source`
- 上游 pipeline 或基础过滤逻辑变化
- 本仓 `prepare` / `forward return` / manifest 逻辑变化
- `data quality report` 出现结构性 `warning` 或 `fail`
- `mining_v1` 或其他严肃协议上线前

agent 负责：

- 发现触发条件
- 起草或更新 review 文档
- 把异常和未确认项写清楚，方便人复核

agent 不负责：

- 为每次普通 run 自动重写 review
- 未经确认把风险写成已关闭
- 代替人做最终业务判断

正式制度文档见：

- `docs/governance/source-pipeline-review-governance.md`
- `docs/governance/block2-data-sample-protocol-governance.md`

## 命名约定

文件名和代码标识可以继续使用英文，保证路径稳定、工具友好。

正文内容默认中文；确有行业通用英文术语时，第一次出现时补中文解释。
