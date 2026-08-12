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

## 构建

```
python3 tools/build_galaxy.py
```

会先从地图文件重新生成 `src/galaxy/05_objects_gen.galaxy`，再拼接出 `MapScript.galaxy`。**你在编辑器里摆完东西存盘后，代码侧要重新构建一次**，否则 group 表还是旧的（类型扫描不受影响，它是运行时的）。

## 坑

编辑器把 group 名字**连输入框里的换行一起存下来**——实测存的是 `"debris\n"` 而不是 `"debris"`。生成器已做 strip，但这类空白差异如果漏掉，会变成非常难查的名字匹配失败。

**Galaxy 没有数组初始化语法**，所以生成的每张表都是"上面一句声明 + `ObjectsGen_Init` 里一串赋值"，两者之间没有任何东西把它们绑在一起。声明了却没填的表不会编译报错——它是运行期一个 null string 被喂给 `StringLength`，崩在离病因很远的地方（region 表就这么崩过一次），或者更糟，一串空字符串参与比较、静默地什么都匹配不上（升级 ally 表就这么静默坏过）。生成器末尾的 `check_fills` 现在会挡住这种情况，**加新表时不要绕过它**。

## 自检

地图加载后打印：

```
scan: hero=N debris=N worker=N miner=N device=N | group(debris)=N
```

前几个数来自类型扫描，最后一个来自 group 表。**如果 group 那个数是 0 而 debris 不是 0，说明构建没跟上编辑器的存盘**，重跑一次构建即可。

> 如果三个数字全是 0，说明预放单位在 `InitMap()` 执行时还没创建完。届时把扫描挪到 0 秒定时触发器里即可，代码侧改一行。

## P0 灰盒摆放清单

一个扇区，先不做多扇区。

1. **地形**：一个内层房间 + 通向外层的走廊 + 外层开阔区。粗糙即可。
2. **玩家角色** `Lob_Hero_Agent`：内层放**恰好一个**。它摆在哪就在哪复活——脚本不另设复活点，因为一个会和出生点漂移开的复活点迟早会变成 bug。
3. **残骸** `Lob_Debris_*`：外层摆 **14-18 个**，堵住部分通路。数量是算出来的，不是拍的——见 `docs/design/p0-scope.md` 的场景规模检查。
4. **设备** `Lob_Device_*`：外层摆 ≥2 个，至少一个**被残骸挡住**，且至少一个**离内层 25-35 格**。
5. **虫群入口**：外层边缘 1-2 处，到设备要留出行军距离。

**摆放的设计意图**：内层、设备、虫群入口三者的距离关系，决定了"跑过去修" vs "留下来打"这个取舍存不存在。设备离内层太近，玩家就不需要做选择，P0 白测。让至少一个设备远到跑一趟要付出真实代价——角色移速 3.0，往返 30 格是 20 秒，对着 45 秒的波次周期才算数。

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

新建员工单位时要带上：

- id 以 `Lob_Emp_` 开头
- `BehaviorArray`：`Lob_Stat_Fortitude` / `Lob_Stat_Prudence` / `Lob_Stat_Temperance` / `Lob_Stat_Justice`
- `Attributes` 里 `Light` 和 `Biological` 置 0（在本作里它们是危险等级，不是体型）
- 不带武器（自卫武器是培训部 lv1 给的）

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

### 异想体的第二个坐标（**存放方式待定**）

**危险等级只是"突破后果"，不是"管理难度"。**这两件事在中段是反相关的：许多熟练玩家宁愿拿 WAW 也不愿意拿 HE。设计层的论证见 `docs/design/agents-and-abnormalities.md` §3。

还需要的两条信息：

- **残余管理难度**——知道一切之后还剩多少麻烦。WAW 残余接近 0（属性够就锁得死），HE 残余高（强制损耗躲不掉）。可能需要分档，也就是需要一个**值**。
- **危险 tag**——部门文档里控制部跨部门准入引用的那个。

**这两条都不能放 attribute。**上一节的两条限制各挡掉一半：集合封闭且已经花完，挡掉危险 tag；attribute 不带值，挡掉分档的残余难度。

也不要用"必须显示在单位面板上"来论证它该是 attribute——**三选一界面是我们自己画的对话框**，名字、编号、说明文本本来就要自己排，可见性根本不构成约束。

真正的约束是另一条：**三选一评估的是还没生成的候选。**所以它要的是**单位类型级**的数据，不是实例级的。这排除了 behavior（要有实例才能读），指向构建期解析——`gen_objects.py` 已经在读 `UnitData.xml` 并生成查表了，多一张表是既有机制的延伸，运行期零开销，且不占引擎的任何封闭预算。

**编辑器侧具体挂在哪个字段上待定**，等真的开始录异想体时再定。在那之前不要为了"先有个地方放"而随便选一个通道——上一次凭空推导出 User2 就是这么来的。

### 员工属性 = 四条 veterancy

四项属性是**同一个单位上的四个 `CBehaviorVeterancy`**。XP 的 native 按 behavior 名字寻址，所以一个单位能挂四条互不干涉的曲线，各有各的等级、各有各的每级 `Modification`、各有各的 UI。

| 属性 | behavior | 落到引擎的哪里 |
|---|---|---|
| 勇气 Fortitude | `Lob_Stat_Fortitude` | 生命 |
| 谨慎 Prudence | `Lob_Stat_Prudence` | SP（还不存在） |
| 自律 Temperance | `Lob_Stat_Temperance` | 工作速度（还不存在） |
| 正义 Justice | `Lob_Stat_Justice` | 攻速 |

**属性升级的效果写在 behavior 的 `Modification` 里，不写在 Galaxy 里。**`11_employee.galaxy` 只搬数字，从不施加数字的后果。目前四行 `Modification` 全是空的——四个落点有两个还不存在，而给另外两个编数值等于把杜撰的平衡塞进最没人会去翻的地方。

**`MinVeterancyXP` 是每级增量，不是累计值**（原版 `DehakaVeterancy` 每行都是 100，即每 100 XP 升一级）。所以设计文档里的绝对阈值要换算成差分：

```
I  0    II 30    III 45    IV 65    V 85    EX 100
         +30       +15       +20      +20      +15
```

**这套阈值在两边各写了一份**：数据侧是增量，Galaxy 侧是绝对值。改一边必须改另一边。Galaxy 侧留绝对值是因为"员工等级取属性等级之**和**"这条不变量必须和它的理由写在一起（`agents-and-abnormalities.md` §2.4），而两条规则读同一张表就不会自相矛盾。

单项默认上限 99，所以 EX（100）默认够不着——这是设计，第六级的存在意义就是给某个升级去解锁。

**员工的等级读数是 behavior，不是 UI。**`Lob_Rank_1..5` 通过 `07_buffs.galaxy` 挂上去，等级掉下来时也会跟着摘掉（培训部能把属性**调低**）。它不许带任何 `Modification`——等级是派生量。

**永久死亡不需要代码**：没有任何东西复活员工。中央本部的补充速率就是照着这个定价的。

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
