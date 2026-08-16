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
| 7 | **任务**：4 条递进 + 计数器 | 3,4,5,6,12 | **已落地** `60_quests.galaxy`，36 条里数了 11 条，欠持久化与奖励 | [`systems/quests.md`](systems/quests.md) |
| 8 | **准入闸门**：任务 → flag upgrade → `CRequirement` | 7 | 待做（纯数据） | §7.1 |
| 9 | **bank** | — | **已落地** `16_bank.galaxy` | [`systems/persistence.md`](systems/persistence.md) |
| 10 | **核心抑制**：lobby game attribute | 7, 8 | 待做 | §7.8 |
| 11 | **三选一发牌** | 6 + 残余难度字段 | **堵住**，见下 | §4 |
| 12 | 防御设施 + 房间/走廊 | — | **已落地并跑通**，欠守军/回收装置单位与更多点位 | [`systems/fortify.md`](systems/fortify.md) |
| 13 | **理智**：崩溃与恢复 | — | **已落地**，欠白伤 E.G.O 这件实物 | [`systems/sanity.md`](systems/sanity.md) |
| 14 | **难度**：逐玩家四档 + 全局平均 | — | **已落地** `01_difficulty.galaxy` | [`systems/difficulty.md`](systems/difficulty.md) |
| 15 | **考验**：四档，上限由难度定 | 14 | **框架已落地** `27_ordeals.galaxy`，欠单位与逐类型行为 | [`systems/ordeal.md`](systems/ordeal.md) |

§ 指 `agents-and-abnormalities.md`。PE-Box 与能源见 [`systems/energy.md`](systems/energy.md)。

## 堵住的东西

### 第 11 项：残余管理难度还没有通道

三选一的准入读的是**残余管理难度**（§4.2），而那个字段放哪儿还没定（见 `dev/authoring-contract.md`）。

在它定下来之前，异想体就先在编辑器里摆好，不做抽取。**不要为了让第 11 项能动就随便挑一个通道存它**——上一次凭空推导出 `User2` attribute 就是这么来的。

同一个未决问题还挡着另外两件事：存档压缩需要的**稳定逐异想体序号**（见 `systems/persistence.md`），以及**"工具异想体"标志**（融毁永不点名它，见 `systems/meltdown.md`）。三个都是"每个异想体一个 per-type 值"，很可能是同一次决定。

### 第 12 项：已经不堵了

一条 `corridor_a` + 一个 `fort1` 点位 + `Lob_Turret_Fire` + `Lob_Build` 已经端到端跑通：买级 → 工人前往 → 建造虚影 → 工地 → 成型 → 空闲钻地 → 敌人靠近升起。

要扩就是重复同一套四样东西：

1. **region** 命名 `room_*` / `corridor_*`
2. 单位（按"单位由用户建"那条），`Cost` **置 0**——修复费用按单位自身 Cost 算，置 0 才让"SCV 免费重建"成立，钱在升级那一步收
3. `CAbilBuild` 的 `InfoArray` 里加一行（守军**不需要**，它们是折跃进来的）
4. 把真单位摆到该站的位置上，加进 group **`fort1` / `fort2` / `fort3`**（group 名 = 等级）

还没有的：`Lob_Guard_*`（守军，两张表现在是空的，所以 `Fort_SeedGarrison` 惰性）、`Lob_Salvage_*`、以及 2/3 级的点位。

**从原版复制单位时，凡是按单位名键控的东西都要跟着改。**morph 技能、驱动 morph 的 behavior/effect、morph 音效、`##unitName##Build` 那个脚手架 actor——这四样都咬过一次，细节在 [`systems/fortify.md`](systems/fortify.md)。

## 下一个

**不是持久化。**第 7 项的存档那一半（`16_bank` 的 quests section）技术上随时能做、也不等任何未决问题，但它**排在整个 milestone 的最后**——存档要存的是这一版最终定下来的形状，而形状还在动。提前做一次就等于要再做一次。

所以剩下的顺序按"能不能自己跑起来"排：

1. **`Lob_Ordeal_Dawn_*` 四个单位**。框架在等它们——建出来之前 `-ordeal` 会一直说 `NOTHING`。四份原作资料在 `docs/usr/ordeals/`，血量/伤害/移速/四抗全在里面。
2. **每种考验自己的行为**：虫子钻地、小丑偷箱子、机器人处决溅白伤、紫罗兰自爆清 Qliphoth。要等单位存在。
3. **第 5 项剩下的**：Qliphoth 归零之后每个异想体各自做什么。
4. **第 8 / 10 项**要读存档，跟着第 7 项走。

任务**内容表本身还有空格**——`usr/quests_unlocks.md` 里安保部 2/3、中央本部 1-3、福利部整节都是空的。那 25 条数不了的任务里有一部分就是这个原因，**填表是策划侧的事**，代码这边已经把位置留好了（声明了但标成 `countable = false`，`-quest` 会说 "no channel yet"）。
