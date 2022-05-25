"""Megaton GA"""

from ipywidgets import interact
from IPython.display import clear_output
import pandas as pd
import sys

from google.api_core.exceptions import ServiceUnavailable

from . import constants, errors, ga3, ga4, google_api, gsheet, widget


class Launch(object):
    def __init__(self, json):
        """constructor"""
        self.creds = None
        self.ga3 = None
        self.ga4 = None
        self.gs = None
        self.json = json
        if json:
            self.auth()

    def auth(self):
        """GCS認証"""
        self.creds = google_api.get_credentials(self.json, constants.DEFAULT_SCOPES)
        try:
            self.ga4 = ga4.LaunchGA4(self.creds)
        except ServiceUnavailable:
            if 'invalid_grant' in str(sys.exc_info()[1]):
                print(f"期限が切れたようなので、もう一度認証します。")
                self.creds = google_api.get_credentials(self.json, constants.DEFAULT_SCOPES, reset_cache=True)
                clear_output()
        except Exception as e:
            raise e

    def launch_ga4(self):
        """GA4の準備"""
        self.ga4 = ga4.LaunchGA4(self.creds)
        self.select_ga4_property()

    def select_ga4_property(self):
        """GA4のアカウントとプロパティを選択"""
        if self.ga4.accounts:
            menu1, menu2, _ = widget.create_ga_account_property_menu(self.ga4.accounts)

            @interact(value=menu1)
            def menu1_selected(value):
                if value:
                    self.ga4.account.select(value)
                    prop = [d for d in self.ga4.accounts if d['id'] == value][0]['properties']
                    menu2.options = [(n['name'], n['id']) for n in prop]
                else:
                    self.ga4.account.select(None)
                    menu2.options = [('---', '')]

            @interact(value=menu2)
            def menu2_selected(value):
                if value:
                    self.ga4.property.select(value)
                    print(
                        f"Property ID {self.ga4.property.id} was created on {self.ga4.property.created_time.strftime('%Y-%m-%d')}")
        else:
            print("権限が付与されたGA4アカウントが見つかりません。")

    def launch_ga(self):
        """GA (UA)の準備"""
        self.ga3 = ga3.Megaton(self.creds, credential_cache_file=google_api.get_cache_filename_from_json(self.json))
        self.select_ga3_view()

    def select_ga3_view(self):
        """GAのアカウントとプロパティとビューを選択"""
        if self.ga3.accounts:
            print("　　↓GAのアカウントとプロパティを以下から選択してください")
            menu1, menu2, menu3 = widget.create_ga_account_property_menu(self.ga3.accounts)

            @interact(value=menu1)
            def menu1_selected(value):
                if value:
                    self.ga3.account.select(value)
                    opt = [d for d in self.ga3.accounts if d['id'] == value][0]['properties']
                    menu2.options = [(n['name'], n['id']) for n in opt]
                else:
                    self.ga3.account.select(None)
                    menu2.options = [('---', '')]
                    menu3.options = [('---', '')]

            @interact(value=menu2)
            def menu2_selected(value):
                if value:
                    self.ga3.property.select(value)
                    menu3.options = [(d['name'], d['id']) for d in self.ga3.property.views if d['property_id'] == value]
                else:
                    self.ga3.property.select(None)
                    menu3.options = [('---', '')]

            @interact(value=menu3)
            def menu3_selected(value):
                if value:
                    self.ga3.view.select(value)
                    print(f"View ID {self.ga3.view.id} was created on {self.ga3.view.created_time}")
        else:
            print("権限が付与されたGAアカウントが見つかりません。")

    def launch_gs(self, url):
        try:
            self.gs = gsheet.LaunchGS(self.creds, url)
        except errors.BadCredentialFormat:
            print("認証情報のフォーマットが正しくないため、Google Sheets APIを利用できません。")
        except errors.BadCredentialScope:
            print("認証情報のスコープ不足のため、Google Sheets APIを利用できません。")
        except errors.BadUrlFormat:
            print("URLのフォーマットが正しくありません")
        except errors.ApiDisabled:
            print("Google SheetsのAPIが有効化されていません。")
        except errors.UrlNotFound:
            print("URLが見つかりません。")
        except errors.BadPermission:
            print("該当スプレッドシートを読み込む権限がありません。")
        except Exception as e:
            raise e
        else:
            if self.gs.title:
                print(f"Googleスプレッドシート「{self.gs.title}」を開きました。")
                return True

    def select_sheet(self, sheet_name):
        try:
            name = self.gs.sheet.select(sheet_name)
        except errors.SheetNotFound:
            print(f"{sheet_name} シートが存在しません。")
        if name:
            print(f"「{sheet_name}」を開きました。")
            return True

    def load_cell(self, row, col, what: str = None):
        self.gs.sheet.cell.select(row, col)
        value = self.gs.sheet.cell.data
        if what:
            print(f"{what}は{value}")
        return value

    def analyze_content(self, sheet_name: str = '使い方'):
        # 設定をシートから読み込む
        if self.select_sheet(sheet_name):
            # 設定を読み込む
            include_domains = self.load_cell(5, 5)
            include_pages = self.load_cell(11, 5)
            exclude_pages = self.load_cell(16, 5)
            cv_pages = self.load_cell(26, 5)
            page_regex = self.load_cell(29, 5)
            title_regex = self.load_cell(32, 5)

            # 元データ抽出：コンテンツ閲覧者
            _df = ga3.cid_date_page(self.ga3, include_domains, include_pages, exclude_pages, page_regex)

            # Pageと人でまとめて回遊を算出
            df = ga3.to_page_cid(_df)

            # 元データ抽出：再訪問した人の最終訪問日
            _df = ga3.cid_last_returned_date(self.ga3)

            # 閲覧後の再訪問を判定
            df2 = ga3.to_page_cid_return(df, _df)

            # 元データ抽出：入口以外で特定CVページに到達
            _df = ga3.cv_cid(self.ga3, cv_pages)

            # 人単位でまとめて最後にCVした日を算出
            _df = ga3.to_cid_last_cv(_df)

            # コンテンツ閲覧後のCVを判定
            df3 = ga3.to_cv(df2, _df)

            # Page単位でまとめる
            df_con = ga3.to_page_participation(df3[['page', 'clientId', 'entrances', 'kaiyu', 'returns', 'cv']])

            # 元データ抽出：タイトル
            df_t = ga3.get_page_title(self.ga3, include_domains, include_pages, exclude_pages, page_regex, title_regex)

            df = pd.merge(
                df_con,
                df_t,
                how='left',
                on='page')[['page', 'title', 'users', 'entry_users', 'kaiyu_users', 'return_users', 'cv_users']]

            return df

    def save_content_analysis_to_gs(self, df, sheet_name: str = '_cont'):
        if self.select_sheet(sheet_name):
            if self.gs.sheet.overwrite_data(df, include_index=False):
                self.gs.sheet.auto_resize(cols=[2, 3, 4, 5, 6, 7])
                self.gs.sheet.resize(col=1, width=300)
                self.gs.sheet.resize(col=2, width=300)
                self.gs.sheet.freeze(rows=1)
                print(f"Google Sheetsを更新しました。")