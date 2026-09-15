import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# ============================================================
# 大宮院（FC1号店）顧客満足度アンケート（神保町・横浜と同一設計・院別差分は2点のみ）
#   1) 書込先ワークシート: 'Omiya'（同一スプレッドシート内の大宮タブ）
#   2) Google口コミリンク : REVIEW_URL（大宮GBP公開後に確定）
# データフロー/運用は ../README_顧客満足度システム_全体設計.md を参照
# ============================================================

# ▼▼▼ 院別設定（ここだけ院ごとに変える） ▼▼▼
WORKSHEET_NAME = 'Omiya'

# Google口コミ誘導リンク。
#
# None にすると高評価ページで口コミ誘導を一切出さず、お礼のみを表示する。
# 2026-07-31 時点の大宮は None。理由は、大宮のGBPが未作成のため。
# Googleが口コミURLをまだ発番していないため。壊れたリンクを出さない。
#
# ⚠️ **Googleマップの検索型URL等で代用してはならない。**
#    未公開の院名で検索すると既存院（神保町）に解決し、その院の口コミが他院に付く（2026-07-31 八丁堀で実測）。
#
# ▼ 再開手順（GBPのオーナー確認が通ったら、これをやる）
#   1. 発番されたかを確認する:
#        cd スマスキ関連/06_IT・システム/システム開発/20241201_顧客満足度システム
#        python check_review_url.py
#      → 「スマートスキンクリニック 大宮院」の「口コミURL」に
#        https://search.google.com/local/writereview?placeid=... が出れば発番済み。
#        「(なし)」ならまだ認証が通っていないので、何もせず待つ。
#   2. 出力されたURLを、下の REVIEW_URL に文字列として設定する（None を置き換える）。
#   3. GitHub リポジトリ nmrnmnmr55/smartskin-survey-omiya の app_hacchobori.py へ push する。
#      Streamlit Cloud が自動で再デプロイする（数分）。
#   4. https://smartskin-survey-omiya.streamlit.app/?d=TEST を開き、
#      「非常に満足」→ 口コミリンクが出て、八丁堀のGoogleページに飛ぶことを目視確認する。
#      ※ 神保町・横浜のページに飛んだら即座に None へ戻すこと。
#   5. README_顧客満足度システム_全体設計.md の該当箇所を「差替済」に更新する。
#
# 参考（発番済みの既存院）:
#   神保町 = https://search.google.com/local/writereview?placeid=ChIJp_i6nMGNGGARn27uO0q54q8
#   横浜   = https://search.google.com/local/writereview?placeid=ChIJ-_X7hphdGGAR8oyeKDHEM9Y
REVIEW_URL = None
# ▲▲▲ 院別設定ここまで ▲▲▲

def show_review_request():
    """Google口コミのお願い。満足度に関係なく、全員に同じ文面・同じリンクを出す。

    2026-09-15: 特典（プレゼント）と、満足度に応じた出し分けを全院で廃止した。再導入しない。
    理由: Googleのポリシーはインセンティブ付き口コミと選別的な依頼を禁止しており、
    八丁堀院のプロフィールが同日に制限（5つ星43件削除・30日投稿停止）を受けたため。
    REVIEW_URL が None の院（口コミURL未発番・投稿制限中）では何も出さない。
    """
    if not REVIEW_URL:
        return
    st.write("Smart skin CLINICは、患者様のお声とともに育ってきたクリニックです。")
    st.write("率直なご感想を、Googleのクチコミで教えていただけると嬉しいです。")
    st.write("ご意見はひとつ残らず読ませていただき、次のご来院に活かしてまいります。")
    st.markdown(f"[クチコミを書く]({REVIEW_URL})")


# カスタムCSSの適用
st.markdown("""
<style>
    body {
        color: #333333;
        background-color: #F8F8F8;
        font-family: "Yu Gothic", "游ゴシック", YuGothic, "游ゴシック体", "ヒラギノ角ゴ Pro W3", "メイリオ", sans-serif;
    }
    .stButton>button {
        color: #FFFFFF;
        background-color: #333333;
        border-radius: 20px;
        padding: 10px 24px;
        font-weight: 500;
        font-family: "Yu Gothic", "游ゴシック", YuGothic, "游ゴシック体", sans-serif;
    }
    .stTextInput>div>div>input, .stTextArea>div>div>textarea {
        border-radius: 10px;
        border: 1px solid #CCCCCC;
        font-family: "Yu Gothic", "游ゴシック", YuGothic, "游ゴシック体", sans-serif;
    }
    h1 {
        font-size: 2.5rem;
        font-weight: 700;
        letter-spacing: -0.5px;
        margin-bottom: 2rem;
        font-family: "Yu Gothic", "游ゴシック", YuGothic, "游ゴシック体", sans-serif;
    }
    p {
        font-size: 1.1rem;
        line-height: 1.8;
        margin-bottom: 1.5rem;
    }
    .stRadio > label {
        font-size: 1.1rem;
        padding: 10px 0;
        font-family: "Yu Gothic", "游ゴシック", YuGothic, "游ゴシック体", sans-serif;
    }
    @media (max-width: 768px) {
        h1 {
            font-size: 2rem;
        }
        p {
            font-size: 1rem;
        }
    }
</style>
""", unsafe_allow_html=True)

# Google Sheets API の設定
scopes = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

try:
    # Streamlit Secrets から認証情報を取得
    credentials = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(credentials)

    # スプレッドシートを開く（神保町・横浜と同一スプレッドシート／八丁堀タブ）
    sheet = client.open_by_key('1R2QKVcLIwAwPE0b4GEr_f1fJ-4wNLt4ZDWyCGK8p-zo').worksheet(WORKSHEET_NAME)
except Exception as e:
    st.error(f"Google Sheets APIの設定中にエラーが発生しました: {str(e)}")
    sheet = None

# URLからユーザーIDを取得する関数（?d=<来院者ID>）
def get_user_id():
    return st.query_params.get("d")

def main():
    col1, col2, col3 = st.columns([1,3,1])
    with col2:
        st.title("お客様満足度調査")

        if 'page' not in st.session_state:
            st.session_state.page = 1
        if 'choice' not in st.session_state:
            st.session_state.choice = None
        if 'row_index' not in st.session_state:
            st.session_state.row_index = None
        if 'user_id' not in st.session_state:
            st.session_state.user_id = get_user_id()

        if st.session_state.page == 1:
            show_page_1()
        elif st.session_state.page == 2:
            show_page_2()
        elif st.session_state.page == 3:
            show_page_3()
        elif st.session_state.page == 4:
            show_page_4()

def show_page_1():
    st.write("当クリニックではお客様の声を踏まえ、より良いサービスの提供を目指しています。")
    st.write("1問のみ、5秒で終わりますので、満足度調査にご協力をお願い申し上げます。")
    options = ["非常に満足", "満足", "どちらでもない", "不満", "非常に不満"]
    choice = st.radio("選択肢", options)

    if st.button("次へ", key="next_button"):
        st.session_state.choice = choice  # 選択を保存
        row_index = save_page_1_to_sheet(choice)
        st.session_state.row_index = row_index
        if choice in ["非常に満足", "満足"]:
            st.session_state.page = 2
        else:
            st.session_state.page = 3
        st.rerun()

def show_page_2():
    st.write("ご回答ありがとうございました！")
    st.write("いただいたお声は、より良いサービスの提供に活かしてまいります。")
    show_review_request()

def show_page_3():
    st.write("この度、満足いただけなかったこと誠に申し訳ございません。心よりお詫び申し上げます。")
    st.write("今後、少しでもよりサービスを提供できるように改善していければと考えております。もし差し支えなければ、ご忌憚のないご意見をお聞かせいただければ幸いです。")
    rating = st.slider("★の数を選択してください", 1, 5, 3, key="rating_slider")
    comment = st.text_area("コメントを記入してください")

    if st.button("送信", key="submit_button"):
        save_page_3_to_sheet(rating, comment)
        st.session_state.page = 4  # 確認ページに遷移
        st.rerun()

def show_page_4():
    st.write("貴重なご意見をいただき誠にありがとうございました。")
    st.write("確かに受領いたしました。")
    st.write("頂いた貴重なご意見をふまえ、少しでも良いサービスを提供できるように改善に努めてまいります。")
    st.write("引き続きどうぞよろしくお願いいたします。")
    show_review_request()

    if st.button("最初に戻る", key="return_button"):
        st.session_state.page = 1  # 最初のページに戻る
        st.session_state.choice = None  # 選択をリセット
        st.session_state.row_index = None  # 行インデックスをリセット
        st.rerun()

def save_page_1_to_sheet(choice):
    if sheet is None:
        st.error("Google Sheetsとの接続に問題があります。")
        return None

    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [now, choice, '', '', '', st.session_state.user_id]  # F列にuser_idを追加
        next_row = len(sheet.get_all_values()) + 1
        sheet.insert_row(row, next_row)
        return next_row
    except Exception as e:
        st.error(f"データの保存中にエラーが発生しました: {str(e)}")
        return None

def save_page_3_to_sheet(rating, comment):
    if sheet is None:
        st.error("Google Sheetsとの接続に問題があります。")
        return

    try:
        if st.session_state.row_index:
            sheet.update_cell(st.session_state.row_index, 4, rating)
            sheet.update_cell(st.session_state.row_index, 5, comment)
        else:
            st.error("行インデックスが見つかりません。管理者にお問い合わせください。")
    except Exception as e:
        st.error(f"データの更新中にエラーが発生しました: {str(e)}")

if __name__ == "__main__":
    main()
