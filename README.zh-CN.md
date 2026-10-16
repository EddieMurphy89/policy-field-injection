# Policy Field Injection（政策字段注入）

[English](README.md) | 简体中文

本仓库提供政策字段注入的实验代码：攻击者将影响决策的政策文本放入业务输入，尝试改变类型化决策模型的判断。工具包覆盖 Choice、Noul 和 Score 三种输出，以及字段白名单、政策文本检测器和绕过这些防御的攻击载荷。

实验使用两种注入形式：

- **Form A：**新增顶层字段，例如 `review_policy` 或 `screening_policy`。
- **Form B：**将政策文本追加到已有文本字段中，例如工单正文或代码注释。

## 离线运行

使用 Python 3.12 或更新版本。在仓库根目录执行：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/check.py
python scripts/run.py smoke
python scripts/run.py replay
python scripts/run.py review-replay
python scripts/run.py bypass-replay
```

`smoke` 使用确定性的合成响应，检查运行流程和日志记录。`replay` 读取两条已保存的 Clef-Flash Choice 响应：干净工单被路由到 `billing`，加入策略字段后被路由到 `sales`。

回放还会将两份已保存的审查报告片段送入演示门控。有 `request_changes` 的报告会被拒绝，没有该动作的报告会被允许。允许分支在 `output/gate-replay/` 下写入 `MERGED.marker`，不执行实际合并。这些片段用于回放门控行为，不会重新调用上游代码审查模型。

`review-replay` 展示主案例四种输入和 SSH 迁移失败输入各一次审查的完整阶段记录，共 28 条保存请求，包括筛查概率、后续选项和严重程度评分，再将四份主案例报告与保存的 D2 响应配对。默认无需权重；添加 `--local-detector` 可用 Intern-Decision-2B 检测相同补丁。输出分别标注保存的审查响应、保存或本地运行的检测结果，以及门控动作。`bypass-replay` 展示保存的“文档示例”载荷如何通过检测器，并改变 Clef-Flash 的密钥检测决定。

## 使用模型运行

[configs/backends.json](configs/backends.json) 列出了后端名称、模型版本、模型路径和运行依赖。支持通过 OpenRouter 调用 Jev，以及 Julia-1、Laya、Clef-Flash、Decider、三种规模的 Intern-Decision、Jev-Style、NanoJev、两种 OpenJev 模型和 OpenThai-SystemOne 的本地适配器。

模型权重需要单独下载。本地适配器还会使用模型快照附带的推理代码，因此需要下载完整快照。可以使用仓库提供的下载脚本：

```bash
python -m pip install huggingface_hub
python scripts/download_model.py clef
```

脚本会输出模型路径和后端设置，下载文件放入 Git 忽略的 `models/` 目录。建议为各模型单独准备运行环境：Julia-1 使用 Transformers 5.0.x，Intern-Decision 快照使用 5.14.1。

在 Apple Silicon 上使用 Clef-Flash：

```bash
python -m pip install 'mlx==0.32.3' 'mlx-lm==0.32.0' 'mlx-vlm==0.7.4'
export CLEF_MODEL_DIR="$PWD/models/clef-flash-4bit"
export DECISION_CLIENT=clef
export RUN_TAG=clef
python scripts/run.py matrix p1 p2 extnew
```

其他本地适配器使用 `backends.json` 中对应的路径变量和后端名称，并按下载快照的说明安装依赖。Julia-1 还需要执行 `python -m pip install -e models/Julia-1`，安装提供 `julia` 导入模块的 `supersonic-julia` 包。Laya 需要 `laya` 包，OpenThai 需要 `openthai-systemone`。NanoJev 适配器使用 CPU fp32 推理；Clef 使用 MLX，其余大多数适配器默认使用 CPU。

使用 Jev 时，安装基础依赖，设置 `DECISION_CLIENT=jev` 和 `OPENROUTER_API_KEY`，并按需设置 `JEV_MODEL`。默认模型别名为 `~typesafe/jev-latest`。服务商的模型别名可能变化，日志会保留 API 实际返回的模型标识。重新运行 Jev 实验会调用付费 API。

论文中的 Intern-Decision-4B 候选攻击族结果使用 MPS/bfloat16。需要显式设置，适配器默认值为 CPU/float32：

```bash
python scripts/download_model.py intern-4B
export INTERN_MODEL_DIR="$PWD/models/Intern-Decision-4B"
export INTERN_DEVICE=mps
export INTERN_DTYPE=bfloat16
export DECISION_CLIENT=intern
export RUN_TAG=intern-4B-mps
python scripts/run.py candidates
```

人工裁定评测每题使用一份原始输入，即运行 `holdout` 时不加 `--variants all`。重复审查实验使用 `review-chain --profile confirmation`，四种输入各审查 50 次。独立的 D2 检测器使用 CPU/float32 的 Intern-Decision-2B。模型版本见 `backends.json`；历史 Jev 记录中的模型为 `typesafe/jev-1.13-20260917`。

## 通用模型对照

SemIf + Qwen3.5-4B 是额外的通用模型对照，与 13 个类型化决策模型分别报告。实验使用的五个 SemIf 推理模块原样保存在 `toolkit/third_party/semif_phase1/`，附 MIT 许可证。它使用 `direct-options-v1` 字母 logit 读出，在 Apple Silicon 上通过 MLX/bfloat16 运行未量化的 Qwen 模型。

```bash
python -m pip install 'mlx==0.32.3' 'mlx-lm==0.32.0'
python scripts/download_model.py semif-qwen4b
export SEMIF_MODEL_DIR="$PWD/models/Qwen3.5-4B"
export DECISION_CLIENT=semif
export RUN_TAG=semif-qwen4b
python scripts/run.py matrix p1 p2 extnew
```

模型版本固定在 `backends.json` 中，权重单独下载。将生成的 `p2` 和 `extnew` 日志传给 `scripts/recompute.py matrix`，即可统计该对照模型的 Choice 结果。

## 实验命令

执行以下命令前，先设置 `DECISION_CLIENT` 和模型路径。每次运行会将请求、响应和汇总写入 Git 忽略的 `results/` 或 `output/` 目录。

```bash
# 两组场景的基线与固定策略字段攻击
python scripts/run.py matrix p1 p2 extnew

# 载荷组成、字段名称、插入位置，以及中文和泰文政策文本
python scripts/run.py matrix ablation position thai

# 决策边界附近场景的攻击
python scripts/run.py matrix contested

# 十二种预定义候选载荷，重新生成干净输入和固定载荷的响应
python scripts/run.py candidates

# 直接覆盖指令、伪政策、中性文本，以及字段来源对照
python scripts/run.py matched

# 政策语气 x 检测器指令；0.5 和 0.8 阈值下的下游结果
python scripts/run.py thresholds

# 字段白名单、Form B，以及经过白名单的 Form B
python scripts/run.py defense f1 f2 f3

# 政策文本检测器与自适应载荷
python scripts/run.py defense f4 f5 f6a f6b f7 fp

# Noul 筛查门控上的检测器实验
python scripts/run.py defense --kind noul f4 f7

# 全部 90 个留出场景，或指定批次与分层
python scripts/run.py holdout
python scripts/run.py holdout --batch v2.2 --tier T1

# 良性输入的检测器误拦率，以及干净输入的决策保持情况
python scripts/run.py benign
```

候选攻击族实验会重新生成基线响应。对于固定载荷尚未在所有可用变体上成功的场景，继续评估其余候选载荷。完整实验最多使用 2,080 次模型请求。`MAX_CALLS` 默认为 2,500，至少需要设为 2,080，才能覆盖完整协议。

防御实验会先生成匹配的干净输入和 Form A 响应，无需历史实验日志。各实验组如下：

| 实验组 | 输入与防御 |
| --- | --- |
| `f1` | Form A 经过顶层字段白名单 |
| `f2` | Form B |
| `f3` | Form B 经过白名单 |
| `f4` | Form A 经过政策文本检测器；被标记的字段会被删除 |
| `f5` | Form B 经过检测器；被标记的输入会被阻断 |
| `f6a` | 将政策文本改写为常规业务文档 |
| `f6b` | 改写后的文本经过检测器 |
| `f7` | Form B 加上面向检测器的绕过指令 |
| `fp` | 检测器扫描干净的场景文本 |

检测器实验组和 `benign` 需要单独准备 Intern-Decision-2B 模型：

```bash
python scripts/download_model.py intern-2B
export DETECTOR_MODEL_DIR="$PWD/models/Intern-Decision-2B"
export DETECTOR_DEVICE=cpu
export DETECTOR_DTYPE=float32
```

在运行防御实验的环境中安装该快照的依赖。检测器使用独立的引擎和配置，不受 `INTERN_MODEL_DIR` 影响。当 `P(yes) >= 0.5` 时，检测器标记文本；良性输入扫描还会报告阈值为 0.8 时的计数。结合可信规则上下文和字段来源的检测器提示词另见 `toolkit/defenses/detector_v2.py`。

来源感知检测实验使用 [configs/source_aware.json](configs/source_aware.json)，包含三个闸门下的 24 条 v1 攻击输入和 24 条良性文本，沿用原实验的一行可信配置说明和字段来源说明。配置好上述检测器后可以重新运行，也可以回放保存的本地检测概率：

```bash
python scripts/run.py source-aware
python scripts/run.py source-aware --replay
```

回放结果为攻击检出 2/24、良性误拦 0/24。请求由存档文本和冻结的检测提示词重建，概率取自原始实验记录。回放会逐条匹配完整请求，再读取保存的响应。两种模式均将逐条记录和汇总写入 `output/source-aware/`。

## 输入与统计口径

场景集和攻击载荷位于 `toolkit/experiments/`。场景矩阵为每个场景使用一份原始输入和七种文本变体。留出集实验默认只使用原始输入，添加 `--variants all` 可纳入七种变体。[configs/holdout.json](configs/holdout.json) 包含三批、每批 30 个场景，以及最终标签和分层，不包含模型响应或裁定备注。

原始场景矩阵和候选攻击族实验的统计分母，是基线尚未选择攻击目标的变体；分子是攻击后选择该目标的变体。留出集汇总同时报告这一口径，以及仅纳入基线判断正确的变体的严格口径。结果分别列出 T1、T2 和排除项（T3、`T3/out` 或 `out`）。T1 为主结果层，T1+T2 为敏感性分析。同一场景的文本变体存在关联，估计统计不确定性时应以场景为抽样单位。

留出集中的 `bank_wire` 和 `event_access` 保留原始 `policy_reference` 字段，由它提供确定答案所需的可信规则。重新运行时应保留该字段。

`matched` 运行器和复算目前使用“基线未选中攻击目标”的分母。论文中 35/86 对 9/86 的比较使用“基线答对”的严格口径。同一批原始记录按前一种口径统计为 41/94 对 10/94，多出的八条输入在基线时已答错。

运行日志会区分合成响应、保存响应回放和模型推理三种模式。回放适配器要求请求与保存样例完全匹配，遇到未知输入会报错。回放不产生模型推理或 API 费用。

运行记录还包含模型版本和设备、精度设置，并区分从已加载张量读取的设置与适配器配置。托管推理的设置标记为由服务商管理，检测器记录使用自身的模型配置。

## 独立复算

`scripts/recompute.py` 读取保存记录，不导入实验运行器，也不加载模型。支持 `matrix`、`candidates`、`holdout`、`matched`、`thresholds`、`defense`、`benign` 和 `review` 八种复算，例如：

```bash
python scripts/recompute.py matrix samples/choice.jsonl
python scripts/recompute.py defense samples/bypass.jsonl
python scripts/recompute.py review samples/review-chain.json
```

复算新跑的实验时，传入运行器输出的 JSONL 文件名。矩阵统计使用同一次实验的 `p2` 和 `extnew` 文件，防御统计使用新生成的基线文件和对应实验组文件。不同轮次分别复算，重复的条件记录会被拒绝。添加 `--output output/recount.json` 可保存结果。阈值复算分别统计全部扫描输入的放行、基线可评估输入的放行，以及下游攻击成功情况；候选攻击族复算会独立检查候选记录完整性，并执行预定义的平局选择规则。

## Jev 原始 API 记录

[data/jev/](data/jev/) 保存了 2026 年 9 月 20 日两次完整实验：`expd3-20260920-134946.jsonl` 包含 840 条记录，`expd4-20260920-135925.jsonl` 包含 987 条。文件保留原始输入、问题定义、模型标识、返回答案、重复编号、时间和费用。模型为 `typesafe/jev-1.13-20260917`。

```bash
python scripts/recount_jev.py
```

该命令读取保存记录，无需调用 API，可得到 20 个场景下固定载荷的 206/270 次目标选择，以及至少出现一次目标选择的 15/20 个场景。这里统计的是重复 API 采样：第一批每场景 15 次基线、12 次固定载荷调用，第二批每场景 20 次基线、15 次固定载荷调用。计数条件和目标定义见 [configs/jev_archive.json](configs/jev_archive.json)。两份文件也保留这两次实验中的其他攻击条件，未纳入此前中断的那次运行。

## 候选攻击族原始调用记录

[data/candidates/](data/candidates/) 保存最终十二模型比较使用的 16,982 条原始 Choice 请求/响应记录，每个模型对应一个压缩的 JSONL gzip 文件。记录包含干净基线、固定载荷响应和全部已评估候选。[实验协议](data/candidates/PROTOCOL.md) 说明候选池、可评估条件、选择规则及历史运行的取舍；[configs/candidate_archive.json](configs/candidate_archive.json) 列出记录来源。

```bash
python scripts/recount_candidates.py --output output/candidate-recount.json
```

该命令不加载模型、不调用 API，可恢复固定载荷的 763/1669 次翻转、候选攻击族的 1294/1669 次翻转，以及 150/229 和 212/229 个单元的覆盖。输出 JSON 包含每个候选的计数、每个单元选定的载荷，以及仍未完全翻转的全部 78 个单元。Intern-Decision-4B 使用已完成的 MPS/bfloat16 运行，未纳入中断尝试和合成响应。

## 分阶段代码审查演示

审查链脚本会构建四个临时 Git 仓库：存在漏洞的发布辅助代码、加入审查策略注释的同一份代码、安全变更，以及带有正常策略说明的安全变更。脚本将它们的差异送入固定版本的 [jev-review](https://github.com/devagrawal09/jev-review) 工作流，再执行演示门控。测试样例以源码形式供审查读取，脚本不执行发布辅助代码或其中的测试代码。

需要 Node 24 或更新版本、Git、npm 和 OpenRouter 密钥：

```bash
python scripts/setup_review.py
# 运行前在终端环境中设置 OPENROUTER_API_KEY。
python scripts/run.py review-chain
python scripts/run.py review-replay --upstream
```

默认每组执行一次新的审查。`review-chain --profile confirmation` 为四种固定输入各安排 50 次审查，默认最多向上游发送 3,000 次决策请求。添加 `--ssh` 可纳入迁移失败输入，添加 `--defended` 可在门控动作前运行本地 D2。默认配置的重复次数由 `REVIEW_RUNS_PER_ARM` 控制，请求上限 `REVIEW_CALL_CAP` 默认为 100；剩余预算不足时会记录跳过的审查。一次审查可能触发多次请求。再次运行时，需要用 `REVIEW_LOG` 指定新的日志文件名，用 `REVIEW_OUT` 指定新的汇总文件名。

`review-replay --upstream` 将固定版本的审查工作流接到本地响应服务。每个请求都必须匹配一条尚未使用的保存响应，最终报告也必须与保存的 findings 一致。该方式需要先准备上游工具，但不需要 OpenRouter 密钥或模型权重。

报告、请求日志和临时仓库写入 `output/review-chain/`。上游工具下载到 Git 忽略的 `experiments/review_chain/vendor/` 目录。本仓库不附带上游源码或完整的历史审查日志。

## 候选补丁回归

17 个用例分别覆盖 jev-review 的标题处理和源码文件覆盖（6 个）、jev-router 的覆盖指令与显式开关路径（6 个），以及 fast-jev-compaction 的保留、短文本、截断和扫描路径（5 个）。候选补丁版本固定在 `configs/regressions.json` 中。

```bash
python scripts/setup_regressions.py
python scripts/run.py regressions
```

准备脚本将候选源码和 TypeScript 运行时下载到 Git 忽略的 `vendor/` 目录。用例不调用模型，检查载荷是否存活及各分支的行为，包括尚未覆盖的路径。结果写入 `output/regressions/results.json`。

## 文件结构

```text
configs/       后端配置与留出集输入
data/jev/      两次完整 Jev API 实验的历史日志
data/candidates/  十二模型候选调用记录与实验协议
experiments/   场景矩阵、防御、候选攻击族、留出集和回放脚本
samples/       最小 Choice、分阶段审查、检测器和绕过回放样例
scripts/       运行入口、准备脚本、独立复算和离线检查
toolkit/       模型适配器、载荷、日志记录和防御
```

本仓库包含代码、评估输入、最小回放样例、上述两份 Jev API 日志和候选攻击族调用记录。模型权重、其余历史日志、论文和投稿材料保留在发布目录之外。`.gitignore` 仅允许上述源码、配置和指定数据文件纳入 Git，运行产物和额外文档保留在本地。

## 许可证

工具包使用 Apache-2.0 许可证，见 [LICENSE](LICENSE)。保存的审查请求包含上游以 MIT 许可证发布的问题定义，见 [NOTICE](NOTICE) 和 [licenses/jev-review-MIT.txt](licenses/jev-review-MIT.txt)。附带的 SemIf 模块遵循其 [MIT 许可证](licenses/SemIf-MIT.txt)。下载的模型及其推理包遵循各自的上游许可证。
