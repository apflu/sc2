# 编辑器侧 ↔ 代码侧 接口约定

编辑器侧负责**空间**（地形、房间、对象摆在哪），代码侧负责**行为**。这份文档是两者之间的唯一契约。

## 两条通道

| 通道 | 表达什么 | 预放对象 | 运行时生成 |
|------|---------|:-------:|:---------:|
| **单位类型** `Lob_Debris_Normal` | 这东西**是什么** | ✅ | ✅ |
| **编辑器 group** `debris` | 属于**哪个具名子集**（初始簇） | ✅ | ✗ |
| **编辑器 region** `resthall_a` | **一块地方**（房间、走廊、扇区范围） | — | — |

**代码里不出现任何编辑器 ID**——ID 由 `tools/gen_objects.py` 在构建时从地图文件里解析，不需要人工搬运。

### 为什么不用 ID 约定

编辑器给放置对象分配的是随机 32 位数（`1209983674`、`982629277`），**不是可手动指定的字段**，所以"按号段约定"这条路不存在。

但 `Objects` 是纯 XML，`UnitType`、`Player`、`Position`、group 成员全在里面，构建时直接解析即可。

### 为什么不用所属玩家分类

所有权在引擎里有原生语义——同盟关系、右键默认行为（打还是走）、选择、小地图颜色、AI 敌意判定。拿它当分类通道，等于让一个我们控制不了的行为轴承载数据语义。而且槽位只有 15 个，6 名玩家加虫群就吃掉一半。

**所有权保持为纯粹的玩法概念。**

### 为什么类型通道是主通道

因为它是唯一**同时覆盖预放和运行时生成**的通道。后期残骸要随机生成，那些对象没有编辑器 ID、没有 group，但一定有类型。

## 命名约定

```
Lob_<段1>_<段2>_<段3>...
```

单位注册在**它 id 的每一级前缀**下：

| 单位 | 可查询的层级 |
|------|------------|
| `Lob_SCV_Miner` | `SCV`、`SCV_Miner` |
| `Lob_Debris_Normal` | `Debris`、`Debris_Normal` |

所以脚本可以按需要的粒度提问——"所有 SCV" 还是"仅矿工"——而新增变体会自动落进它已有的各级前缀，**代码一行都不用改**。加一个 `Lob_Debris_Heavy`，`Debris` 那一层立刻就包含它。

**状态用不同的第一段表达，不是不同的变体。**

| | | |
|---|---|---|
| `Lob_Device_Basic` | 在线 | 落在 `Device` |
| `Lob_DeviceDown_Basic` | 失能 | 落在 `DeviceDown` |

这样 `ObjectsGen_ScanDevice()` 天然只返回**在线**设备，不需要任何过滤——这正是"不检测失能，直接数没失能的"。如果写成 `Lob_Device_Basic_Down`，它会同时落进 `Device`，"在线设备"就得靠减法算，那就白费了。

两者靠**段名替换**配对（`Lob_Device_` ↔ `Lob_DeviceDown_`，保留变体段），所以加一对新设备只用在编辑器里建两个单位，脚本不动。

生成器为每一级前缀产出：

```galaxy
unitgroup ObjectsGen_Scan<前缀> ()      // 全图存活、不分归属
bool      ObjectsGen_Is<前缀> (unit)    // 判定
unitgroup ObjectsGen_Group (string)     // 具名 group 成员（仅预放）
```

尚未建出单位的前缀会产出**空表**——扫描返回空、判定返回 false。所以代码可以先于单位写好，未完成的内容是惰性的而不是报错的，两台机器不必按同一顺序落地。预期前缀列在 `tools/gen_objects.py` 的 `EXPECTED_CATEGORIES`。

## 构建、语言的坑、自检

全部搬到了 [`galaxy-pitfalls.md`](galaxy-pitfalls.md)。**写 Galaxy 之前读那一页**——先声明后使用、没有数组初始化、位运算能用哪些、`natives.galaxy` 不是全集，每一条都对应至少一轮真实调试。

## P0 灰盒摆放清单

一个扇区，先不做多扇区。

1. **地形**：一个内层房间 + 通向外层的走廊 + 外层开阔区。粗糙即可。
2. **玩家角色** `Lob_Hero_Agent`：内层放**恰好一个**。它摆在哪就在哪复活——脚本不另设复活点，因为一个会和出生点漂移开的复活点迟早会变成 bug。
3. **残骸** `Lob_Debris_*`：外层摆 **14-18 个**，堵住部分通路。数量是算出来的，不是拍的——见 `docs/design/p0-scope.md` 的场景规模检查。
4. **设备** `Lob_Device_*`：外层摆 ≥2 个，至少一个**被残骸挡住**，且至少一个**离内层 25-35 格**。
5. **虫群入口**：外层边缘 1-2 处，到设备要留出行军距离。

**摆放的设计意图**：内层、设备、虫群入口三者的距离关系，决定了"跑过去修" vs "留下来打"这个取舍存不存在。设备离内层太近，玩家就不需要做选择，P0 白测。让至少一个设备远到跑一趟要付出真实代价——角色移速 3.0，往返 30 格是 20 秒，对着 45 秒的波次周期才算数。

## 异想体文档里的文字会变成玩家看到的字

`docs/usr/abnormality/<单位id>.md` 里的**名称**和**图鉴四段**会被 `gen_abnormalities.py` 抽进 `src/strings/abnormality.enUS.txt`，再合进地图的 `GameStrings.txt`。

所以：**写文档仍然是唯一的作者动作**，但那些字从此是可翻译资源。代码里拿到的是 key（`Lob/Abno/Lore/O_03_03/2`），不是文字。

要改措辞就改文档再构建；**不要改 `abnormality.enUS.txt`**，它每次构建都会被整体覆盖。

## 数据文件

`Base.SC2Data/GameData/` 下目前有四个 catalog，都是手写的：

| 文件 | 内容 |
|------|------|
| `UnitData.xml` | `CUnit` |
| `ActorData.xml` | `CActorUnit` |
| `WeaponData.xml` | `CWeaponLegacy` |
| `EffectData.xml` | `CEffectDamage` |

SC2 按固定文件名自动加载这个目录，新增一个 catalog 不需要改 `ComponentList.SC2Components`。

### 谁来建单位 **【已定】**

**`CUnit` 由人在编辑器里复制现有单位来建，不手写。**Behavior、Effect、Weapon、Upgrade 这类**不需要 actor** 的 catalog 条目可以手写。

理由就是下面那一整节：actor 靠 `unitName` 绑定，不跟着 `CUnit` 的 `parent` 走。手写一个 `parent="Marine"` 的单位得到的是**没有模型、没有枪口火焰、没有音效**的东西，而这些缺失不会报错，只会在游戏里看起来不对。编辑器复制会把 actor 一起带过来。

代码侧对此是免疫的：没建出来的前缀产出空表，扫描返回空、判定返回 false（见"命名约定"末尾）。所以**代码可以先写，单位后建**，中间那段时间只是功能惰性，不是坏的。

新建**员工**单位时要带上：

- id 以 `Lob_Emp_` 开头
- `BehaviorArray`：`Lob_Attr_Fortitude` / `Lob_Attr_Prudence` / `Lob_Attr_Temperance` / `Lob_Attr_Justice` / `Lob_Rank`
- 不带任何危险等级 attribute（`Light` / `Biological` 之类在本作里是等级，不是体型）
- `Food` 置 0（补给就是电网，Marine 的 -1 会让每个员工偷偷耗电）
- `LifeStart` / `LifeMax` **置 1**，`EnergyMax` / `EnergyStart` **置 0**，`EnergyRegenRate` 置 0

**属性直接就是那条 vital，不是加成。**

| 属性 | 是什么 | 怎么实现 |
|---|---|---|
| 勇气 Fortitude | **最大生命** | `Modification` 里 `VitalMaxArray index="Life" value="1"` |
| 谨慎 Prudence | **最大 SP** | `VitalMaxArray index="Energy" value="1"` |
| 自律 Temperance | 工作速度 +1%/点、成功率 +0.2%/点 | Galaxy 侧的两条公式 |
| 正义 Justice | 攻速与移速 | 待定 |

所以单位自身的基础值必须**让位**：`LifeMax` 是 1 不是 45，`EnergyMax` 是 0。血条上的数字就是面板上的数字，不用在脑子里做加法。

**那个 1 就是"员工必须有属性最小值"的原因。**单位在任何东西能给它设点数之前会存在一瞬间，那一瞬间 `LifeMax` 为 0 是活不下来的。所以基础值取"不为零的最小数"，`11_employee.galaxy` 在**创建事件**上播种属性（不是在 tick 上，那要等两秒）。

`c_statMin` 是**下限**而不是初始值，因为培训部能把属性**往下压**——两者需要同一个答案：员工可以被弄差，但不能被文书工作弄死。

播种之后还要**手动填满**：提高一条 vital 的上限**不会**同时提高当前值，否则员工会站在 1/21 血。

SP 的回复率为 0 是故意的：SP 靠主休息室和福利部回，不靠站着不动。

**白伤**（工作失败）就是扣这条 vital，和生命值没有任何关系——这正是重点：选错工作在人崩掉之前什么都看不出来。SP 归零挂 `Lob_Panicked`，那个 behavior 的 `Modification` **目前是空的**，因为设计说了疯狂会发生（§2.4、培训部 lv2、福利部白弹）但没说疯狂长什么样。

### 收容单元

结构见 `docs/usr/containment.md`。代码侧的两个关键点：**大门才是有耐久度的那个东西，收容单元不是**；**异想体一直存在**，"被收容"是它的一个状态，不是世界的状态。

| id | 是什么 | 数量 |
|---|---|---|
| 与文档同名（如 `O_03_03`） | 异想体本身 | 每个异想体一个 |
| `ContainGateHorizontal` | 大门 | 通用 |

**是不是异想体，看它有没有 `docs/usr/abnormality/<id>.md`**，不看命名前缀。见下文"异想体的 per-type 数字"。

大门属于哪个收容单元是**空间事实**，用空间回答（离该异想体 home 最近的门，`c_cellRadius` 以内），不靠命名绑定。大门类型目前在 `13_containment.galaxy` 里列名字，因为它是从暴雪的可破坏大门复制来的、不带 `Lob_` 前缀；改名成 `Lob_Door_*` 那张表就可以删掉。

**大门用的是原版可破坏大门的机制，不是 `Lob_Device_`/`Lob_DeviceDown_` 那种类型互换。**它自带降下状态和 revive，比类型互换更贴近"大门降下 / 升起"：**活着 = 升起，死了 = 降下**，恢复是 revive，全程没有 morph。

各自要带上：

- **异想体单位**：危险等级 attribute **恰好一个**，而且要和文档里写的一致（构建时会核对）。归属玩家 `c_abnoPlayer`。摆在收容单元里面——**它摆在哪，哪里就是它的 home**，镇压之后传送回那里。
- **大门**：不要带任何危险等级 attribute。原版大门自带 `Armored`，在本作里那是 HE。

#### 复制粘贴一个收容单元

一个单元是**三个单位**：异想体、`ContainGateHorizontal` 大门、`ContainGateControl` 控制台。三者之间**全是空间绑定**——没有名字、没有 id、没有编组，粘到哪儿就在哪儿成立一个单元。所以复制粘贴就是对的做法，代码这边一行都不用改。

要手动改的只有两样，而且两样都**不会报错**：

- **控制台的归属玩家。**`Cont_OwnerOf` 先读控制台的 owner，读不到才退到"离得最近的核心"。而编辑器粘贴时保留的是**复制来源**的玩家——从控制部复制一个粘到安保部，它仍然答应控制部。全场没有任何地方会提这件事，只有那边的熔毁会点到这个单元的名。`-cont` 会把这条冲突直接打出来（`own=X(PANEL SAYS SO, nearest core is Y)`）。
- **异想体的单位类型。**每个单元要放**不同的**异想体。同类型的两个单位在 `AbnoGen_IndexOf` 眼里是同一个索引，PE 箱和观察等级会共用。

大门和控制台是靠 `UnitGroupClosestToPoint` 认领的，所以两个单元挨多近都不会串——**除非某个单元漏了自己那扇门**，那它会安静地借用 `c_cellRadius`（12）以内邻居的那扇。`-cont` 里 `door=none` 是漏了门，看起来正常的门则可能是借的。

**镇压不是击杀。**异想体永远不会被移除；致命伤像设备那样被拦截，然后延迟传送回收容单元、恢复初始状态、计数器复位、大门立刻满血升起。设计 §5 禁止一次突破让人丢掉槽位，这就是它的实现。

三个 behavior 已经写好（不需要 actor）：`Lob_Contained`（无敌 + 不可指挥 + 被动 + 不能攻击，一个 `Modification` 说完）、`Lob_Qliphoth`（**层数就是计数器**）、`Lob_DoorStrain`（层数扣生命回复，让"修理只能拖延、不能阻止"成立——任何固定伤害数值都能被足够多的 SCV 修回来，递增的回复惩罚不能）。

### 玩家槽位

从地图自己的 `MapInfo` 读出来的，不靠记忆——玩家记录按槽位顺序带着各自的 race id：

| 槽位 | race | 是什么 |
|---|---|---|
| 1-6 | `Terr` | 六名玩家 |
| 7 | `Zerg` | 虫群 |
| 8 | `Abnormality` | 出逃的异想体 |

**虫群原来是 2 号槽，现在 2 号是玩家。**任何还写着 2 的地方会给队友刷虫。已改：`c_zergPlayer = 7`，`c_abnoPlayer = 8`。

8 号单独是一个 race，因为出逃的异想体要**同时**敌对虫群和全体玩家。

**继承，不要展开。**编辑器"复制单位"会把父单位的字段全量拍平进新条目——`Lob_SCV_*` 就是这么来的，一个单位 60 行。手写时用 `parent=`，条目就变成一份相对基准单位的 diff，一眼能看出改了什么。数组字段按下标覆盖：

```xml
<CUnit id="Lob_Hero_Agent" parent="Marine">
    <AbilArray index="3" Link="Repair"/>   <!-- 顶掉 Marine 的 Stimpack -->
    <WeaponArray index="0" Link="Lob_Hero_Rifle"/>
</CUnit>
```

要删掉继承来的数组项用 `<XxxArray index="N" removed="1"/>`。

**唯一必须重申的字段是 actor 的 `Model`。**暴雪的很多 actor 根本不写 `Model`——它靠 actor id 和 model id 同名来解析。继承一个"未设置"的字段，意味着子 actor 会拿自己的 id 去找模型，然后找不到。

**但 actor 不能继承具体单位的 actor。**这是实测撞出来的：

```
Scope[Lob_Hero_Agent, Unit] Unable to create unit actor
```

单位 catalog 是惰性数据，继承得很干净；**actor 是消息总线的订阅者**，而父 actor 携带的订阅是烤死在父单位名字上的。子 actor 上写 `unitName` **不会**重定向它们——`parent="Marine"` 的子 actor 仍然只监听 `UnitBirth.Marine`，我们的单位出生时没人应答，于是无法创建。

暴雪自己的 `CarrierInterceptorDummy`（`parent="Carrier"`）展示了变通办法，也顺便展示了为什么不该用它：

```xml
<On index="0" Terms="UnitBirth.CarrierInterceptorDummy"/>
<On index="1" Terms="UnitBirth.CarrierInterceptorDummy"/>
...
<On index="73" removed="1"/>
```

它得**按数组下标**逐条改写继承来的订阅。暴雪哪天调整父 actor 的事件顺序，这套下标就静默失效了。

**结论**：`CUnit` 继承具体单位（`parent="Marine"`）没问题；`CActorUnit` 只继承抽象基类（`GenericUnitStandard` / `TerranBuildingEx` / `DestructibleUnitStandard`），需要什么字段显式写。

### 依赖

地图当前依赖 `Void (Mod)`，也就是多人数据链（core + liberty + swarm + void 的 multi 部分）。

**战役单位不在里面。**`Raynor` / `RaynorCommando` 这类只存在于 `*.sc2campaign`。要用它们得在编辑器里 Map → Dependencies → Add Standard → **Void (Campaign)**。加完之后 `Lob_Hero_Agent` 的 `parent` 从 `Marine` 换成 `RaynorCommando` 就行——`RaynorCommando` 本来就是 200 血 / 护甲 1 / 只有 stop-attack-move 加一个技能，和我们要的几乎是同一个单位。

**XML 注释里不能出现 `--`**。这是 XML 规范本身的限制，不是 SC2 的。写中文破折号或者改标点。构建时 `gen_objects.py` 会解析 `UnitData.xml`，所以这类错误至少会在构建时炸出来，而不是留到游戏里。

### Attribute = 危险等级

五个危险等级就是五个原生 attribute。不另建字段、不另建表：

| 等级 | Attribute | Galaxy | 编辑器 |
|---|---|---|---|
| Zayin | `Biological` | `c_unitAttributeBiological` | |
| Teth | `Light` | `c_unitAttributeLight` | |
| HE | `Armored` | `c_unitAttributeArmored` | |
| WAW | `Psionic` | `c_unitAttributePsionic` | |
| Aleph | `User1` | `c_unitAttributeUser1` | 该槽位显示名为 "Map Object" |

显示名已经在 Text Editor 里改过，所以单位面板、tooltip、武器的加成行全都直接写 "HE" 而不是 "Armored"，一行脚本都不用。情报部 lv2 要的"头顶标注危险等级"、控制部 lv2/lv3 的"HE 级以下 / Aleph 级以下"准入，在代码侧都退化成 `Risk_Of()` 加一个比较——见 `src/galaxy/06_risk.galaxy`。

**代价是这五个 attribute 从此只有这一个含义。**任何不是异想体的东西都不能带它们，否则它会读出一个自己没有的等级。已经清掉的：

- `Lob_Device_Basic` / `Lob_Core_Basic` / `Lob_Debris_Normal` 原本带 `Armored`（＝HE）
- `Lob_SCV_*` 原本带 `Light` + `Biological`（＝Teth + Zayin）
- `Lob_Hero_Agent` 从 `Marine` 继承 `Light` + `Biological`，用 `value="0"` 显式关掉

**attribute 是一个封闭集合，共 13 个，引擎不接受第 14 个**：

```
Light  Armored  Biological  Mechanical  Robotic  Psionic  Massive
Structure  Hover  Heroic  Summoned  User1  MapBoss
```

`User1` 是单独存在的特例，**没有 User2/User3/User4**。以编辑器的定义为准，别从 `User1` 推导。

而且 **attribute 只是一个标签，不带任何值**——需要存数值的东西不能放这里。

上面五个花掉之后，我们自己还在用 `Mechanical` 和 `Structure`，剩下的每一个都对原版技能和过滤器有既有含义。所以**危险等级是最后一个能进 attribute 的标签**，之后任何"想给单位类型挂一条信息"的需求都得另找地方。

注意这也会改变原版武器的属性加成落在谁身上——"对 Armored +X" 现在是"对 HE +X"。这是个特性，不是副作用，但摆武器数值的时候要记着。

### 异想体的 per-type 数字：**说明文档就是数据源**

**危险等级只是"突破后果"，不是"管理难度"。**这两件事在中段是反相关的：许多熟练玩家宁愿拿 WAW 也不愿意拿 HE。设计层的论证见 `docs/design/agents-and-abnormalities.md` §3。

有三样东西需要**每个异想体一个数字**：Qliphoth 计数器默认值、工作偏好表、残余管理难度。attribute 是封闭的 13 个纯标签、不带值，装不下任何一样；随便挑一个没用的 `CUnit` 字段偷偷夹带数字，正是这份文档一直在警告的事。

**答案是它本来就已经写好了。**`docs/usr/abnormality/<单位id>.md` 声明一个异想体，**文件名就是 `UnitData.xml` 里的单位 id**，`tools/gen_abnormalities.py` 在构建时把里面的散文解析成 `src/galaxy/04_abno_gen.galaxy`：

| 从文档哪里 | 解析出什么 |
|---|---|
| 第一行 | 名字 |
| `## Basic Information` | 危险等级 |
| `## Details` | E-Box 速度、工作冷却 |
| `## Abnormality Basic Info` | 最大 PE-Box 数、**失败一箱的伤害类型与数值** |
| `## Outcome Ranges` | Good / Normal 的下界 |
| `## Abnormality Work Preferences` | 4 种工作 × 5 个属性等级的成功率 |
| `## Abnormality Escape Information` | Qliphoth 计数器（`X` = 没有计数器，**不等于 0**） |

**"有没有一行"就是"是不是异想体"**——不需要 `Lob_Abno_` 前缀，单位可以直接叫 `O_03_03`。

解析是刻意宽容的：这些文件是写给人看的，表格是从 wiki 粘来的参差不齐的制表符文本，章节顺序不固定，早期的可能根本没有表。缺的项走文档化的默认值，并且**在构建时报出来**，所以缺口是可见的而不是静默的零。

构建时还会**交叉核对危险等级**：文档写一份，单位的 attribute 写一份，两者必须一致。文档那份驱动准入规则，attribute 那份驱动伤害加成和单位面板，而它们不一致时两边都不会报错。这是唯一一件两台机器各自都检查不了的事。

> 注意：核对只看该 `CUnit` 上**显式写出**的 attribute，不看从 `parent` 继承来的。`parent="Critter"` 这类要把继承来的等级显式置 0。

### 编辑器会覆盖我们手写的 catalog，而且它会在失败之后覆盖

**这已经毁过一次数据了。**日志里是这样：

```
Error: Error (XML: not well-formed (invalid token)) occurred while loading Weapon
       from game data file 'GameData/WeaponData.xml'
```

编辑器**没能加载** `WeaponData.xml`，然后照样保存了——把它当时手上那点东西写了回去。结果是两把武器同时丢了 `Range`、`Backswing`、`Effect`，而且我写的多行注释被拆成了一行一个 `<!-- -->`。

游戏里的表现是：**玩家角色走到敌人面前站着不动。**没有报错，没有少按钮，只是不会打。一个没有 `Effect` 的武器开火而什么都不做，一个没有 `Range` 的武器根本不开火。

所以：

- **看见 `Error ... occurred while loading X from game data file` 就立刻停下**，别保存。那一行的意思是"接下来我保存的东西会比现在少"。
- `check_weapons` 现在会拦住没有 `Effect` 或 `Range` 的武器。它只查这两个字段，因为**只有这两个的缺席是无声的**。
- 手写 catalog 之后如果在编辑器里存过盘，`git diff` 值得扫一眼——编辑器的重排（`1.0` → `1`、注释拆行）本身无害，**跟着一起消失的字段才是**。

**它做了第二次**，同一个文件、同两把武器、同三个字段。所以这不是偶发。

而第二次带来了一条线索：**同一次保存里，编辑器自己建的 `Lob_Ordeal_Dawn_Amber_Weapon` 毫发无伤**，只有我手写的那两把被吃了。三个条目里唯一的结构差异是：

> **被吃的那两个，`<!-- -->` 写在 `<CWeaponLegacy>` 元素内部；活下来的那个没有内部注释。**

所以现在的写法是：**catalog 注释一律写在条目外面，不要写在条目里面。**这在别的文件里本来就是常态，`WeaponData.xml` 是唯一的例外，也是唯一被毁过的文件。**这是一条假说，不是结论**——下一次编辑器存盘就是检验。如果字段又没了，`check_weapons` 会立刻说出来，而假说被推翻。

#### 工作伤害：**四种，逐异想体**

`## Abnormality Basic Info` 里那行 `Work Damage / WhiteDamageTypeIcon.png White 1-2` 是被解析的。**失败一箱扣什么，是异想体的属性，不是工作的属性**：

| | 扣哪里 |
|---|---|
| **Red** | 生命 |
| **White** | SP（精神） |
| **Black** | 两者，各扣全额 |
| **Pale** | **最大生命的百分比** |

Pale 那条是唯一需要多想一层的：**勇气直接就是最大生命**，所以定额伤害会随着员工成长而相对变轻——练得越壮越免疫。Pale 用百分比，正好把这条路堵死，对老手和新人一样危险。

**员工没有倒地状态，掉到 0 就是死。**所以 Red/Black/Pale 和 White 不是同一件事的不同数字：选错工作在一个门前是一个糟糕的下午，在另一个门前是一场葬礼。这也是为什么 `-work` 的赔率旁边现在印着伤害类型——赔率不告诉你输了要付多少。

伤害走 `UnitSetPropertyFixed` 直接扣，不走战斗系统：工作伤害没有来源、没有武器、没有方向，不该被**物理**护甲减免或被任何东西反弹。

**E.G.O 护甲的落点是 `Emp_DamageScale(who, type, source)`**，返回百分比，现在恒为 100。是百分比而不是减免值，因为一件 E.G.O 抗某几种、对另几种**易伤**，所以它必须能超过 100。

它拿到 `source` 是因为**工作伤害和战斗伤害是两回事**，虽然今天走同一段算术：

| | 函数 | 是什么 |
|---|---|---|
| 工作伤害 | `Emp_WorkDamage(who, type, amount)` | 收容单元里、自愿进去的人、一个箱子的价钱。**没有东西打他。** |
| 战斗伤害 | `Emp_CombatDamage(who, type, amount)` | 出逃的异想体、考验、虫群。**有东西打他。** |

两个都调 `Emp_ApplyDamage(who, type, amount, source)`，那里只有算术，而且不该开始关心自己为什么被调用——它一旦关心，上面两个就再也分不开了。

分开不是洁癖。护甲是挡在你和某个东西之间的，而漏掉的箱子不是一个"东西"，所以 E.G.O 抗性几乎肯定不会对两者一视同仁；情报部的读数需要把它们分开报，因为"你的 Malkuth 组在门口一直掉白"和"有东西在杀你的 Malkuth 组"是两个不同的问题、两套不同的应对，加在一起两个都说不清；而**工作伤害是玩家派人时自己选的代价，战斗伤害不是**——任何以后想奖励或宽恕其中之一的东西，都得先能叫出它的名字。

`source` 和伤害类型是**两条互不相干的轴**：类型是这一下花了什么，来源是发生了什么。一扇门和一个小丑都可以收白伤。

这里有一个"引擎看起来已经有了"的陷阱，记下来免得以后重新推一遍：

```xml
<DamageTakenFraction index="Melee" value="3"/>
```

原生、真实，而且 `3` 证明**超过 1 的易伤是原生支持的**。但它的 index 是一个封闭集（`Melee` / `Ranged` / `Splash` / `Ability` / `Basic`），而这些**真实武器已经在用**了——一件靠占用其中一个来抗 Red 的 E.G.O，会连虫子的攻击一起抗。所以 Red/White/Black/Pale 需要自己的通道，具体是哪个留给做 E.G.O 的时候定。**不要现在凭空挑一个**——上一次凭空推导出 `User2` attribute 就是这么来的。

顺带：`UnitCreateEffectUnit(caster, effect, target)` 和 `UnitDamage(...)` 都存在，所以"把工作伤害交给战斗系统去走 `DamageResponse`"是一条真实的路。它的代价是 White 扣的是 Energy 而 `CEffectDamage` 只打 Life，四种伤害会变成两套不同的机制。也留到那时候再权衡。

图标名和词都能认，两者有其一即可；`Purple` 当 `Black`、`Blue` 当 `Pale`。缺这一行时默认 White 1-2 并在构建时报出来。

**还没解决的**：控制部跨部门准入引用的那个"危险"tag。它是标签不是数字，但 attribute 已经花完了——现在多了一个现成的去处（文档里加一节，生成器加几行）。

## Region

**房间用 region 画，不要用"绕着单位摆圆圈"去近似。**主休息室是有墙的房间，圆形永远不是那个形状。

早先这份文档写着"不用 Region，因为只能靠 `RegionFromId`，会把 ID 账本问题带回来"。**那条已作废**：`Regions` 也是纯 XML，

```xml
<region id="1">
    <name value="resthall_a"/>
    <shape type="circle">…</shape>
</region>
```

名字和 id 都在里面，所以和 group 完全一样——构建时解析，代码里只出现名字。`ObjectsGen_Region("resthall_a")` 直接返回 region，查不到就返回空 region（不是 null），调用方不用判空。

`Regions` 文件**要画了第一个 region 才会出现**，没有不算错误：表为空、查询返回空 region，建立在上面的东西保持惰性而不是报错。

### 命名

前缀有语义。目前：

| 前缀 | 用途 | 谁读 |
|---|---|---|
| `resthall*` | 主休息室 | `19_sector.galaxy` |

**归属靠包含关系判定，不靠名字里写玩家编号。**谁的核心站在哪个 `resthall*` 里，那个 region 就是谁的休息室。

### 范围会变

部门升级会改变休息室的作用范围，所以脚本测的**不是**画出来那个 region 本身，而是一个运行时合成的 region：初始加入画出来的那个，之后 `Sector_RestHallExtend(player, extra)` 往上叠。画出来的形状是起点，不是终点。
