# 编辑器侧 ↔ 代码侧 接口约定

编辑器侧负责**空间**（地形、房间、对象摆在哪），代码侧负责**行为**。这份文档是两者之间的唯一契约。

## 两条通道

| 通道 | 表达什么 | 预放对象 | 运行时生成 |
|------|---------|:-------:|:---------:|
| **单位类型** `Lob_Debris_Normal` | 这东西**是什么** | ✅ | ✅ |
| **编辑器 group** `debris` | 属于**哪个具名子集**（扇区、初始簇） | ✅ | ✗ |

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
3. **残骸** `Lob_Debris_*`：外层摆 8-12 个，堵住部分通路。
4. **设备** `Lob_Device_*`：外层摆 2 个，至少一个**被残骸挡住**。
5. **虫群入口**：外层边缘 1-2 处。

**摆放的设计意图**：内层、设备、虫群入口三者的距离关系，决定了"跑过去修" vs "留下来打"这个取舍存不存在。设备离内层太近，玩家就不需要做选择，P0 白测。让至少一个设备远到跑一趟要付出真实代价。

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

### 依赖

地图当前依赖 `Void (Mod)`，也就是多人数据链（core + liberty + swarm + void 的 multi 部分）。

**战役单位不在里面。**`Raynor` / `RaynorCommando` 这类只存在于 `*.sc2campaign`。要用它们得在编辑器里 Map → Dependencies → Add Standard → **Void (Campaign)**。加完之后 `Lob_Hero_Agent` 的 `parent` 从 `Marine` 换成 `RaynorCommando` 就行——`RaynorCommando` 本来就是 200 血 / 护甲 1 / 只有 stop-attack-move 加一个技能，和我们要的几乎是同一个单位。

**XML 注释里不能出现 `--`**。这是 XML 规范本身的限制，不是 SC2 的。写中文破折号或者改标点。构建时 `gen_objects.py` 会解析 `UnitData.xml`，所以这类错误至少会在构建时炸出来，而不是留到游戏里。

## 扇区划分（P0.5+）

用 **group** 来划，不用编辑器 Region——Region 只能靠 `RegionFromId`，会把 ID 账本问题带回来，而 group 有名字，且名字由我们自己定。
