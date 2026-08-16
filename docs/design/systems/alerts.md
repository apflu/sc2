# 提示（Alert）

> 代码在 `04_alerts.galaxy`，id 表由 `tools/gen_alerts.py` 生成到 `tools/stock_alerts.txt` 再到 `src/galaxy/03_alerts_gen.galaxy`。

## 原版的 321 条全部关掉

这个数字不是估的：把地图依赖链上（core → liberty → swarm → void，加 Liberty 战役）所有 `AlertData.xml` 里的 `CAlert` 数一遍，321 条。

**其中几乎没有一条是在说这张地图里会发生的事。**"你的部队正在受到攻击"是一句对战的话；一次收容班次是由突破、融毁、大门降下、有人崩溃构成的，每一件都想要自己的那一句。

关掉不是为了清静，是因为**提示的价值全部来自它稀有**。321 条继承来的提示把这份预算花在了什么都不是的地方，等我们自己的第一条出现时，它已经没有钱可花了。

## 做法：`UISetAlertTypeVisible`

```galaxy
UISetAlertTypeVisible(PlayerGroupAll(), "AttackUnitAlly", false);
```

这是**暴雪自己的用法**——`zzerus03` 就是用它在"玩家本来就该在掉单位"的那一段里把 `AttackUnit_Zerg` 静音的。按**提示类型**、按**玩家组**，正好是想要的粒度。

考虑过但没用的另一条路：在地图的 `AlertData.xml` 里覆盖根部的 `<CAlert default="1">`，把 `Display` 全置 0。一行就够，还能顺带盖住将来新增的原版提示——但它**会一起盖住我们自己的**，而且这台机器编译不了地图，验证不了根 default 能不能被地图覆盖。所以选了可验证的那条。

## 要改的只有一个函数

```galaxy
bool Alerts_Keep (string alert) {
    return false;
}
```

**其余全是生成的。**关于提示的所有决定都在这一个函数里，所以"我们保留了什么"读起来是一条条理由，而不是一张 321 行表格里的若干处缺席。

现在是空的：没有哪条原版提示被证明值它占的那一行，而加回来是一个条件的事。

## id 表为什么是生成的、又为什么是提交的

- **生成**：手抄 321 个字符串，抄错一个就是一条永远静不下来的提示，而且没有任何报错。
- **提交**：构建不能依赖 `~/SC2GameData/` 存在。和 `tools/known_calls.txt` 同一个理由，同一套做法。

`gen_alerts.py` 直接运行时从游戏数据刷新 txt；构建时它只读 txt。**只在地图依赖变了的时候需要重跑。**

不在依赖链里的 mod 的提示 id 一律不收：一条不可能触发的提示不值得点名，而点它等于向引擎打听一个没有加载的东西。

## 我们自己的提示

`Lob_` 前缀。生成器会把它们从表里剔掉，`Alerts_IsOurs` 再拦一道——**一次重建不该需要记得自己关过谁。**

目前只有编辑器里建的 `Lob_TestAlert`。
