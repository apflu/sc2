# 写 Galaxy 之前

> 这一页是**踩过的坑**，不是语言教程。每一条都对应至少一轮真实的调试，几条对应四轮。
> 编辑器侧的约定在 [`authoring-contract.md`](authoring-contract.md)，构建流程在 [`pipeline.md`](pipeline.md)。

## 构建

```
python3 tools/build_galaxy.py
```

会先从地图文件重新生成 `src/galaxy/05_objects_gen.galaxy` 和 `04_abno_gen.galaxy`，再按文件名顺序拼接出 `MapScript.galaxy`。任何 `void Xxx_Init ()` 会被自动收进 `InitMap()`。

**你在编辑器里摆完东西存盘后，代码侧要重新构建一次**，否则 group 表还是旧的（类型扫描不受影响，它是运行时的）。

## 语言

### 先声明后使用，而且报错报在错的地方

模块按**文件名顺序**拼接，所以一个写在自己定义上方的调用是编译错误。麻烦在于**编译器把它报在调用处、说的是 "invalid argument list"**，看起来像签名对不上，会把人引到完全错的地方去查。

这个错已经花掉四轮调试，每一次都是"某个块被挪动了"或者"调用跨了模块边界"。`build_galaxy.py` 的 `check_forward_refs` 现在会在写文件前挡住它，并直接指出是哪个函数。

**这条决定了模块编号。**`13_meltdown.galaxy` 排在 13 而不是 15，就是因为 `14_work` 要调它；它靠 `"containment" < "meltdown"` 排在收容之后，这是承重的。

### 变量名撞上类型名，报的还是 "invalid list of args"

```galaxy
int Waves_OwnerOf (unit marker) {     // 编译不过
```

`marker` 是 Galaxy 的**内置句柄类型**（`Marker()`、`MarkerGetCastingUnit()`）。所以这不是"一个叫 marker 的 unit"，是**两个类型关键字挨在一起**。

编译器说的是 `invalid list of args`，而且**指在函数头那一行**——和"先声明后使用"那个错长得一模一样，但它不是。这一条花了一次完整的跨机器往返才找到。

危险的是句柄类型，因为它们全是**普通英文名词**：

```
marker  order  wave  text  color  bank  point  sound  timer  region
trigger doodad actor byte  string unit  revealer
```

没人会把变量叫 `int`，但描述"生成点"时第一个想到的词就是 `marker`，描述"命令"时就是 `order`——**最自然的那个名字恰好是编译不过的那个。**

`build_galaxy.py` 的 `check_type_names` 现在会挡住它，并指出是哪一行哪个词。完整类型表是从 `~/SC2GameData/` 的 native 声明里扒出来的，不是手列的。

### 改名留下的引用，报的还是 "invalid args list"

同一件事的四张面孔——**报错文字和真正的原因几乎无关**：

| 真正的原因 | 编译器说 | 报在哪 | 挡它的闸 |
|---|---|---|---|
| 先用后声明 | `invalid argument list` | **调用处** | `check_forward_refs` |
| 变量名撞上类型名 | `invalid list of args` | **函数头那一行** | `check_type_names` |
| 引用了已改名/不存在的全局 | `invalid args list` | **那个值下一次被用的地方**（常常是一句拼接） | `check_globals` |
| 调用了根本不存在的函数 | `Syntax error` | **调用处**，看起来像那一行写错了 | `check_calls` |

最后一条是**删函数留下的**：`Fort_JobFor` 在一次重构里被删掉，`30_workers` 里的调用还在。

`check_forward_refs` 挡不住它，而且是**设计上挡不住**：它拿调用去比对一个**定义**，而一个哪儿都没有定义的调用，长得和调用一个 native 完全一样。所以 `check_calls` 需要一份"允许调用什么"的名单——`tools/known_calls.txt`，由 `tools/gen_known_calls.py` 从 `~/SC2GameData/mods/*/base.sc2data/TriggerLibs/` 里扒出来（4434 个），已提交，构建不依赖那个目录存在。

> 名单只取 mods 的 TriggerLibs，**不取战役地图自己的脚本**。自定义地图调不到它们，而把它们算进来只会让名单宽到能吞掉真正的拼写错误。

`gvg_abnoName` 改成 `gvg_abnoNameKey` 之后，`90_debug` 里有三行还在问旧名字，编译器指着一句字符串拼接说 "invalid args list"。

Galaxy 没有一句能读的"未声明标识符"报错，所以这个只能在构建期挡。`check_globals` 只认 `gv_` / `gvg_` 前缀——**这正是本项目全局变量的命名约定，而且从不用于别的东西**。

> 一次跨机器往返太贵，所以规则是：**同一句报错咬第二次，就不修那一例，去 `tools/` 里加一道闸。**现在这句话已经对应三道了。

### 没有数组初始化语法

所以生成的每张表都是"上面一句声明 + Init 里一串赋值"，两者之间**没有任何东西把它们绑在一起**。

声明了却没填的表不会编译报错——它是运行期一个 null string 被喂给 `StringLength`，崩在离病因很远的地方（region 表就这么崩过一次），或者更糟，一串空字符串参与比较、**静默地什么都匹配不上**（升级 ally 表就这么静默坏过，盟友传播整个没生效而没有任何报错）。

生成器末尾的 `check_fills` 现在会挡住这种情况，**加新表时不要绕过它**。

数组大小必须是**字面量**，`const int c_cellMax = 32;` 不能拿来当 `[c_cellMax]`。

### 位运算：`<<` 和 `|` 确认可用，`>>` `&` `^` `~` 没有证据

`<<` 和 `|` 在暴雪自己发布的脚本里到处都是，直接作用在 int 上并赋给 int 变量：

```galaxy
attackersLimit = 1 << diff;                                    // MeleeAI.galaxy
(1 << (c_targetFilterDead - 32)) | (1 << (c_targetFilterHidden - 32))   // NativeLib
```

光 `1 << (` 就有一万五千处。

而 `>>` `&` `^` `~`：**把暴雪发布的每个 `.galaxy` 文件 grep 一遍，没有一处 int 用法**，命中的全是注释里的散文。它们大概率能用，但**这台机器编译不了地图**，所以不要把存档格式之类的东西押在上面。要右移或掩码时，整数 `/` 和 `%` 在非负数上做同一件事，且毫无疑问：

```
v >> n   ==   v / (1 << n)          v & (2^n - 1)   ==   v % (1 << n)
```

另外有一个真正的 `bitmask` 类型，带 `BitMaskAndBitMask` / `OrBitMask` / `XorBitMask` / `Invert` / `LeftShift` / `CountOnBits` / `SetIndex` / `TrueIndex`。它是**堆对象不是值**，所以适合挂在单位上当标志位，不适合当编码器。

### `StringFind` 返回 1-based 下标，找不到返回 -1

不是 0。暴雪代码里两处都验证了：`StringSub(s, 1, found - 1)` 和 `if (found == -1)`。`02_codec.galaxy` 的 base64 解码就靠这个语义。

`StringToInt("")` 会**抛触发器错误**而不是返回 0，所以每个可选参数都得过一遍带默认值的包装（`Debug_Int`）。

## `natives.galaxy` 不是全集

`~/SC2GameData/mods/core.sc2mod/base.sc2data/TriggerLibs/` 下还有 **`natives_missing.galaxy`，另外 236 个 native**。

**只 grep `natives.galaxy` 就断言"这个 native 不存在"是错的，已经错过两次**，其中一次差点导致为每个异想体生成一个单位加 actor。至少要 `grep -rn` 整个 `TriggerLibs/`；用户能在编辑器里看到的东西一定存在于 `NativeLib.TriggerLib`。

几个对本项目重要的，全在 `natives_missing.galaxy` 里：

| | |
|---|---|
| `UnitAbilityAdd/Remove/ChangeLink` | 运行时增删改技能 |
| `UnitSetInfoButtonTooltip` | **按单位实例改按钮 tooltip**（图鉴整个建立在这上面） |
| `UnitGet/SetAttributePoint` | 直接读写属性点数，不需要载体 buff |
| `DataTableInstance*` | 实例级数据表 |

> **在 `NativeLib.TriggerLib` 里能看到，不等于能调。**没有 `<FlagNative/>` 的是编辑器侧的构造，手写 Galaxy 调不了——`BankPreload` 就是这样一个，两个参数都带 `<ParamFlagPreload/>`，它是编译期声明。

## 显示给玩家的文本里 `<` `>` 会被当成 markup

`<s>` 是字体样式标签，而一个没有 `val` 的样式标签等于在找名字为空的样式——那就是 `TextError: 无法找到字体样式[]` 的来源。

旧的聊天版 `-help` 印的是 `-stat <s> <v>`，所以**每次有人打 `-help` 都会报一次**，而这个错查了很久，因为它看起来和文字内容毫无关系。

占位符写成 `NAME` / `VALUE`；异想体文档里 wiki 留下的 `<name>` 由生成器转义成 `&lt;name&gt;`。合法的只有 `<n/>` 和 `<c val="...">`。

## XML 注释里不能有 `--`

`<!-- ... -- ... -->` 不是合法 XML。这条踩过五次以上，每次都是构建时 `check_catalogs` 解析八个 catalog 报出来。要写破折号就用 em dash。

## 自检

地图加载后往**调试区**打印（不是字幕区——它是开发者文本）：

```
scan: hero=N debris=N worker=N miner=N device=N | group(debris)=N
```

同一行随时可以用 `-scan` 再要一次。

前几个数来自类型扫描，最后一个来自 group 表。**如果 group 那个数是 0 而 debris 不是 0，说明构建没跟上编辑器的存盘**，重跑一次构建即可。

> 如果三个数字全是 0，说明预放单位在 `InitMap()` 执行时还没创建完。届时把扫描挪到 0 秒定时触发器里即可，代码侧改一行。

## 一条通用的
每当一类 bug 花掉不止一轮调试，**加一个构建期检查，而不是修那一个实例**。现在有八个，全是这么来的：

| | 挡什么 |
|---|---|
| `check_fills` | 声明了却没填的生成表 |
| `check_forward_refs` | 先用后声明 |
| `check_type_names` | 变量名撞上 Galaxy 类型名 |
| `check_globals` | 引用了已改名/不存在的全局 |
| `check_calls` | 调用了哪儿都没定义的函数 |
| `check_catalogs` | catalog XML 解析不了（含注释里的 `--`） |
| `check_catalog_fields` | **字段名是真的，但放错了地方** |
| `check_weapons` | 武器丢了 `Effect` 或 `Range`（编辑器覆盖过 catalog） |

中间四个挡的是**同一件事的四张面孔**，见上面那张表。

## catalog 字段放错地方，游戏里没有任何声音

```xml
<CBehaviorBuff id="Lob_Mind_White">
    <Modification>
        <DamageResponse .../>      <!-- 字段是真的，位置是错的 -->
```

`DamageResponse` 挂在**行为本体下**，和 `Modification` 平级；而看起来是它孪生兄弟的 `DeathResponse` **就在 `Modification` 里面**。两个名字都没有任何一处暗示这件事，游戏也不带 schema。

**编辑器只会在日志里印一行 `Unable to find field`，然后把这个字段直接忽略。**于是单位安静地没有你给它的那个东西，而"没生效"和"机制没做对"在游戏里长得一模一样。

`check_catalog_fields` 用的是暴雪自己的数据当白名单：`tools/catalog_fields.txt` 收了原版每一个 `(类, 父元素, 子元素)` 三元组，`tools/gen_catalog_fields.py` 生成，已提交，构建不依赖 `~/SC2GameData/`。

比对**按类族**而不是按精确类名（`CBehaviorAttribute` → `CBehavior`），**父元素名也一起模糊**——因为最外层的父元素就是条目本身，`InfoIcon` 挂在 `CBehaviorAttribute` 上会读成 `CBehavior/CBehaviorAttribute/InfoIcon`，而原版只演示过 `CBehavior/CBehaviorBuff/InfoIcon`。只模糊一头，基类字段挂在冷门子类上就会全被判成瞎编。原版从没出现过的类整个跳过。**名单故意放宽**：误报会挡住本来能跑的构建，比漏掉一个冷门字段更糟。

> 这几道闸都会报行号，所以剥注释和字符串时**必须等长替换成空格**，不能删掉——删掉会让第一个注释之后的所有偏移量整体错位，指向一行完全没问题的代码。这比没有闸更糟。`blanked()` 就是干这个的。
