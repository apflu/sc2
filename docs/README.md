# 文档索引

**先读这一页，然后只读你需要的那一个文件。**

这些文档是写给会在这个仓库里干活的人和 agent 的，每份都尽量做到自足。之所以拆得这么细，是因为它们曾经不是——路线图长到 163 行、里面塞满了系统设计，而任何来改一行融毁逻辑的人都得先翻过存档同步和难度曲线。

## 我要动手做什么

| 你要做的事 | 读这个 | 别读 |
|---|---|---|
| 决定下一个做什么 | [`design/build-order.md`](design/build-order.md) | 系统文档，除非你选中了它 |
| 写 Galaxy | [`dev/galaxy-pitfalls.md`](dev/galaxy-pitfalls.md) | — |
| 在编辑器里摆东西 / 建单位 / 写 catalog | [`dev/authoring-contract.md`](dev/authoring-contract.md) | — |
| 改工作循环、PE-Box、能源、胜利 | [`design/systems/energy.md`](design/systems/energy.md) | |
| 改融毁 | [`design/systems/meltdown.md`](design/systems/meltdown.md) | |
| 改难度、波次强度、考验 | [`design/systems/difficulty.md`](design/systems/difficulty.md) | |
| 改存档 / 跨局解锁 | [`design/systems/persistence.md`](design/systems/persistence.md) | |
| 改防御设施、房间、守军 | [`design/systems/fortify.md`](design/systems/fortify.md) | |
| 加一个异想体 | [`dev/authoring-contract.md`](dev/authoring-contract.md) 的「异想体的 per-type 数字」一节 + 抄一份 `usr/abnormality/*.md` | |
| 改构建流程 | [`dev/pipeline.md`](dev/pipeline.md) | |

## 三份基础文档

这三份是**设计的来源**，不是实现说明。改实现不需要读完，但**推翻一条设计决定之前必须先读对应的那一节**——它们几乎每一条都写了"为什么不是另一种做法"，而那部分正是最容易被无意中撤销的。

| | 内容 |
|---|---|
| [`design/gameplay-baseline.md`](design/gameplay-baseline.md) | MVP 玩法基线。**§1 最高设计原则**是整个项目的地基，任何一条新机制都要能对它交代 |
| [`design/agents-and-abnormalities.md`](design/agents-and-abnormalities.md) | 员工、异想体两个坐标、槽位与三选一、任务与核心抑制、跨局持久化 |
| [`design/p0-scope.md`](design/p0-scope.md) | P0 那条链的范围（已完成，留作记录） |

**这三份不拆，即使它们最长。**代码注释里到处是 `Design 8.1`、`Baseline 7.1`、`§2.4` 这样的引用，拆开就会把编号全打断——而那些编号正是"这行代码为什么这么写"的唯一线索。它们本来就是按节读的，不是从头读的。

## 策划侧（用户手写，代码侧只读）

`usr/` 下的东西是**数据源**，不是说明文档。改它们等于改游戏：

| | |
|---|---|
| `usr/abnormality/<单位id>.md` | 一份文档 = 一个异想体。构建时被 `tools/gen_abnormalities.py` 解析成代码 |
| `usr/department.md` | 九个部门的升级树 |
| `usr/quests_unlocks.md` | 任务、解锁、核心抑制 |
| `usr/mechanism.md` | 工作速度与成功率的公式 |
| `usr/containment.md` | 收容单元的构成与状态 |

## 一条贯穿所有文档的规则

**新代码一律逐玩家写。**

代码库曾经有一个 `c_p0Player = 1`，用在英雄、部门和读数上。它长得像配置项，实际上是"只有一个玩家"这个断言，而且顺着每一处引用扩散——修的时候是三个模块一起改。它已经删干净了，仓库里零引用。

**再出现一个那样的常量就是信号。**

## `blizzard-tutorials/` 和 `mkdocs-sc2/`

第三方参考资料，不是本项目的文档。找 SC2 侧的事实优先 grep `~/SC2GameData/`（真实的官方数据和 native 定义），这两个目录是二手的。
