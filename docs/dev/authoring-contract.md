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
