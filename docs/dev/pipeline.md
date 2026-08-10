# 开发流水线

两台机器：Linux 侧写代码，Windows 侧开编辑器 / 跑游戏。仓库是唯一的传递媒介。

## 真相源与生成物

| 路径 | 性质 | 谁维护 |
|------|------|--------|
| `src/galaxy/*.galaxy` | **真相源**，所有游戏逻辑 | 代码侧 |
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
2. **不要在编辑器的触发器模块里保存**。编辑器会用 `Triggers`（当前为空）重新生成 `MapScript.galaxy`，冲掉全部逻辑。真冲掉了也不要紧——重跑一次构建即可恢复，这正是设置构建步骤而非直接手写 `MapScript.galaxy` 的原因。

地形、doodad、单位摆放在编辑器里做是安全的，不碰这两个文件。

## 代码侧与编辑器侧的对接

逻辑不硬编码坐标，通过**命名的 region / point / unit** 对接：编辑器侧负责摆放并命名，代码侧按名字查找。具体命名约定在 P0 定下来后补充到这里。

## 数据（GameData）

见玩法基线的相关讨论，结论：

- **T1 玩法调参**（部门升级、波次、残骸档位、设备产率等）：CSV → 生成 Galaxy 常量数组，不碰数据编辑器。
- **T2 SC2 基础数值**（单位 HP、武器伤害等）：CSV → 单向生成 GameData XML，字段白名单。
- **T3 结构性数据**（Actor、Effect 树、命令卡、Requirement）：手写 XML，不进表格。

`.xlsx` 不作为真相源（二进制、无法 diff/merge），只作为编辑便利，存回 CSV。生成出来的 catalog 不要在数据编辑器里改。

以上工具在 P0 验证完核心循环之后再建——现在还没有任何数值需要调。
