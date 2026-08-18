# 四种伤害该走哪条通道

**调查 + 一条已经跑通的竖切。**承重的两个问号已经在游戏里验过（见「验过了的」）。结论在最前面，证据在后面，代价和待确认的东西在最后。

起因是一个具体的问题：**E.G.O 武器要不要把伤害数值全部换成 placeholder？**——即保留原版武器的 UI（面板上那个"Damage: N"），但实际数值由脚本另算。

调查下来，**有比 placeholder 更好的答案**，而且它顺带把 `Emp_DamageScale` 那个悬了很久的"Red/White/Black/Pale 需要一条自己的通道"给填上了。

---

## 结论

**`Kind` 就是那条通道。**

`CEffectDamage` 的 `<Kind>` 在整个原版数据里**只有四个取值**：

```
Melee   Ranged   Spell   Splash
```

而我们**正好有四种伤害**。

这不是巧合能用的那种巧合——它是引擎里唯一一条"伤害的种类"轴，而且已经被到处认得：

| 认得 `Kind` 的地方 | 是什么 |
|---|---|
| `<DamageTakenFraction index="Melee" value="0.8"/>` | **异想体和考验的四条防御**，逐单位，引擎算 |
| `<DamageDealtFraction index="...">` | 增伤，同一条轴 |
| `<DamageResponse><Kind>...</Kind>` | 拦截：改数值、清零、触发另一个效果 |
| `TriggerAddEventUnitDamaged(t, u, c_unitDamageTypeRanged, ...)` | **脚本按类型注册伤害事件** |

最后一条尤其关键：`c_unitDamageTypeSpell / Melee / Ranged / Splash` 是**触发器层的常量**，也就是说这四个种类在脚本里是一等公民，不需要我们自己解码。

于是 **E.G.O 武器不需要 placeholder：数值就写真的。**

---

## 证据

### 一、`Kind` 只有四个值

```
$ grep -rhoP '(?<=<Kind value=")[A-Za-z]+' mods/*/base.sc2data/GameData/EffectData.xml | sort -u
Melee
Ranged
Spell
Splash
```

`DamageTakenFraction` / `DamageDealtFraction` 的下标也正好是这四个（外加一个 `NoProc`）。

### 二、四条防御是原生的

维基上每个异想体和考验都带一张表：

> 绯红黎明：RED 0.8（耐受）/ WHITE 1.3（脆弱）/ BLACK 1.3（脆弱）/ PALE 2.0（易伤）

这张表现在**没有地方放**。有了 `Kind` 映射之后它就是一个隐藏 buff：

```xml
<CBehaviorBuff id="Lob_Def_Ordeal_Dawn_Crimson">
    <InfoFlags index="Hidden" value="1"/>
    <Modification>
        <DamageTakenFraction index="Melee"  value="0.8"/>
        <DamageTakenFraction index="Ranged" value="1.3"/>
        <DamageTakenFraction index="Spell"  value="1.3"/>
        <DamageTakenFraction index="Splash" value="2.0"/>
    </Modification>
</CBehaviorBuff>
```

**一张维基表格 = 一个 buff，一行都不用写脚本。**这是整件事里最大的一笔收益，因为这张表每个异想体都有一份，而异想体是要有三十个的。

### 三、SP 就是 Energy —— 我之前说错了

`Emp_SP` 读的是 `c_unitPropEnergy`，上限来自谨慎的 `<VitalMaxArray index="Energy" value="1"/>`。

也就是说 **SP 有一根引擎画的条**，就在血条下面。我在 `Emp_DamageShown` 的注释里写"SP 是我们的东西，引擎不画它的条"，**那是错的**，已经改掉了。

真实情况没那么惨也没那么好：条会动，但**没有数字、没有颜色，而且大多数玩家会把那根蓝条读成法力**。所以 `Emp_DamageShown` 仍然值得留着——它要补的是"扣了多少、什么类型、为什么"，不是"有没有反馈"。

这一条还有个副作用：**白伤在目录里其实是能表达的**，只是不能用 `CEffectDamage`：

```xml
<CEffectModifyUnit id="...">
    <VitalArray index="Energy"><Change value="-12"/></VitalArray>
</CEffectModifyUnit>
```

`CEffectDamage` 没有任何字段能打 Energy（它只有 `VitalFractionCurrent`，那是 Feedback 用的"当前值的百分比"）。但 `CEffectModifyUnit` 有 `VitalArray`，扣多少就是多少。

### 四、`DisplayEffect` 是真的

回答原问题：**`CWeaponLegacy` 有 `<DisplayEffect>`**，原版用得很多（寡妇雷、母舰核心、风暴舰、飓风、蝗虫……）。

它的作用正是"面板上显示这个效果的数值，实际打出去的是另一个"。所以哪怕我们最后真的要做 placeholder，工具是现成的、原版认证的。

**但按下面的方案，我们基本上不需要它**——只有黑伤会用到（它的真实效果是一个两成员的 `CEffectSet`，面板没法自己总结成一个数）。

### 五、脚本能听见伤害，而且能挑

```galaxy
native void TriggerAddEventUnitDamaged (trigger t, unitref u,
                                        int inDamageType, int inDamageFatal,
                                        string inEffect);
```

**能按伤害种类过滤，也能按效果 id 过滤。**配套的：

- `EventUnitDamageAmount()` —— 实际扣了多少
- `EventUnitDamageAttempted()` —— **被拦截之前本来要扣多少**
- `EventUnitDamageEffect()` —— 是哪个效果打的
- `EventUnitDamageSourceUnit()` —— 谁打的

### 六、`DamageResponse` 能拦

```xml
<CBehaviorBuff id="Lob_Mind_White">
    <BehaviorFlags index="Permanent" value="1"/>
    <InfoFlags index="Hidden" value="1"/>
    <DamageResponse ModifyFraction="0" ModifyMinimumDamage="1">
        <Kind index="Melee" value="0"/>
        <Kind index="Spell" value="0"/>
        <Kind index="Splash" value="0"/>
        <Kind index="NoProc" value="0"/>
        <Chance value="1"/>
    </DamageResponse>
</CBehaviorBuff>
```

**这个形状猜不出来，而且编辑器只会说 `Unable to find field`。**三处都反直觉：

| 直觉 | 实际 |
|---|---|
| `DamageResponse` 在 `<Modification>` 里 | **在行为本体下**，和 `Modification` 平级。`Modification` 是"带着它你有什么不同"（移速、护甲、`DamageTakenFraction`），而"被打时发生什么"不属于那一类。**但 `DeathResponse` 偏偏在 `Modification` 里** |
| `<Kind value="Ranged"/>` 选中一种 | `<Kind index="X" value="0"/>` 是**排除**。默认全部响应，你关掉不要的——所以上面列的是**忽略的三种**，不是捕获的那一种。原版范本是 `GuardianShield` 和 `HardenedShield` |
| `ModifyFraction` 是减免比例 | 是**乘数**。原版拿 2 做易伤、0.5 做抗性，所以 0 才是"一点都不落"。`DamageTakenNone` / `SpectreShield` / `ProtectiveBarrier` 都是这么写的，而且都**同时带 `ModifyMinimumDamage="1"`**——否则引擎坚持每次至少打掉一点，慈悲武器会把人慢慢治死 |

`Chance` 原版处处显式写 1，跟着写。

字段全集：`Chance ClampMaximum ClampMinimum Exhausted Fatal Handled Location Minimum ModifyAmount ModifyFraction ModifyLimit ModifyMinimumDamage Priority TargetFilters`，子元素还有 `Kind` / `RequireEffectArray` / `ExcludeEffectArray` / `ValidatorArray`。

**一个行为只能带一个 `DamageResponse`**（原版无反例），所以黑伤和苍伤各要一个自己的行为，不能挤在一起。

> `DamageTakenFraction` 则**确实**在 `<Modification>` 里（`FlashBangGrenade` 是范本）。两个字段一个在里一个在外，是这次踩坑的全部内容。

---

## 推荐的做法

一句话：**引擎能做的全交给引擎，脚本只做引擎做不到的那一件事——把数字送进 SP。**

### 出的方向（员工打怪）：100% 原生

武器是真武器，数值是真数值，`Kind` 就是伤害类型。

- 面板显示正确，不需要 `DisplayEffect`
- 目标的 `DamageTakenFraction` 自动套上它那四条防御
- E.G.O 护甲也是 `DamageTakenFraction`，**比我们自己的 `Emp_DamageScale` 百分比更好**：它天然支持超过 1.0（易伤），而且和异想体防御共用一套算法
- **零脚本**

### 进的方向（东西打员工）：拦一下

员工身上挂一个常驻隐藏 buff，把**白伤和黑伤**的生命扣减清零（`DamageResponse Kind ModifyFraction="0"`）。脚本注册对应种类的伤害事件，用 `EventUnitDamageAttempted()` 读回真实数值，然后：

- 白伤 → `SP_Damage`；**如果目标已崩溃 → `SP_Restore`**（这就是白 E.G.O 救人的机制，不用一行特判）
- 黑伤 → 一半生命一半 SP
- 红伤 → **完全不拦**，引擎打的就是对的
- 苍伤 → 拦，脚本按最大生命百分比算

也就是说 `Emp_CombatDamage` 从"每个调用点自己算"变成"一个伤害事件处理器"，而 `Emp_ApplyDamage` / `Emp_DamageShown` 原地不动，仍然是那唯一的漏斗。

### 苍伤是唯一一个没有原生形态的

`CEffectDamage` 没有"最大生命的百分之几"这种字段。`VitalFractionCurrent` 是**当前值**的百分比，不是最大值——用它会让残血的人挨得更轻，正好反了。

所以苍伤永远要走脚本。**四种里三种半原生，一种不行**，这个比例值得接受。

---

## 代价，和还没确认的

### `Kind` 被征用了，全地图都得守规矩

映射得定死（下面是提案，四选四，怎么配都行）：

| 我们的 | 引擎的 |
|---|---|
| RED | `Melee` |
| WHITE | `Ranged` |
| BLACK | `Spell` |
| PALE | `Splash` |

**代价是：地图里不能再有不守这条规矩的武器。**目前只有一处违规——`50_waves.galaxy` 的 `c_waveUnitType = "Zergling"`，用的是原版跳虫的武器。那是个占位系统，虫群单位本来就要自己做。

`Lob_Hero_Rifle` 原本是 `Kind="Ranged"`，按上表会变成白伤。**已经改成 `Melee`（红）**——一发子弹收的是命，不是理智。

> 我先前在 `Emp_DamageScale` 的注释里否定过这条路，理由是"一件抗 Red 的 E.G.O 会连带抗跳虫"。那个理由**在我们自己造所有武器的前提下不成立**——那正是这条路的全部意义。注释要改。

### 验过了的

| | 结果 |
|---|---|
| **`ModifyFraction="0"` 之后伤害事件还触发吗？** | **会。**`-dmg` 印出 `attempted=12 actual=0`。这是整个方案的承重点，现在它立住了 |
| **`AcquireFilters` 允许 Ally，引擎真的会主动选中友军吗？** | **会。**玩家会自己走过去打崩溃的员工，不用下命令。而健康的同事两把武器都够不着，报 "只能以 passive 单位为目标"——那正是两个过滤器该有的样子 |

### 还没验的

1. **`DamageTakenFraction` 在事件之前还是之后？**它决定抗性是引擎白送的还是得由 `Emp_DamageScale` 自己算。

   **`-dmg more` 就是这个实验。**用步枪（20 点，`Kind="Melee"` 即红伤）打绯红，它的红防是 0.8：

   | 读到 | 结论 |
   |---|---|
   | `attempted=16` | 抗性在事件**之前**就算完了——`attempted` 已经含抗性 |
   | `attempted=20 actual=16` | 抗性在**之后**，脚本拿到的是原始值 |

   两种都能用，但**必须知道是哪一种**，否则把 `Emp_DamageScale` 接上的那天会把抗性算两遍。
2. **`Kind` 除了伤害响应之外还影响什么？**比如 AI 的近战/远程判断、`KindSplash` 的配合。看上去不影响，但没验过。
3. **面板能不能显示伤害类型？**一个数字是够的，但"12（白）"更好。武器名和提示文本是本地化字符串而不是 UI 布局，所以应该能写——**这一条不碰 layout 文件**。

### 还没决定的

这条路会让**每个异想体多一个防御 buff**。它是 30 份逐单位数据，形状和"逐类型数值通道"那个悬案一模一样，**很可能是同一次决定的两面**：如果那个通道最后是"从文档生成目录 XML"，那这些 buff 也应该一起生成，而不是手写。

所以：**方案可行、收益明确，但落地方式最好和那个决定一起定。**

---

## 已经做了的例子（一条竖切）

`17_damage.galaxy` + 四处目录改动，只覆盖**白伤**这一种，用来验前面那三个问号。

| 东西 | 在哪 | 干什么 |
|---|---|---|
| 映射 | `17_damage.galaxy` 顶部 | `c_dmgKindWhite = c_unitDamageTypeRanged` 等四条。用引擎自己的常量改名，**没有表可以对不上** |
| 拦截 | `Lob_Mind_White` | `<DamageResponse ModifyFraction="0"><Kind value="Ranged"/></DamageResponse>`。**由脚本挂上**（`Dmg_GiveMind`），不写在 CUnit 里，所以复制出来的员工不会缺一个脑子 |
| 桥 | `Dmg_White_Func` | 读 `EventUnitDamageAttempted()`（**被拦之前**的数），送进 `Emp_CombatDamage` |
| 慈悲 | `Dmg_IsMercy` | 队友开的白伤 + 目标已崩溃 → `SP_Restore`。**这条规则在脚本里而不是在伤害类型里**，因为紫罗兰的自爆也是白伤，写进类型会让考验去治疗它本该击垮的人。区别不是类型，是**谁开的枪** |
| 第一件白 E.G.O | `Lob_Ego_Mercy` | 12 白，`AcquireFilters` 允许 Ally 且**要求 `Passive`**——崩溃状态设的正是这个旗标，所以拿白武器的人会自己停在崩溃的同事面前，拿红武器的人不会 |
| 一张防御表 | `Lob_Def_Ordeal_Dawn_Crimson` | 维基上那四个数，四行，挂在绯红身上，**零脚本** |

### 为什么慈悲武器是第二把枪，以及它为什么不占面板

过滤器是**一个合取式**（`required;excluded`），说不出"敌人，或者崩溃了的队友"。所以它是第二把武器，和原版处理对空对地是同一个办法——引擎自己挑哪把打得着。

**但它不会在单位面板上多出一行伤害**，因为 `<Options index="Hidden" value="1"/>`。

这也是原版对同一个问题的答案：刺蛇身上挂着一把隐藏的 `HydraliskMelee`，蟑螂挂着 `RoachMelee`，而爆虫真正开火的 `VolatileBurst` 是隐藏的、面板上那一行是一把没有 `Effect`、只有 `DisplayEffect` 的 `VolatileBurstDummy`。**单位开哪把枪和面板承认几把枪是两个问题**，`Hidden` 是回答后一个的字段。

藏起来也是更诚实的读法：**"白伤治疗崩溃的人"是伤害类型的规则，不是某一件 E.G.O 的属性**。面板该说这把武器对目标做什么，第二行只是把同一件事说了两遍。

> 一个副作用没有处理：**两把武器可以同时开火**。玩家可以一边用步枪打跳虫、一边给同事回理智。要让"救人占用你的注意力"成立，得给两把枪 `<Cost><Cooldown Link="..."/></Cost>` 挂同一个冷却池（`VolatileBurstDummy` 就是这么和 `VolatileBurst` 绑的）。**这是一个设计决定，不是 bug**，先记在这里。

### 一把共用的，还是每件 E.G.O 一把

既然隐藏了，每件白 E.G.O 配一把自己的慈悲枪在 UI 上不花钱，好处是**回复量能跟着武器走**。

代价是每件白 E.G.O 多一条目录条目要手写。**建议先做一把共用的**：装备系统在你装上白 E.G.O 时把它加上，卸下时拿掉，回复量是个定值。等回复量真的需要按武器分档时再拆，那时拆的是一条已经在运转的规则。

顺带给 `Lob_Hero_Rifle` 补了显式的 `AcquireFilters`（排除 Player/Ally）。它原来没写，靠 `TargetFilters` 兜底，而那个字符串**没有排除友军**——在这把枪之前无所谓，现在同一个单位身上有一把是真的会打友军的，两者不能含糊。

### 用 `-dmg` 验什么

三档，层层包含：

| | 印什么 |
|---|---|
| `-dmg on` | 只有打在**人**身上的（员工和玩家）——桥真正仲裁的那些 |
| `-dmg more` | 加上**考验和异想体**，到此为止。**这是打游戏时该开着的那一档** |
| `-dmg all` | 再加虫群、炮塔、废墟。诚实但读不了：一波跳虫啃炮塔是一秒十行 |

每行都标了 **`[ours]`** 还是 **`[engine]`**——谁真正把这个数落下去的。

**打怪物的伤害不被"拦截"，但现在会被印出来。**之前它是静默跳过的，而"什么都没印"和"触发器根本没响"从外面看一模一样。

- **什么都不打印** → `ModifyFraction="0"` 之后伤害事件不触发，整个方案要换钩子。这是最关键的一条。
- **`attempted=12 actual=0`** → 正确，桥通了。
- **`attempted` 不等于 12** → `DamageTakenFraction` 在事件之前就算过了。那是好事（护甲免费），但要写进文档。
- **走过去不自动开枪** → `AcquireFilters` 允许 Ally 并不足以让引擎主动选中友军，慈悲得改成主动技能。

## 决定：算术全部收进脚本

起因是一次读数对不上：琥珀打玩家，`-dmg` 报 `attempted=10`，而 `LocustMPDamage` 的 `Amount` 写着 12，玩家有 1 点护甲。

**查下来没有任何东西出错。**

| | |
|---|---|
| 12 从哪来 | `swarm.sc2mod` 里是 12。**我们依赖的是 Void**，`voidmulti.sc2mod` 把它覆盖成了 **10** |
| 那 1 点护甲呢 | `LocustMPDamage` 带着 `<ArmorReduction value="1"/>`，正好抵消 |

10 − 1 + 1 = 10。一分不差。

**而这正是问题。**解释一个两点的差额用掉了一次跨 mod 依赖查询和一个多数人没听说过的字段，结论还是"本来就没差"。**一个玩家推不出来的数字，和一个 bug 无法区分**——而这个游戏要求玩家在三十个异想体之间横向比较四种伤害。平砍护甲、属性加成、破甲，全都在减一些屏幕上没有的量。

所以：

> **目录只保留关于一次命中的两件事：基础数值，和类型。**其余全部是脚本。

落实：

- 四种伤害**全部**拦截，红伤也不例外——`Lob_Mind_Red` / `_White` / `_Black` / `_Pale`，一种一个行为（一个行为只能带一个 `DamageResponse`）
- `Lob_Hero_Agent` 的 `LifeArmor` 归 0
- 抗性落在 `Emp_DamageScale(who, type, source)`，现在恒为 100，等数据到位
- **E.G.O 等级的增伤/压制也在那里**——它依赖攻方和守方两边，是成对的，没有任何目录字段是成对的

### 怪物那边暂时还是原生的

一个怪物只有一个池子、每种伤害一个乘数，那**正好就是 `DamageTakenFraction`**——而那个乘数本来就是 Lobotomy 的抗性模型，不是星际的护甲。绯红那张表照挂不误。

**等级机制会终结这个例外**：成对的关系目录表达不了，到那时怪物这边也得进脚本，`UnitDamage(attacker, effect, victim, bonus)` 是现成的路。

### 顺带发现：琥珀的伤害类型是错的

`Lob_Ordeal_Dawn_Amber` 挂的是原版的 `LocustMP` 和 `LocustMPMelee`。`LocustMPDamage` 的 `Kind` 是 `Ranged`——**按映射那是白伤**，所以它才会被白伤拦截器接住。而资料上琥珀是**红伤 1-2**。

这是"地图里每一把武器都得守规矩"那条代价的第一个实例，而且它**安静地生效了**：琥珀一直在扣玩家的理智，看起来完全正常。

## 相关

- `docs/dev/authoring-contract.md` —— 工作伤害 / 战斗伤害的分工，`Emp_DamageScale` 的位置
- `docs/design/systems/sanity.md` —— SP、崩溃、白 E.G.O 的恢复
- `docs/design/systems/ordeal.md` —— 为什么考验的爆炸是脚本算的（在这条路落地之前，那些理由仍然成立）
