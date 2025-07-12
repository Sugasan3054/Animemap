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
        st.markdown("アニメ・漫画の聖地を検索して地図上に表示します")
        
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
                    self.model = genai.GenerativeModel('gemini-pro')
                    st.success("✅ API接続完了")
                    return True
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
                {query}周辺にある日本のアニメ・漫画・ゲームの聖地巡礼スポットを5つ教えてください。
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
                
                実在する場所で、正確な緯度経度を含めてください。
                """
            else:  # 作品名
                prompt = f"""
                「{query}」の聖地巡礼スポットを5つ教えてください。
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
                
                実在する場所で、正確な緯度経度を含めてください。
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
                spot = PilgrimageSpot(
                    name=spot_data.get('name', ''),
                    anime_title=spot_data.get('anime_title', ''),
                    description=spot_data.get('description', ''),
                    latitude=float(spot_data.get('latitude', 0)),
                    longitude=float(spot_data.get('longitude', 0)),
                    address=spot_data.get('address', ''),
                    scene_description=spot_data.get('scene_description', '')
                )
                spots.append(spot)
                
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
            zoom_start=10
        )
        
        # 各スポットにマーカーを追加
        for i, spot in enumerate(spots):
            # アニメタイトルごとに色を変える
            colors = ['red', 'blue', 'green', 'purple', 'orange', 'darkred', 'lightred', 'beige', 'darkblue', 'darkgreen']
            color = colors[i % len(colors)]
            
            popup_html = f"""
            <div style="width: 300px;">
                <h4>📍 {spot.name}</h4>
                <p><strong>🎬 作品:</strong> {spot.anime_title}</p>
                <p><strong>📍 住所:</strong> {spot.address}</p>
                <p><strong>📝 説明:</strong> {spot.description}</p>
                <p><strong>🎭 シーン:</strong> {spot.scene_description}</p>
            </div>
            """
            
            folium.Marker(
                location=[spot.latitude, spot.longitude],
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=f"{spot.name} ({spot.anime_title})",
                icon=folium.Icon(color=color, icon='star')
            ).add_to(m)
        
        return m
    
    def display_spot_details(self, spots: List[PilgrimageSpot]):
        """スポット詳細を表示"""
        if not spots:
            return
            
        st.subheader("📍 検索結果")
        
        for i, spot in enumerate(spots, 1):
            with st.expander(f"{i}. {spot.name} - {spot.anime_title}"):
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.write(f"**📍 場所名:** {spot.name}")
                    st.write(f"**🎬 作品:** {spot.anime_title}")
                    st.write(f"**📮 住所:** {spot.address}")
                    st.write(f"**🌐 座標:** {spot.latitude}, {spot.longitude}")
                
                with col2:
                    st.write(f"**📝 説明:** {spot.description}")
                    st.write(f"**🎭 シーン:** {spot.scene_description}")
    
    def run(self):
        """アプリケーションを実行"""
        # APIキーの設定確認
        if not self.setup_gemini():
            st.info("👆 まず左のサイドバーでGemini APIキーを設定してください")
            return
        
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
            with st.spinner("聖地を検索中..."):
                spots = self.search_pilgrimage_spots(search_query, search_type)
            
            if spots:
                # 地図表示
                st.subheader("🗾 聖地巡礼マップ")
                map_obj = self.create_map(spots)
                
                # 地図を表示
                st_folium(map_obj, width=700, height=500, key="pilgrimage_map")
                
                # 詳細情報表示
                self.display_spot_details(spots)
                
            else:
                st.warning("検索結果が見つかりませんでした。別のキーワードで試してください。")
        
        # 使い方の説明
        with st.expander("ℹ️ 使い方"):
            st.markdown("""
            ### 🔍 検索方法
            
            **地域名で検索:**
            - 「東京」「大阪」「京都」など地域名を入力
            - その地域周辺の聖地巡礼スポットを表示
            
            **作品名で検索:**
            - 「君の名は。」「鬼滅の刃」「新海誠」など作品名を入力
            - その作品の聖地巡礼スポットを表示
            
            ### 📍 地図の見方
            - 各マーカーをクリックすると詳細情報が表示されます
            - 作品ごとに異なる色のマーカーで表示されます
            - ズームイン/アウトで詳細を確認できます
            
            ### ⚠️ 注意事項
            - 情報は参考程度にご利用ください
            - 実際の訪問前に最新情報を確認することをお勧めします
            - 撮影や見学の際は周辺住民の迷惑にならないよう注意してください
            """)

if __name__ == "__main__":
    app = PilgrimageMapApp()
    app.run()