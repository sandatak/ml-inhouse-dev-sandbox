"""オープンロジ出荷依頼CSV作成のローカル完結モック（Tkinter GUI）。

業務ロジックはこのファイルに持たない。build_plans_csv.py と build_opl_csv.py を
サブプロセスとして順に呼ぶだけのラッパーで、ロジックの実体は2スクリプト側のみに存在する。
通信なし・標準ライブラリのみ（tkinterも標準ライブラリ）。

GUIを開かずに検証したい場合は --selftest を付けると、mock/input・sample の
ダミーデータでパイプライン全体を一度通して結果を標準出力に表示する。
"""
import argparse, os, subprocess, sys, tkinter as tk
from tkinter import filedialog, scrolledtext

HERE = os.path.dirname(os.path.abspath(__file__))
PLANS_SCRIPT = os.path.join(HERE, "build_plans_csv.py")
OPL_SCRIPT = os.path.join(HERE, "build_opl_csv.py")


def run(args):
    r = subprocess.run([sys.executable] + args, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("オープンロジ出荷依頼CSV作成（ローカル完結モック）")
        self.geometry("760x620")
        self.vars = {}
        self._build_plans_section()
        self._build_opl_section()
        self._build_log()
        self._bring_to_front()

    def _bring_to_front(self):
        # Terminalから起動した場合、macOSはウィンドウを自動で最前面に出さないことがあるため明示的に行う
        self.lift()
        self.attributes("-topmost", True)
        self.after(300, lambda: self.attributes("-topmost", False))
        self.focus_force()

    def _pick(self, key, is_save, filetypes):
        path = (filedialog.asksaveasfilename(filetypes=filetypes)
                if is_save else filedialog.askopenfilename(filetypes=filetypes))
        if path:
            self.vars[key].set(path)

    def _row(self, parent, label, key, r, is_save=False, filetypes=(("CSV", "*.csv"), ("All", "*.*"))):
        tk.Label(parent, text=label, width=16, anchor="w").grid(row=r, column=0, sticky="w", padx=4, pady=2)
        var = tk.StringVar()
        self.vars[key] = var
        tk.Entry(parent, textvariable=var, width=58).grid(row=r, column=1, padx=4)
        tk.Button(parent, text="選択", command=lambda: self._pick(key, is_save, filetypes)).grid(row=r, column=2, padx=4)

    def _build_plans_section(self):
        f = tk.LabelFrame(self, text="① 商品情報CSVの作成（build_plans_csv.py）", padx=8, pady=8)
        f.pack(fill="x", padx=8, pady=6)
        self._row(f, "同梱物マスタ", "items", 0)
        self._row(f, "優先順位ファイル", "priority", 1, filetypes=(("Text", "*.txt"), ("All", "*.*")))
        self._row(f, "緩衝材ルールJSON", "cushion", 2, filetypes=(("JSON", "*.json"), ("All", "*.*")))
        self._row(f, "出力先", "plans_out", 3, is_save=True)
        tk.Button(f, text="商品情報CSVを作成 →", command=self.on_run_plans).grid(row=4, column=1, pady=6, sticky="w")

    def _build_opl_section(self):
        f = tk.LabelFrame(self, text="② 出荷依頼CSVの作成（build_opl_csv.py）", padx=8, pady=8)
        f.pack(fill="x", padx=8, pady=6)
        self._row(f, "配送先回答CSV", "bdash", 0)
        self._row(f, "購入データCSV", "orders", 1)
        self._row(f, "突合リストCSV", "konpo", 2)
        self._row(f, "商品情報CSV", "plans_in", 3)
        tk.Label(f, text="配送便指定", width=16, anchor="w").grid(row=4, column=0, sticky="w", padx=4)
        self.delivery = tk.StringVar(value="4")
        box = tk.Frame(f)
        box.grid(row=4, column=1, sticky="w")
        tk.Radiobutton(box, text="4: 佐川（既定）", variable=self.delivery, value="4").pack(side="left")
        tk.Radiobutton(box, text="2: ネコポス", variable=self.delivery, value="2").pack(side="left")
        self._row(f, "出力先", "opl_out", 5, is_save=True)
        tk.Button(f, text="出荷依頼CSVを作成 →", command=self.on_run_opl).grid(row=6, column=1, pady=6, sticky="w")

    def _build_log(self):
        f = tk.LabelFrame(self, text="実行ログ・検算レポート", padx=8, pady=8)
        f.pack(fill="both", expand=True, padx=8, pady=6)
        self.log = scrolledtext.ScrolledText(f, height=14)
        self.log.pack(fill="both", expand=True)

    def append_log(self, text):
        self.log.insert("end", text + "\n")
        self.log.see("end")

    def on_run_plans(self):
        v = self.vars
        if not all(v[k].get() for k in ("items", "priority", "cushion", "plans_out")):
            self.append_log("[エラー] ①の入力・出力先をすべて指定してください")
            return
        code, out = run([PLANS_SCRIPT, "--items", v["items"].get(), "--priority", v["priority"].get(),
                          "--cushion-rules", v["cushion"].get(), "--out", v["plans_out"].get()])
        self.append_log(out)
        if code == 0:
            self.vars["plans_in"].set(v["plans_out"].get())
            self.append_log("→ ①完了。②の「商品情報CSV」欄に自動セットしました")

    def on_run_opl(self):
        v = self.vars
        if not all(v[k].get() for k in ("bdash", "orders", "konpo", "plans_in", "opl_out")):
            self.append_log("[エラー] ②の入力・出力先をすべて指定してください")
            return
        code, out = run([OPL_SCRIPT, "--bdash", v["bdash"].get(), "--orders", v["orders"].get(),
                          "--konpo", v["konpo"].get(), "--plans", v["plans_in"].get(),
                          "--delivery", self.delivery.get(), "--out", v["opl_out"].get()])
        self.append_log(out)
        if code == 0:
            self.append_log("→ ②完了。出荷依頼CSVを出力しました")


def selftest():
    mock = os.path.join(HERE, "mock")
    sample = os.path.join(HERE, "sample")
    out_dir = os.path.join(mock, "output")
    os.makedirs(out_dir, exist_ok=True)
    plans_out = os.path.join(out_dir, "商品情報.csv")
    opl_out = os.path.join(out_dir, "出荷依頼_mock.csv")

    print("=== ① 商品情報CSVの作成 ===")
    code, out = run([PLANS_SCRIPT, "--items", os.path.join(sample, "同梱物マスタ.csv"),
                      "--priority", os.path.join(sample, "優先順位.txt"),
                      "--cushion-rules", os.path.join(sample, "緩衝材ルール.json"),
                      "--out", plans_out])
    print(out)
    if code != 0:
        sys.exit("①が失敗したため中断")

    print("=== ② 出荷依頼CSVの作成 ===")
    code, out = run([OPL_SCRIPT, "--bdash", os.path.join(mock, "fixtures", "配送先回答.csv"),
                      "--orders", os.path.join(mock, "fixtures", "購入データ.csv"),
                      "--konpo", os.path.join(mock, "fixtures", "突合リスト.csv"),
                      "--plans", plans_out, "--delivery", "4", "--out", opl_out])
    print(out)
    if code != 0:
        sys.exit("②が失敗したため中断")
    print(f"出力確認 → {opl_out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true", help="GUIを開かずmock/inputとsampleでパイプライン全体を検証")
    a = ap.parse_args()
    if a.selftest:
        selftest()
    else:
        App().mainloop()
