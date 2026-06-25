# 区块二数据与样本协议说明

日期：2026-06-24

## 1. 这份文档是干嘛的

这份文档不是为了把区块二做成复杂治理系统。

它主要是为了讲清楚：

- 这套系统到底认哪份数据
- 数据来源怎么复核
- 样本时间窗口怎么固定
- 数据质量怎么判断能不能进入严肃研究
- 后续 run 应该记录哪些关键信息，才能追溯回来

如果没有这份说明，最容易出现：

- 不同 run 悄悄用了不同口径
- sample protocol 被顺手改动，历史结果却无法比较
- data quality 的 `warning` / `fail` 只有代码，没有维护规则
- agent 知道要改功能，但不知道是否顺手改到了规则

## 2. 当前定位

区块二当前更适合被理解成一层轻量审查辅助。

它负责：

- 把数据来源整理清楚
- 把样本切片整理清楚
- 把质量异常暴露出来
- 把追溯字段留好

它不是：

- agent 全权判断的数据治理系统
- 每次 run 都要重写的一份日志
- 给所有任务都强制阅读的长说明

## 3. 最小文档结构

区块二先保持最小结构，不要一开始拆很多文档。

当前建议保留 4 层：

- `AGENTS.md`
  - 入口短规则
- `docs/governance/block2-data-sample-protocol-governance.md`
  - 区块二总治理规则
- `docs/governance/source-pipeline-review-governance.md`
  - source review 专项规则
- `docs/data/source-pipeline-review-*.md`
  - 当前事实审查记录

这套结构的目标是：

- 入口简单
- 规则清楚
- 需要时再展开看细节

## 4. 区块二里哪些对象需要重点维护

### 4.1 现在就需要治理

下面 4 个对象，已经足够重要，不能只靠代码自然生长。

- `source pipeline review`
  - 负责回答数据从哪里来、哪些过滤在上游做、还有哪些 PIT 风险
- `sample protocol`
  - 负责固定 formation / validation / OOS / walk-forward 的时间切片
- `data quality policy`
  - 负责定义什么属于 `fail`，什么属于 `warning`
- `dataset manifest contract`
  - 负责固定 dataset 必须记录哪些来源、口径和追溯字段

### 4.2 B 线再正式处理

下面这些对象也重要，但可以等 B 线集成时再正式单列规则。

- `run manifest integration`
- `metrics by slice` 输出结构
- `diagnostics by slice` 输出结构
- gate 如何消费 sample slices

## 5. agent 和人怎么分工

### 5.1 人负责什么

人负责：

- 判断当前协议是否过期
- 判断这次改动是否触发治理更新
- 审核 agent 起草的文档
- 决定哪些判断进入正式口径

### 5.2 agent 负责什么

agent 负责：

- 发现这次任务是否碰到了区块二协议对象
- 起草或更新对应文档
- 把风险和未确认项显式写出来
- 把材料整理到方便人复核的程度

agent 不负责：

- 未经确认把临时判断写成正式口径
- 为每次普通 run 重写治理文档
- 接管最终业务判断

## 6. 什么时候要看这份文档

不是每个任务都要读完整治理文档。

建议按下面的阅读路径执行：

### 6.1 每次进入仓库

先看 `AGENTS.md`。

它只负责提醒：

- 区块二是协议层
- 遇到哪些任务要继续看治理文档
- 哪些事情不能临时乱改

### 6.2 任务碰到区块二协议时

再看本文件。

典型触发场景：

- 新 dataset profile
- 新 `source_universe_key`
- sample protocol 改动
- forward return 定义改动
- data quality 出现结构性 `warning` / `fail`
- manifest 追溯字段改动

### 6.3 任务碰到 source review 专项时

再看：

- `docs/governance/source-pipeline-review-governance.md`

也就是说：

- `AGENTS.md` 是进门提醒
- 本文件是区块二总规则
- source governance 是专项细则

## 7. 这四类对象什么时候值得特别留意

### 7.1 source pipeline review

触发例子：

- 新 universe
- 上游 pipeline 变化
- prepare / manifest / forward return 逻辑变化
- data quality 暴露出来源异常

专项规则见：

- `docs/governance/source-pipeline-review-governance.md`

### 7.2 sample protocol

触发例子：

- 新 `sample_protocol_id`
- `mining_v1` 窗口改动
- OOS / walk-forward 日期切片改动
- 新 forward return 口径进入协议

现在先守住这几条：

- 具体窗口必须写进配置或协议
- 不能由 candidate 或单次 run 临时覆盖
- 同一 dataset + 同一 protocol 要生成稳定 hash

#### `mining_v1_mainboard_walkforward`

`sample protocol`（样本协议，用来固定正式评分窗口、滚动切片和最终样本外边界）在主板正式版里先按下面这套口径执行：

- 正式评分窗口：`2014-01-01` 到 `2026-05-31`
- 预热期：`2013-01-01` 起，只用于长窗口因子计算
- 股票范围：沪深主板
- 股票池来源：`source_universe_key = "univ_trade_mainboard"`
- 主评估方式：5 年 formation（形成期） + 20 个交易日 embargo（隔离带，防止未来收益泄漏） + 1 年 test（测试期）的 walk-forward（滚动前推验证）
- final OOS（final out-of-sample，最终样本外）：`2026-01-01` 到 `2026-05-31`，只报告，不用于调参

这套协议的定位是“第一版正式主板挖因子评分协议”。

它解决的是：

- 同一批主板候选因子始终用同一段历史做正式评分
- walk-forward 切片有稳定边界，不会因单次 run 临时漂移
- final OOS 有独立身份，不会混进调参样本

区块二只负责记录引用关系、切片规则和质量追溯，不在本仓重写主板股票池构造逻辑。

### 7.3 data quality policy

触发例子：

- 新增检查项
- `fail` / `warning` 阈值调整
- `sandbox_v1` 和 `mining_v1` 对 warning 的处理方式不同

现在先守住这几条：

- 合同破坏类问题直接 `fail`
- 统计可疑类问题标记 `warning`
- warning 的解释要能让人看懂，不只是机器字段

### 7.4 dataset manifest contract

触发例子：

- 新增来源字段
- 新增 sample protocol 追溯字段
- 新增 source review 引用字段
- manifest 字段语义变化

现在先守住这几条：

- 字段要稳定
- 字段语义要清楚
- 新旧 run 需要可追溯、可比较

当前主板正式版建议在 `manifest`（清单元数据，用来记录数据来源、样本协议和追溯字段）里至少保留下面这些字段：

| 字段 | 中文解释 |
| --- | --- |
| `dataset_id` | 冻结数据集名称，用来区分不同主板数据集 |
| `source_universe_key` | 上游股票池键名，本轮统一写 `univ_trade_mainboard` |
| `sample_protocol_id` | 样本协议名称，用来标识这套正式评分切片 |
| `sample_protocol_hash` | 样本协议指纹，用来确认切片规则没有被悄悄改动 |
| `date_start` | 正式评分窗口开始日期 |
| `date_end` | 正式评分窗口结束日期 |
| `warmup_start` | 预热期起点，只用于长窗口因子计算 |
| `forward_return_definition` | 未来收益定义，用来说明收益是怎么算出来的 |
| `data_quality_report` | 数据质量报告路径或标识，用来回看 warning / fail 结论 |

## 8. 当前推荐执行方式

当前先不要继续拆很多专项治理文档。

建议先这样执行：

1. 用本文件做区块二总入口
2. `source pipeline review` 继续用专项治理文档
3. `sample protocol`、`data quality policy`、`manifest contract` 先在本文件下管理
4. 等 B 线真的复杂起来，再决定是否拆专项规则

这样做的好处是：

- 不会一开始就文档爆炸
- agent 也不会每次都读很多材料
- 规则已经有地方可落，不会继续飘着
- 重点仍然是方便人审查，不是让 agent 自治

## 9. 成功标准

这份文档的成功标准不是“多了一份 markdown”。

而是：

```text
agent 知道区块二哪些东西属于协议
agent 知道什么时候需要继续看规则
人知道什么时候需要确认口径
文档数量保持最小，但关键规则不会丢
```

如果能做到这些，区块二会变得更完善，但不会明显更复杂。
