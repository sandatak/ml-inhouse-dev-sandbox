"""商品情報CSV（build_opl_csv.py の --plans 入力）を、構造化済みの同梱物マスタ・緩衝材ルール・優先順位から機械的に組み立てる。

これはAI（Claude）が毎回「文章を読んで品名・緩衝材を判断する」工程を置き換えるための本番スクリプト。
前提：同梱物リストの構造化（AIDごとに実物を列挙する）と、優先順位の確定（配送便と同様、ユーザーが案件ごとに決める運用判断）は
このスクリプトの外側（＝人間、または案件登録時の一回限りの作業）で終わらせておく。ここから先に解釈の余地は残さない。

入力:
  --items          同梱物マスタCSV（AID, プラン, 商品ID, 企画名, 同梱物）
                    同梱物は "|" 区切りで実物を列挙（例: ブロマイド|チェキ|アクリルキーホルダー）
  --priority       優先順位ファイル（AIDを1行1件、優先度の高い順）。配送便指定と同じく人が確定した運用上の決定
  --cushion-rules  緩衝材ルールJSON（[{"keyword":..,"flag":..,"material":..}, ...]）
                    同梱物のいずれかにkeywordが含まれる最初のルール（ファイル先頭ほど優先）を適用
  --name-template  商品名テンプレート。{plan}=プラン名, {campaign}=企画名（既定: "【{plan}プラン】{campaign}特典"）
出力:
  --out            商品情報CSV（AID,プラン,商品ID,商品名,品名,緩衝材指定,緩衝材）
                    build_opl_csv.py の --plans にそのまま渡せる
"""
import argparse, csv, io, json, sys


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def read_priority(path):
    with open(path, encoding="utf-8-sig") as f:
        return [line.strip() for line in f if line.strip()]


def load_cushion_rules(path):
    with open(path, encoding="utf-8-sig") as f:
        rules = json.load(f)
    for r in rules:
        if not {"keyword", "flag", "material"} <= r.keys():
            sys.exit(f"緩衝材ルールの形式が不正: {r}")
    return rules


def resolve_cushion(items, rules):
    for r in rules:
        if any(r["keyword"] in item for item in items):
            return r["flag"], r["material"]
    return "", ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", required=True)
    ap.add_argument("--priority", required=True)
    ap.add_argument("--cushion-rules", required=True)
    ap.add_argument("--name-template", default="【{plan}プラン】{campaign}特典")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    items_rows = {r["AID"].strip(): r for r in read_csv(a.items)}
    priority = read_priority(a.priority)

    missing = [aid for aid in priority if aid not in items_rows]
    if missing:
        sys.exit(f"優先順位ファイルにあるが同梱物マスタに無いAID: {', '.join(missing)}")
    extra = [aid for aid in items_rows if aid not in priority]
    if extra:
        sys.exit(f"同梱物マスタにあるが優先順位ファイルに無いAID: {', '.join(extra)}")

    rules = load_cushion_rules(a.cushion_rules)

    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["AID", "プラン", "商品ID", "商品名", "品名", "緩衝材指定", "緩衝材"])
    for aid in priority:
        r = items_rows[aid]
        items = [x.strip() for x in r["同梱物"].split("|") if x.strip()]
        name = a.name_template.format(plan=r["プラン"].strip(), campaign=r["企画名"].strip())
        flag, material = resolve_cushion(items, rules)
        w.writerow([aid, r["プラン"].strip(), r["商品ID"].strip(), name, "、".join(items), flag, material])
    with open(a.out, "w", encoding="utf-8-sig", newline="") as f:
        f.write(out.getvalue())
    print(f"{len(priority)}件の商品情報を書き出しました → {a.out}")


if __name__ == "__main__":
    main()
