"""图表代码沙箱：受限 exec 渲染 matplotlib（演示级沙箱，非安全边界）。

定位说清：这里的"沙箱"指**能力受限的执行环境**——注入 plt/pd/df、
禁 import/文件/网络/双下划线，渲染超时熔断。
真正的安全边界在 SQL 执行器（read_only 连接）；图表代码只碰内存数据和
一个指定输出路径，风险面小，演示级约束够用（简历上如实标注这一点）。
"""

import re
import threading
from pathlib import Path

FORBIDDEN = re.compile(
    r"plt\.show|import\s|open\s*\(|subprocess|os\.|socket|shutil|"
    r"__import__|__builtins__|__subclasses__|eval\s*\(|exec\s*\(", re.I)
RENDER_TIMEOUT_S = 20


def guard_code(code: str) -> str | None:
    hits = set()
    for m in FORBIDDEN.finditer(code):
        hits.add(m.group(0).strip())
    if hits:
        return f"[代码被拒绝] 出现禁止的调用 {sorted(hits)}；只能用已注入的 plt/pd/df 画图"
    return None


def _normalize(code: str) -> str:
    """工具层自愈：模型高频无视"用 OUT 变量"的指令，硬编码自己的文件名
    （实测 savefig('city_user_count_rank.png')）——不指望提示词，直接改写。"""
    if "savefig" not in code:
        return code + "\nplt.savefig(OUT, dpi=150, bbox_inches='tight')\nplt.close()"
    # 把 savefig('任意硬编码路径' 或 savefig(f'...') 一律重写到 OUT
    code = re.sub(r"savefig\s*\(\s*f?['\"][^'\"]*['\"]", "savefig(OUT", code)
    return code


def run_chart_code(code: str, df, out_path: Path) -> str | None:
    """执行画图代码；成功返回 None，失败返回模型可读错误（回喂重试用）。"""
    err = guard_code(code)
    if err:
        return err
    code = _normalize(code)

    import matplotlib
    matplotlib.use("Agg")  # 无头渲染，不弹窗
    import matplotlib.pyplot as plt
    # 中文字体在注入前配好——模型代码就不用管字体，只管画
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC"]
    plt.rcParams["axes.unicode_minus"] = False

    env = {"plt": plt, "pd": __import__("pandas"), "df": df, "OUT": str(out_path)}
    box: dict = {}

    def _worker() -> None:
        try:
            exec(compile(code, "<chart>", "exec"), env)  # noqa: S102 —— 演示级沙箱，约束见 guard
            plt.close("all")
        except Exception as exc:  # noqa: BLE001 —— 错误要回喂模型重画
            box["error"] = f"[渲染出错] {exc.__class__.__name__}: {exc}"

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    t.join(RENDER_TIMEOUT_S)
    if t.is_alive():
        return f"[渲染超时] 超过 {RENDER_TIMEOUT_S}s，检查是否死循环"
    if "error" in box:
        return box["error"]
    if not out_path.exists() or out_path.stat().st_size < 1024:
        return "[渲染出错] 代码执行完但未生成图片——必须以 plt.savefig(OUT, dpi=150, bbox_inches='tight') 收尾"
    return None
