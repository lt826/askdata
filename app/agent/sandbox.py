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
    """画图代码静态安检：正则扫出禁止的调用即拒绝。

    禁止清单：import（plt/pd 已注入无需引入）、open/subprocess/os./socket/
    shutil（文件与网络）、eval/exec/__ 双下划线（逃逸）、plt.show（无头
    环境会报错）。
    返回 None=通过；字符串=拒绝原因（回喂模型重画用）。
    """
    hits = set()
    for m in FORBIDDEN.finditer(code):
        hits.add(m.group(0).strip())
    if hits:
        return f"[代码被拒绝] 出现禁止的调用 {sorted(hits)}；只能用已注入的 plt/pd/df 画图"
    return None


def _normalize(code: str) -> str:
    """画图代码"工具层自愈"：执行前强制改写两类问题（badcase 4 的修法）。

    模型高频无视"必须 savefig(OUT)"的指令、硬编码自己的文件名——提示词
    管不住生成内容里的具体参数（第 4 次实锤），所以不靠说服靠改写：
      1. 代码里没有 savefig → 末尾补一行标准收尾
      2. savefig('任何硬编码路径') → 正则一律重写为 savefig(OUT
    """
    if "savefig" not in code:
        return code + "\nplt.savefig(OUT, dpi=150, bbox_inches='tight')\nplt.close()"
    # 把 savefig('任意硬编码路径' 或 savefig(f'...') 一律重写到 OUT
    code = re.sub(r"savefig\s*\(\s*f?['\"][^'\"]*['\"]", "savefig(OUT", code)
    return code


def run_chart_code(code: str, df, out_path: Path) -> str | None:
    """在受限环境里执行模型生成的 matplotlib 代码，落一张 PNG。

    受限点：plt/pd/df 三个变量预先注入（模型代码免 import）、中文字体
    预先配好、guard_code 安检、_normalize 改写、线程 + 20s 超时。
    四个失败哨兵：静态违禁 / 运行时异常 / 超时 / **执行完但目标文件
    不存在**（防"跑成功了但图画到别的目录"的静默失败）。

    参数: code 模型生成的画图代码；df 查询结果 DataFrame；out_path 目标 PNG 路径
    返回:  None=成功（out_path 已落盘）；字符串=失败原因（喂给重试）
    """
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
