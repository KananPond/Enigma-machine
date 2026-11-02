# ENIGMA · 恩尼格码模拟器

一个用 Python 编写的**恩尼格码（Enigma）加密机模拟器**，带完整的桌面 GUI 界面。
模拟的核心严格遵循真实机器的电气与机械行为：转子步进、**双步进（double stepping）**、
转子环设定（Ringstellung）、接线板（Steckerbrett）以及反射器（Umkehrwalze）。

> A faithful Python simulation of the Enigma cipher machine with a full desktop
> GUI: rotor stepping, double stepping, ring settings, plugboard and reflector.

![Enigma simulator](docs/screenshot.png)

---

## 功能特性

| 功能 | 说明 |
| --- | --- |
| 完整机器模型 | 三转子（I–VIII）+ 反射器（A/B/C）+ 接线板，电气路径逐跳可追溯 |
| 真实步进规则 | 按键前步进、双步进异常、转子缺口（turnover notch）触发 |
| 交互式 GUI | 灯板、键盘、三个转子控制面板、接线板编辑器、报文加解密 |
| 信号路径显示 | 实时显示电流经过 插头板 → 右转子 → 中转子 → 左转子 → 反射器 → 返回 的每一跳 |
| 报文分组 | 按历史惯例可把密文按 5 个字母分组显示 |
| 参考向量测试 | 26 个单元测试，覆盖公开的历史参考向量 |

## 快速开始

项目使用**虚拟环境**管理依赖（运行时零第三方依赖，只用标准库 `tkinter`）。

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run.py
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run.py
```

> Linux 上若缺少 tkinter：`sudo apt install python3-tk`。

可选的开发/测试工具：

```powershell
python -m pip install -r requirements-dev.txt
pytest
```

## 界面说明

* **机器设置**（顶部）
  * *反射器 UKW*：选择 A / B / C。B 是绝大多数真实战时电文使用的反射器。
  * *三个转子*：下拉框选择转子类型（I–VIII），`▲ ▼` 调整 **环设定（Ring）** 与
    **窗口位置（Position）**。转子位于缺口（notch）上时，右侧 `NOTCH` 指示灯会亮起。
  * 选择一个已经在机器中的转子时，两个转子会**自动互换**（同一转子不能装两次）。
* **插头板（Steckerbrett）**：先点一个字母，再点第二个字母即接一根电缆；再次点击已接线的字母可拔掉电缆。
  真实机器最多 10 根电缆，且同一字母不能重复使用。
* **灯板 / 键盘**：点击键盘按键，或直接用**真实键盘**敲字母，机器即会步进并点亮对应灯泡。
* **报文面板**：输入明文 → `Encipher / Decipher`。由于恩尼格码密码是**互反的**，
  用相同设置解密密文会得到原文；`Group in fives` 按五字母分组显示。
* **信号路径**：显示上一次按键时电流在机器内部的完整路径。

## 机器模型

信号路径（每次按键）：

```
插头板 → 右转子 → 中转子 → 左转子 → 反射器 → 左转子 → 中转子 → 右转子 → 插头板
```

* **转子变换**：转子接线为 `W`，窗口位置为 `p`，环设定为 `r`，则有效偏移量为
  `e = (p − r) mod 26`；正向（自右向左）变换为 `W[(l + e) mod 26] − e`，
  反向为 `W⁻¹[(l + e) mod 26] − e`。
* **步进**：每次按键**先**步进。右转子总是步进；右转子处于缺口、或中转子自身处于缺口时，
  中转子步进；中转子处于缺口时左转子随之中转子一起步进 —— 这就是著名的**双步进**。
* **缺口（turnover letters）**：I→Q、II→E、III→V、IV→J、V→Z，VI/VII/VIII→Z+M。
  缺口位于字母环上，因此改变环设定**不会**改变步进节奏。
* **互反性**：反射器没有自连点，因此没有接线板时任何字母都不会被加密成它自己；
  同一台机器同一设置下，加密与解密互为逆运算。

## 正确性验证

`tests/` 中的测试全部基于公开的历史参考向量（Wikipedia / Crypto Museum）：

| 设置 | 明文 | 期望密文 |
| --- | --- | --- |
| 转子 I-II-III，反射器 B，环设定 AAA，起始 AAA | `AAAAA` | `BDZGO` |
| 同上，26 个字母（会触发一次转子交接） | `A`×26 | `BDZGOWCXLTKSBTMCDLPBMUQOFX` |
| 同上，环设定 `BBB`（即 02-02-02） | `AAAAA` | `EWTYX` |
| 加密后再解密（互反性） | `ATTACKATDAWN` | 还原原文 |
| Wikipedia 的标准步进序列 | — | `ADU → ADV → AEW → BFX → BFY` |

运行测试：

```powershell
python -m unittest discover -s tests -v     # 仅用标准库
pytest                                       # 使用 pytest
```

## 项目结构

```
Enigma machine/
├── enigma/                 # 与界面无关的模拟核心
│   ├── data.py             # 转子接线、缺口、反射器接线表
│   ├── plugboard.py        # Steckerbrett（插头板）
│   ├── machine.py          # 机器模型、步进规则、加解密
│   └── message.py          # 报文规范化与五字母分组
├── enigma_gui/             # Tkinter 桌面界面
│   ├── theme.py            # 配色与字体
│   ├── widgets.py          # 灯板、键盘、转子面板、插头板、信号路径
│   └── app.py              # 主窗口
├── tests/                  # unittest 测试（参考向量）
├── docs/screenshot.png
├── run.py                  # 程序入口
├── requirements.txt        # 运行时依赖（空：仅标准库）
├── requirements-dev.txt    # 开发依赖（pytest）
└── pyproject.toml
```

核心库可以脱离界面单独使用：

```python
from enigma import EnigmaMachine, Plugboard

# 参考向量设置：转子 I-II-III，反射器 B，无接线板，起始 AAA
eng = EnigmaMachine.create(
    rotor_order=("I", "II", "III"),
    reflector="B",
    plugboard=Plugboard(),
    ring_settings=("A", "A", "A"),
    positions=("A", "A", "A"),
)
print(eng.encrypt("AAAAA"))   # -> BDZGO

# 带接线板的日常设置
eng = EnigmaMachine.create(
    rotor_order=("I", "II", "III"),
    reflector="B",
    plugboard=Plugboard.parse("AV BS CG"),
)
print(eng.encrypt("ATTACKATDAWN"))
```

## 数据来源

* 转子接线、缺口位置、反射器接线：Wikipedia《Enigma machine》转子表与
  “Turnover notch positions”，以及 [Crypto Museum](https://www.cryptomuseum.com/crypto/enigma/)。
* 参考向量与步进序列：Wikipedia 的 “Normalized Enigma sequences” 与相关密码学文献。
* 单元测试会校验：每台转子的接线是字母表的排列；每个反射器是**无自连点的对合**（involution）。

## 说明与已知限制

* 模拟的是三转子的陆海军用恩尼格码（M3）。四转子 M4（薄反射器 Beta/Gamma）未纳入界面，
  但 `enigma/data.py` 中保留了 `B thin` / `C thin` 两款薄反射器接线。
* 历史上真实电文会先用转子/插头板设置加密一个消息密钥，再换新设置加密正文；
  本程序只提供单机操作与整段加解密，不含密钥流程（Kenngruppenverfahren）。
* 界面为单屏布局，窗口会自动适配屏幕尺寸。

## 许可

MIT
