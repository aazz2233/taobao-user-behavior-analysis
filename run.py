"""免安装入口：``python run.py <build|analyse|charts|all|info> [选项]``。

仓库路径含中文时，``pip install -e .`` 生成的 .pth 会被 Windows 的 site 模块
按本地编码读取而报错（UnicodeDecodeError）。这个脚本把 ``src`` 直接加入
``sys.path``，无需安装即可运行，也可在纯 ASCII 路径下照常使用。
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from taobao_analysis.cli import main  # noqa: E402  (必须在 sys.path 调整之后导入)

if __name__ == "__main__":
    raise SystemExit(main())
