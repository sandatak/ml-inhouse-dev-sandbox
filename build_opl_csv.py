"""オープンロジ出荷依頼CSVを組み立てる（ストア販売分）。個人情報は標準出力にもワーニングにも出さない。

入力:
  --bdash  b-dash（データパレット）配送先フォーム回答CSV（Shift_JIS）
  --orders 購入データ（AID, No, 注文番号, PDC, RS会員ID）※事前購入＋追加販売分
  --konpo  突合リスト（RS会員ID, 梱包No）※赤荻さんが手動作成。梱包Noは納品物の並び順
  --plans  商品情報（AID, プラン, 商品ID, 商品名, 品名, 緩衝材指定, 緩衝材）※上の行ほど優先
  --delivery 配送便指定（4=佐川〈既定〉 / 2=ネコポス：ユニーク商材なしの案件で使うことがある）
出力:
  --out    出荷依頼CSV（UTF-8 BOM・CRLF・見出し2行）
  --warn-out ワーニング（テキスト）。省略時は <out>_ワーニング.txt
  標準出力に検算レポート
"""
import argparse, csv, io, os, sys
from collections import OrderedDict, defaultdict

HEADER = "商品ID,商品名,商品コード,軽減税率適用商品,サイズ,在庫数,出荷依頼数,出荷予約,単価,合計金額,小計,配送料,手数料,割引額,総計,総計通常税率,総計軽減税率,配送先郵便番号,配送先都道府県,配送先住所,配送先マンション・ビル名,配送先氏名,配送先会社名,配送先電話番号,配送先連絡メール,配送先マスタ登録,注文番号,配送便指定,配送会社指定,出荷希望日,お届け希望日,希望時間帯,緩衝材指定,緩衝材,ギフトラッピング単位,ラッピングタイプ,贈り主氏名,同梱指定,不在時宅配ボックス,割れ物注意,品名,明細書メッセージ,発送通知メッセージ,明細書の同梱,明細書の金額印字,ご依頼主郵便番号,ご依頼主都道府県,ご依頼主住所,ご依頼主マンション・ビル名,ご依頼主氏名,ご依頼主会社名,ご依頼主部署名,お問い合わせ先,ご依頼主電話番号,ご依頼主メールアドレス,お問い合わせフォーム,ご依頼主UUID".split(",")
NOTE = "【商品ID列か商品コード列のいずれか必須】,【任意】,【商品ID列か商品コード列のいずれか必須】,【任意】,【入力不要】,【入力不要】,【必須】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【必須】,【必須】,【必須】,【任意】,【必須】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【ご依頼主UUID未指定時は必須】,【ご依頼主UUID未指定時は必須】,【ご依頼主UUID未指定時は必須】,【任意】,【ご依頼主UUID未指定時は必須】,【任意】,【任意】,【任意】,【ご依頼主UUID未指定時は必須】,【任意】,【任意】,【任意。指定時は他の依頼主項目は無視】".split(",")
SENDER = {"ご依頼主郵便番号": "1070052", "ご依頼主都道府県": "東京都", "ご依頼主住所": "港区赤坂2-5-27",
          "ご依頼主氏名": "Reader Store", "お問い合わせ先": "URL", "ご依頼主電話番号": "0335683372",
          "お問い合わせフォーム": "https://ebookstore.sony.jp/mtc/stc/help/support/"}
ADDR_KEYS = ("郵便番号", "都道府県", "住所", "建物名", "姓", "名", "電話番号", "メールアドレス")


def read_csv(path, enc="utf-8-sig"):
    raw = open(path, "rb").read()
    for e in (enc, "utf-8-sig", "cp932"):
        try:
            return list(csv.DictReader(io.StringIO(raw.decode(e))))
        except UnicodeDecodeError:
            continue
    sys.exit(f"文字コードを判別できません: {path}")


def main():
    ap = argparse.ArgumentParser()
    for k in ("bdash", "orders", "konpo", "plans", "out"):
        ap.add_argument("--" + k, required=True)
    ap.add_argument("--delivery", default="4", choices=["4", "2"])
    ap.add_argument("--warn-out")
    a = ap.parse_args()
    warn_path = a.warn_out or os.path.splitext(a.out)[0] + "_ワーニング.txt"
    warn = []

    plans = OrderedDict((r["AID"].strip(), r) for r in read_csv(a.plans))
    plan_rank = {aid: i for i, aid in enumerate(plans)}
    orders = read_csv(a.orders)
    order2member = {}
    for r in orders:
        on, m = r["注文番号"].strip(), r["RS会員ID"].strip()
        if on in order2member and order2member[on] != m:
            warn.append(f"[要確認] 注文番号 {on} に複数の会員IDが紐づいている")
        order2member[on] = m
    konpo = {}
    for r in read_csv(a.konpo):
        m, k = r["RS会員ID"].strip(), r["梱包No"].strip()
        if not m:
            continue
        if m in konpo and konpo[m] != k:
            warn.append(f"[要確認] 突合リストで同じ会員に梱包Noが2つ（{konpo[m]} / {k}）")
        konpo[m] = k

    # 配送先：注文番号→会員IDで顧客IDを補完。同じ会員の回答が複数なら回答IDが大きい（新しい）方を採用
    answers = defaultdict(list)
    for r in read_csv(a.bdash, "cp932"):
        on = r["注文番号"].strip()
        m = r.get("顧客ID", "").strip() or order2member.get(on)
        if not m:
            warn.append(f"[除外] 配送先回答 回答ID={r['回答ID']} 注文番号={on}：購入データに無い（テスト回答等）")
            continue
        answers[m].append(r)
    addr = {}
    for m, rs in answers.items():
        rs.sort(key=lambda r: int(r["回答ID"]))
        addr[m] = rs[-1]
        if len(rs) > 1:
            same = all(rs[0][k] == x[k] for x in rs for k in ADDR_KEYS)
            ids = "・".join(r["回答ID"] for r in rs)
            ons = "・".join(sorted({r["注文番号"].strip() for r in rs}))
            warn.append(f"[重複回答] 梱包No={konpo.get(m, '(突合リストに無し)')} 注文番号={ons} 回答ID={ids} → 回答ID {rs[-1]['回答ID']} を採用"
                        + ("（内容は同じ）" if same else "【内容が異なる・要確認】"))

    # 数量：会員×AID で注文番号を数える
    qty = defaultdict(int)
    for r in orders:
        aid = r["AID"].strip()
        if aid not in plans:
            warn.append(f"[要確認] 商品情報に無いAID {aid}（注文番号 {r['注文番号'].strip()}）")
            continue
        qty[(r["RS会員ID"].strip(), aid)] += 1

    lines, no_addr, no_konpo = [], set(), set()
    for (m, aid), n in qty.items():
        if m not in addr:
            no_addr.add(m); continue
        if m not in konpo:
            no_konpo.add(m); continue
        lines.append((konpo[m], plan_rank[aid], m, aid, n))
    lines.sort()

    # 同じ梱包の行は、その梱包に入っているプランのうち優先度がいちばん高いもの（＝その梱包の先頭行）の
    # 緩衝材指定・緩衝材・品名に揃える。CSV全体や商品情報の一番上には揃えない（例：B＋CならB）
    head = {}
    for k, _, _, aid, _ in lines:
        head.setdefault(k, plans[aid])

    out = io.StringIO()
    w = csv.writer(out, lineterminator="\r\n")
    w.writerow(HEADER); w.writerow(NOTE)
    for k, _, m, aid, n in lines:
        p, ad, base = plans[aid], addr[m], head[k]
        row = dict.fromkeys(HEADER, "")
        row.update({"商品ID": p["商品ID"], "商品名": p["商品名"], "出荷依頼数": str(n), "出荷予約": "1",
                    "配送先郵便番号": ad["郵便番号"].strip().replace("-", ""), "配送先都道府県": ad["都道府県"].strip(),
                    "配送先住所": ad["住所"].strip(), "配送先マンション・ビル名": ad["建物名"].strip(),
                    "配送先氏名": f"{ad['姓'].strip()} {ad['名'].strip()}", "配送先電話番号": ad["電話番号"].strip().replace("-", ""),
                    "配送先連絡メール": ad["メールアドレス"].strip(), "注文番号": k, "配送便指定": a.delivery,
                    "緩衝材指定": base["緩衝材指定"].strip(), "緩衝材": base["緩衝材"].strip(), "品名": base["品名"].strip()})
        row.update(SENDER)
        w.writerow([row[h] for h in HEADER])
    open(a.out, "w", encoding="utf-8-sig", newline="").write(out.getvalue())

    for m in sorted(no_addr, key=lambda x: konpo.get(x, "")):
        warn.append(f"[未発送] 配送先未登録 梱包No={konpo.get(m, '(突合リストに無し)')} 会員 {m[:8]}… 数量={sum(v for (mm, _), v in qty.items() if mm == m)}")
    for m in sorted(no_konpo):
        warn.append(f"[要確認] 突合リストに梱包Noが無い 会員 {m[:8]}…（配送先はあり・CSVに入れていない）")

    summary = [f"出力 {len(lines)}行 / 梱包 {len({l[0] for l in lines})}件 / 数量合計 {sum(l[4] for l in lines)} / 配送便指定 {a.delivery}",
               f"購入データの数量合計 {sum(qty.values())}（差分は配送先未登録・突合リスト漏れの分）"]
    open(warn_path, "w", encoding="utf-8-sig", newline="").write("\r\n".join(summary + warn) + "\r\n")
    print("\n".join(summary + warn))
    print(f"ワーニング → {warn_path}")


if __name__ == "__main__":
    main()
