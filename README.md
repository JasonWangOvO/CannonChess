# CannonChess

炮棋 Python 原型，当前实现双人本地对战和图形界面。

## 运行

无需第三方依赖，使用 Python 3.10 标准库。

```bash
python run_game.py
```

也可以安装为包后运行：

```bash
python -m cannonchess
```

## 当前功能

- 程序启动后进入模式选择。
- 双人本地对战可用，同一鼠标轮流移动。
- 每局随机生成 5-10 范围内的矩形棋盘，棋子数量为短边长 + 1。
- A 方使用克莱因蓝方块，B 方使用勃艮第红方块。
- 障碍物为黑色，空地为白色。
- 选中棋子后以淡黄色提示可移动位置。
- 支持悔棋、投降、重新开始。
- 支持胜负判定和 50 回合无吃子平局判定。

## 工程结构

- `src/cannonchess/core.py`：纯规则逻辑。
- `src/cannonchess/gui.py`：Tkinter 图形界面。
- `src/cannonchess/agents.py`：AI 接口预留。
- `tests/test_core.py`：核心规则测试。
