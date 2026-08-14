# 开发流水线

两台机器：Linux 侧写代码，Windows 侧开编辑器 / 跑游戏。仓库是唯一的传递媒介。

## 真相源与生成物

| 路径 | 性质 | 谁维护 |
|------|------|--------|
| `src/galaxy/*.galaxy` | **真相源**，所有游戏逻辑 | 代码侧 |
| `src/strings/enUS.txt` | **真相源**，所有玩家可见文本 | 代码侧 |
| `enUS.SC2Data/LocalizedData/GameStrings.txt` | 半生成物：`Lob/` 命名空间由构建覆盖，其余原样保留 | 两边 |
| `<其他语言>.SC2Data/LocalizedData/GameStrings.txt` | 翻译，**构建永不触碰** | 编辑器 / 译者 |
| `LobotomyShiphold.SC2Map/MapScript.galaxy` | **生成物**，已提交 | `tools/build_galaxy.py` |
| `LobotomyShiphold.SC2Map/Triggers` | 保持为空 | 不使用触发器 GUI |
| `LobotomyShiphold.SC2Map/t3*`, `MapInfo`, doodad/单位摆放 | 地形与空间布局 | 编辑器侧 |

构建：

```
python3 tools/build_galaxy.py
```

模块按**文件名排序**拼接，所以用数字前缀控制声明顺序（Galaxy 要求函数先定义后使用）。任何模块里形如 `void Xxx_Init ()` 的函数会被自动收集，按模块顺序在 `InitMap()` 里调用。

## 两条纪律

1. **不要手改 `MapScript.galaxy`**。它每次构建都会被整体覆盖。
2. **动过触发器之后保存，会重新生成 `MapScript.galaxy`**，冲掉全部逻辑。重跑一次构建即可恢复——这正是设置构建步骤而非直接手写 `MapScript.galaxy` 的原因。

   触发条件是**碰了触发器模块**，不是每次保存。**编辑 AI 也算**，因为编辑器会为 AI 生成对应的触发器。只改地形、单位摆放、数据编辑器的保存不会重新生成。

   冲掉之后不只是"少了我们的代码"：编辑器会按它内存里的状态重建，**包括把已经删掉的 Melee Initialization 塞回来**（于是玩家会拿到对战初始资源和农民）。所以动过触发器或 AI 之后，重新构建是必须的。

地形、doodad、单位摆放、数据编辑器在编辑器里做是安全的，不碰这两个文件。

## 玩家可见文本一律走 key

**任何玩家能看到的字符串都写在 `src/strings/enUS.txt`，代码里只出现 key。**

行内英文是一份已经丢掉的翻译：找不到、交不出去、等到想加第二种语言的那天，它变成在二十六个模块里翻找。

```galaxy
ObjectiveSetName(obj, StringExternal("Lob/Objective/Energy/Name")
                      + StringToText("  (37/200)"));
```

`tools/gen_strings.py` 把这些合并进地图的 enUS `GameStrings.txt`：**只覆盖 `Lob/` 命名空间**，数据编辑器写的那一百多行 `Abil/Name`、`Button/Tooltip` 原样读回写出。别的语言的文件构建从不写——**加一种语言就是往那儿放一个文件，仅此而已**。

两条检查，因为它替掉的失败模式是无声的：Galaxy 引用了一个没定义的 `Lob/` key，游戏里渲染出来是**什么都没有**，看起来像布局 bug 而不是缺字符串。

| | |
|---|---|
| 引用了但没定义 | **构建报错** |
| 定义了但没被引用 | 警告（key 也可能是拼出来的，静态看不见） |

扫描认的是**所有 `"Lob/..."` 字面量**，不只是 `StringExternal(...)` 里那些——一个 key 被交给 `Quest_Declare` 存进表、三个函数之后才取出来用，它一样是 key。只认直接调用的第一版把三十六个活着的任务标题报成了死键。

拼接用的前缀（`"Lob/Dept/Name/" + 部门 id`）两边都不算：它不是 key，也不能证明哪个 key 活着。

**调试输出故意不走这条路。**`-quest`、`-fort`、F12 那些是开发者文本，翻译它们等于让译者去渲染一条只有我会看的消息。

> Galaxy 有 `StringToText` 而**没有 `TextToString`**。本地化字符串是单向的——一旦某个读数需要它，那一整行就得全程按 `text` 拼。`Debug_SayText` 就是为此存在的。

## 编辑器生成的脚本（AI 模块）

编辑器的 AI 模块会生成 `aiXXXXXXXX.galaxy`，并往 `MapScript.galaxy` 里塞 `include` 和 `InitCustomAI()`。本构建整个覆盖那个文件，因此**这些接线会被丢掉**——而且丢得无声无息，因为一个没被 include 的脚本只是个没人用的文件，不是编译错误。

构建现在检测到 `ai*.galaxy` 会打警告。真要用编辑器 AI 的话，得让 `tools/build_galaxy.py` 负责发射 include 与 `InitCustomAI()`。

## 代码侧与编辑器侧的对接

逻辑不硬编码坐标，通过**命名的 region / point / unit** 对接：编辑器侧负责摆放并命名，代码侧按名字查找。具体命名约定在 P0 定下来后补充到这里。

## 数据（GameData）

见玩法基线的相关讨论，结论：

- **T1 玩法调参**（部门升级、波次、残骸档位、设备产率等）：CSV → 生成 Galaxy 常量数组，不碰数据编辑器。
- **T2 SC2 基础数值**（单位 HP、武器伤害等）：CSV → 单向生成 GameData XML，字段白名单。
- **T3 结构性数据**（Actor、Effect 树、命令卡、Requirement）：手写 XML，不进表格。

`.xlsx` 不作为真相源（二进制、无法 diff/merge），只作为编辑便利，存回 CSV。生成出来的 catalog 不要在数据编辑器里改。

以上工具在 P0 验证完核心循环之后再建——现在还没有任何数值需要调。
