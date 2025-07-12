import streamlit as st
import folium
from streamlit_folium import st_folium
import google.generativeai as genai
import json
import re
import requests
from typing import Dict, List, Optional
import os
from dataclasses import dataclass
import hashlib

@dataclass
class PilgrimageSpot:
    name: str
    anime_title: str
    description: str
    latitude: float
    longitude: float
    address: str
    scene_description: str

class PilgrimageMapApp:
    def __init__(self):
        self.setup_page()
        
    def setup_page(self):
        st.set_page_config(
            page_title="聖地巡礼マップ",
            page_icon="🗾",
            layout="wide"
        )
        
        st.title("🗾 聖地巡礼マップ")
        st.markdown("アニメ・漫画の聖地を検索して地図上に表示します（最大20箇所）")
        
    def setup_gemini(self):
        """Gemini APIの設定"""
        # サイドバーでAPIキーを入力
        with st.sidebar:
            st.header("⚙️ 設定")
            api_key = st.text_input(
                "Gemini API Key",
                type="password",
                help="Google AI StudioでAPIキーを取得してください",
                key="gemini_api_key_input"
            )
            
            if api_key:
                try:
                    genai.configure(api_key=api_key)
                    
                    # 利用可能なモデルを取得
                    try:
                        available_models = []
                        for model in genai.list_models():
                            if 'generateContent' in model.supported_generation_methods:
                                available_models.append(model.name)
                        
                        st.info(f"利用可能なモデル: {', '.join(available_models)}")
                        
                        # 推奨モデルを順番に試す
                        preferred_models = [
                            'models/gemini-2.0-flash-exp',
                            'models/gemini-1.5-flash',
                            'models/gemini-1.5-pro',
                            'models/gemini-2.5-flash',
                            'models/gemini-2.5-pro'
                        ]
                        
                        model_set = False
                        for model_name in preferred_models:
                            if model_name in available_models:
                                try:
                                    self.model = genai.GenerativeModel(model_name)
                                    st.success(f"✅ API接続完了 ({model_name})")
                                    model_set = True
                                    break
                                except Exception as e:
                                    continue
                        
                        # 推奨モデルが見つからない場合、最初の利用可能なモデルを使用
                        if not model_set and available_models:
                            try:
                                self.model = genai.GenerativeModel(available_models[0])
                                st.success(f"✅ API接続完了 ({available_models[0]})")
                                model_set = True
                            except Exception as e:
                                st.error(f"❌ モデル初期化エラー: {str(e)}")
                                return False
                        
                        if not model_set:
                            st.error("❌ 利用可能なモデルが見つかりません")
                            return False
                        
                        return True
                        
                    except Exception as e:
                        st.error(f"❌ モデル一覧取得エラー: {str(e)}")
                        return False
                except Exception as e:
                    st.error(f"❌ API接続エラー: {str(e)}")
                    return False
            else:
                st.warning("⚠️ Gemini APIキーを入力してください")
                return False
        
        return hasattr(self, 'model')
        
    def search_pilgrimage_spots(self, query: str, search_type: str) -> List[PilgrimageSpot]:
        """聖地巡礼スポットを検索"""
        if not hasattr(self, 'model'):
            st.error("Gemini APIが設定されていません")
            return []
            
        try:
            if search_type == "地域名":
                prompt = f"""
                {query}周辺にある日本のアニメ・漫画・ゲーム・ライトノベルの聖地巡礼スポットを可能な限り多く（最大20箇所）教えてください。
                有名な作品から比較的マイナーな作品まで、幅広く含めてください。
                
                以下の条件で回答してください：
                - 実在する場所のみ
                - 正確な緯度経度を含める
                - 様々なジャンルの作品を含める（アニメ、漫画、ゲーム、ライトノベル等）
                - 映画館、展示場、記念館、実際のロケ地なども含める
                - 有名な聖地から隠れた聖地まで幅広く
                
                以下のJSON形式で回答してください：
                
                {{
                    "spots": [
                        {{
                            "name": "スポット名",
                            "anime_title": "作品名",
                            "description": "スポットの説明",
                            "latitude": 緯度,
                            "longitude": 経度,
                            "address": "住所",
                            "scene_description": "作品内でのシーンの説明"
                        }}
                    ]
                }}
                
                可能な限り20箇所に近い数を提供してください。
                """
            else:  # 作品名
                prompt = f"""
                「{query}」に関連する聖地巡礼スポットを可能な限り多く（最大20箇所）教えてください。
                
                以下の条件で回答してください：
                - 実在する場所のみ
                - 正確な緯度経度を含める
                - 作品に登場する場所、モデルになった場所
                - 作者ゆかりの地
                - 関連施設（記念館、展示場、グッズショップ等）
                - イベント会場
                - 関連する観光地
                
                以下のJSON形式で回答してください：
                
                {{
                    "spots": [
                        {{
                            "name": "スポット名",
                            "anime_title": "{query}",
                            "description": "スポットの説明",
                            "latitude": 緯度,
                            "longitude": 経度,
                            "address": "住所",
                            "scene_description": "作品内でのシーンの説明"
                        }}
                    ]
                }}
                
                可能な限り20箇所に近い数を提供してください。
                """
            
            response = self.model.generate_content(prompt)
            
            # JSONを抽出
            json_match = re.search(r'```json\n(.*?)\n```', response.text, re.DOTALL)
            if json_match:
                json_text = json_match.group(1)
            else:
                # JSONマーカーがない場合、{ で始まり } で終わる部分を探す
                json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
                if json_match:
                    json_text = json_match.group(0)
                else:
                    st.error("JSONデータが見つかりませんでした")
                    return []
            
            data = json.loads(json_text)
            
            spots = []
            for spot_data in data.get('spots', []):
                try:
                    spot = PilgrimageSpot(
                        name=spot_data.get('name', ''),
                        anime_title=spot_data.get('anime_title', ''),
                        description=spot_data.get('description', ''),
                        latitude=float(spot_data.get('latitude', 0)),
                        longitude=float(spot_data.get('longitude', 0)),
                        address=spot_data.get('address', ''),
                        scene_description=spot_data.get('scene_description', '')
                    )
                    # 有効な座標のみを追加
                    if spot.latitude != 0 and spot.longitude != 0:
                        spots.append(spot)
                except (ValueError, TypeError):
                    # 無効な座標データをスキップ
                    continue
                
            return spots
            
        except json.JSONDecodeError as e:
            st.error(f"JSONの解析に失敗しました: {str(e)}")
            st.text("レスポンス内容:")
            st.text(response.text)
            return []
        except Exception as e:
            st.error(f"検索中にエラーが発生しました: {str(e)}")
            return []
    
    def create_map(self, spots: List[PilgrimageSpot]) -> folium.Map:
        """聖地巡礼マップを作成"""
        if not spots:
            # デフォルトの日本地図
            m = folium.Map(
                location=[35.6762, 139.6503],  # 東京
                zoom_start=6
            )
            return m
        
        # 最初のスポットを中心に設定
        center_lat = sum(spot.latitude for spot in spots) / len(spots)
        center_lon = sum(spot.longitude for spot in spots) / len(spots)
        
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=8
        )
        
        # マーカーの色とアイコンのバリエーションを増やす
        colors = ['red', 'blue', 'green', 'purple', 'orange', 'darkred', 'lightred', 
                 'beige', 'darkblue', 'darkgreen', 'cadetblue', 'darkpurple', 'white', 
                 'pink', 'lightblue', 'lightgreen', 'gray', 'black', 'lightgray']
        icons = ['star', 'heart', 'film', 'camera', 'map-marker', 'flag', 'home', 
                'building', 'tree', 'cloud']
        
        # 各スポットにマーカーを追加
        for i, spot in enumerate(spots):
            color = colors[i % len(colors)]
            icon = icons[i % len(icons)]
            
            popup_html = f"""
            <div style="width: 350px; font-family: Arial, sans-serif;">
                <h4 style="margin-bottom: 10px; color: #333;">📍 {spot.name}</h4>
                <p><strong>🎬 作品:</strong> {spot.anime_title}</p>
                <p><strong>📍 住所:</strong> {spot.address}</p>
                <p><strong>📝 説明:</strong> {spot.description}</p>
                <p><strong>🎭 シーン:</strong> {spot.scene_description}</p>
                <p><strong>🗺️ 座標:</strong> {spot.latitude:.4f}, {spot.longitude:.4f}</p>
            </div>
            """
            
            folium.Marker(
                location=[spot.latitude, spot.longitude],
                popup=folium.Popup(popup_html, max_width=350),
                tooltip=f"{spot.name} ({spot.anime_title})",
                icon=folium.Icon(color=color, icon=icon)
            ).add_to(m)
        
        return m
    
    def display_spot_details(self, spots: List[PilgrimageSpot]):
        """スポット詳細を表示"""
        if not spots:
            return
            
        st.subheader(f"📍 検索結果 ({len(spots)}箇所)")
        
        # 作品別にグループ化
        spots_by_anime = {}
        for spot in spots:
            if spot.anime_title not in spots_by_anime:
                spots_by_anime[spot.anime_title] = []
            spots_by_anime[spot.anime_title].append(spot)
        
        # 作品ごとに表示
        for anime_title, anime_spots in spots_by_anime.items():
            with st.expander(f"🎬 {anime_title} ({len(anime_spots)}箇所)"):
                for i, spot in enumerate(anime_spots, 1):
                    st.markdown(f"### {i}. {spot.name}")
                    
                    col1, col2 = st.columns([1, 1])
                    
                    with col1:
                        st.write(f"**📮 住所:** {spot.address}")
                        st.write(f"**🌐 座標:** {spot.latitude:.4f}, {spot.longitude:.4f}")
                        st.write(f"**📝 説明:** {spot.description}")
                    
                    with col2:
                        st.write(f"**🎭 シーン:** {spot.scene_description}")
                        
                        # Googleマップのリンクを追加
                        google_maps_url = f"https://www.google.com/maps?q={spot.latitude},{spot.longitude}"
                        st.markdown(f"[🗺️ Googleマップで見る]({google_maps_url})")
                    
                    st.markdown("---")
    
    def run(self):
        """アプリケーションを実行"""
        # APIキーの設定確認
        if not self.setup_gemini():
            st.info("👆 まず左のサイドバーでGemini APIキーを設定してください")
            return
        
        # セッション状態の初期化
        if 'search_results' not in st.session_state:
            st.session_state.search_results = []
        if 'last_search_query' not in st.session_state:
            st.session_state.last_search_query = ""
        if 'last_search_type' not in st.session_state:
            st.session_state.last_search_type = ""
        
        # 検索フォーム
        with st.form("search_form", clear_on_submit=False):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                search_query = st.text_input(
                    "🔍 検索キーワード",
                    placeholder="例: 東京, 君の名は。, 鬼滅の刃",
                    key="search_query_input"
                )
            
            with col2:
                search_type = st.selectbox(
                    "検索タイプ",
                    ["地域名", "作品名"],
                    key="search_type_select"
                )
            
            submit_button = st.form_submit_button("🔍 検索", type="primary")
        
        # 検索実行
        if submit_button and search_query:
            with st.spinner("聖地を検索中...（最大20箇所）"):
                spots = self.search_pilgrimage_spots(search_query, search_type)
            
            # 検索結果をセッション状態に保存
            st.session_state.search_results = spots
            st.session_state.last_search_query = search_query
            st.session_state.last_search_type = search_type
            
            if spots:
                st.success(f"✅ {len(spots)}箇所の聖地巡礼スポットが見つかりました！")
            else:
                st.warning("検索結果が見つかりませんでした。")
        
        # 検索結果がある場合に表示
        if st.session_state.search_results:
            spots = st.session_state.search_results
            
            # 地図表示
            st.subheader("🗾 聖地巡礼マップ")
            
            # 検索クエリをハッシュ化して一意のキーを作成
            query_hash = hashlib.md5(
                f"{st.session_state.last_search_query}_{st.session_state.last_search_type}".encode()
            ).hexdigest()[:8]
            
            map_obj = self.create_map(spots)
            
            # 地図を表示（一意のキーを使用）
            map_data = st_folium(
                map_obj, 
                width=700, 
                height=500, 
                key=f"pilgrimage_map_{query_hash}",
                returned_objects=["last_object_clicked"]
            )
            
            # 統計情報
            anime_count = len(set(spot.anime_title for spot in spots))
            st.info(f"📊 統計: {len(spots)}箇所のスポット、{anime_count}作品")
            
            # 詳細情報表示
            self.display_spot_details(spots)
            
        elif submit_button:
            st.warning("検索結果が見つかりませんでした。別のキーワードで試してください。")
        
        # 使い方の説明
        with st.expander("ℹ️ 使い方"):
            st.markdown("""
            ### 🔍 検索方法
            
            **地域名で検索:**
            - 「東京」「大阪」「京都」など地域名を入力
            - その地域周辺の聖地巡礼スポットを最大20箇所表示
            
            **作品名で検索:**
            - 「君の名は。」「鬼滅の刃」「新海誠」など作品名を入力
            - その作品の聖地巡礼スポットを最大20箇所表示
            
            ### 📍 地図の見方
            - 各マーカーをクリックすると詳細情報が表示されます
            - 作品・場所ごとに異なる色とアイコンで表示されます
            - ズームイン/アウトで詳細を確認できます
            
            ### 🎯 検索のコツ
            - 地域名は「渋谷」「新宿」など具体的な地名がおすすめ
            - 作品名は正確な名前で検索すると良い結果が得られます
            - 「スタジオジブリ」「新海誠」など監督名での検索も可能
            
            ### ⚠️ 注意事項
            - 情報は参考程度にご利用ください
            - 実際の訪問前に最新情報を確認することをお勧めします
            - 撮影や見学の際は周辺住民の迷惑にならないよう注意してください
            - 私有地への立ち入りは避けてください
            """)

if __name__ == "__main__":
    app = PilgrimageMapApp()
    app.run()