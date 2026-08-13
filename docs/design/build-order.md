# 还差哪些系统

> 把 `agents-and-abnormalities.md` 和 `usr/quests_unlocks.md` 要的东西拆成可实现的模块，按依赖排序。
> **这是路线图，不是设计文档。**每一行的设计在 `systems/` 下，这里只回答"下一个动手的是哪个，以及为什么不是别的"。
>
> 它曾经不是这样——长到 163 行、塞满了融毁和存档的设计论证，任何来看"下一步做什么"的人都得先翻过去。如果这一页又开始长，说明有一节该搬进 `systems/` 了。

## 清单

| # | 系统 | 依赖 | 状态 | 设计 |
|---|---|---|---|---|
| 1 | **员工**：四项属性、等级、SP、永久死亡 | — | **已落地** `11_employee.galaxy` | §2 |
| 2 | **收容单元**：大门 downable、异想体常驻、Qliphoth | 08, 09 | **已落地** `13_containment.galaxy` | `usr/containment.md` |
| 3 | **工作**：每箱一掷、结果判定、四种伤害 | 1, 2 | **已落地** `14_work.galaxy` | `usr/mechanism.md` |
| 4 | **融毁**：60s 倒计时 + 等级 | 2 | **已落地** `13_meltdown.galaxy` | [`systems/meltdown.md`](systems/meltdown.md) |
| 5 | **突破 / 镇压** | 2 | **已落地**（在 13 里），欠「计数器归零后各自做什么」 | §5 |
| 6 | **观察等级 / 图鉴** | 2 | **已落地**（在 13 里） | §4.3 |
| 7 | **任务**：4 条递进 + 计数器 | 3,4,5,6,12 | 待做 | §7 + `usr/quests_unlocks.md` |
| 8 | **准入闸门**：任务 → flag upgrade → `CRequirement` | 7 | 待做（纯数据） | §7.1 |
| 9 | **bank** | — | **已落地** `16_bank.galaxy` | [`systems/persistence.md`](systems/persistence.md) |
| 10 | **核心抑制**：lobby game attribute | 7, 8 | 待做 | §7.8 |
| 11 | **三选一发牌** | 6 + 残余难度字段 | **堵住**，见下 | §4 |
| 12 | 防御设施 + 房间/走廊 | — | **已落地** `26_fortify.galaxy`，欠编辑器侧 | [`systems/fortify.md`](systems/fortify.md) |
| 13 | SP = Energy vital | — | **已落地**（在 11 里），欠「疯狂做什么」 | 基线 8 |
| 14 | **难度**：逐玩家四档 + 全局平均 | — | **已落地** `01_difficulty.galaxy` | [`systems/difficulty.md`](systems/difficulty.md) |
| 15 | **考验**：四档，上限由难度定 | 14 | 待做（上限已就位） | [`systems/difficulty.md`](systems/difficulty.md) |

§ 指 `agents-and-abnormalities.md`。PE-Box 与能源见 [`systems/energy.md`](systems/energy.md)。

## 堵住的东西

### 第 11 项：残余管理难度还没有通道

三选一的准入读的是**残余管理难度**（§4.2），而那个字段放哪儿还没定（见 `dev/authoring-contract.md`）。

在它定下来之前，异想体就先在编辑器里摆好，不做抽取。**不要为了让第 11 项能动就随便挑一个通道存它**——上一次凭空推导出 `User2` attribute 就是这么来的。

同一个未决问题还挡着另外两件事：存档压缩需要的**稳定逐异想体序号**（见 `systems/persistence.md`），以及**"工具异想体"标志**（融毁永不点名它，见 `systems/meltdown.md`）。三个都是"每个异想体一个 per-type 值"，很可能是同一次决定。

### 第 12 项：代码写完了，等编辑器

`26_fortify.galaxy` 已经落地，但它现在**扫不到任何东西**。要跑起来需要三样编辑器侧的东西：

1. **region** 命名 `room_*` / `corridor_*`
2. **工事点位** `Lob_Fort_L<n>_<Rest>` 摆在那些 region 里
3. **`Lob_Turret_*` / `Lob_Guard_*` / `Lob_Salvage_*`** 单位（按"单位由用户建"那条）

建工事建筑时**把 `Cost` 置 0**——修复费用是按单位自身 Cost 算的，置 0 才让"SCV 免费重建"成立，钱在升级那一步收。

## 下一个

**第 7 项，任务的计数一半。**它现在能数的东西比看起来多：

| 任务 | 读什么 |
|---|---|
| 培训部 1 / 2 | 员工等级（`Emp_Rank`） |
| 培训部 3 | 镇压过的不重复异想体 |
| 情报部 1 | 完成的工作次数 |
| 情报部 2 | 观察等级（`Cont_ObservationOfPlayer`） |
| 情报部 3 | 本部门升级等级（`Dept_LineLevel`） |
| 控制部 3 | 融毁（`Melt_AnsweredBy` 已经在数了） |

只有控制部 1 和安保部 1 要防御设施。

注意任务**内容表本身还有空格**——`usr/quests_unlocks.md` 里安保部 2/3、中央本部 1-3、福利部整节都是空的。所以先做的是框架和已写明的那几条，**不是把表填满**（那是策划侧的事）。
