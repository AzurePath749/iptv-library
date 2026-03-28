# -*- coding: utf-8 -*-
import json
import re
from pathlib import Path
from typing import List, Dict
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Classifier:
    def __init__(self, config: dict):
        self.config = config
        self.rules = self._load_rules()
        
    def _load_rules(self) -> Dict:
        """加载分类规则"""
        rules_file = 'sources/rules.json'
        try:
            with open(rules_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return self._default_rules()
    
    def _default_rules(self) -> Dict:
        """默认分类规则"""
        return {
            "china": {
                "keywords": ["CCTV", "央视", "北京", "上海", "广东", "浙江", "江苏", "四川", 
                           "湖南", "湖北", "安徽", "福建", "山东", "河南", "河北", "天津",
                           "重庆", "凤凰", "华视", "中视", "台视", "华视", "民视", "TVBS",
                           "香港", "澳亚", "明珠", "国际", "凤凰"],
                "keywords_en": ["CCTV", "Hunan", "Dragon", "Phoenix", "TVB", "CTI"]
            },
            "asia": {
                "keywords": ["日本", "韩国", "NHK", "KBS", "MBC", "SBS", "TBS", "东京",
                           "首尔", "新加坡", "马来", "泰国", "越南", "印尼", "菲律宾"],
                "keywords_en": ["Japan", "Korea", "NHK", "KBS", "MBC", "Tokyo", "Seoul",
                               "Singapore", "Thai", "VTV"]
            },
            "europe": {
                "keywords": ["英国", "法国", "德国", "俄罗斯", "意大利", "西班牙", "荷兰",
                           "瑞士", "瑞典", "挪威", "丹麦", "芬兰", "波兰", "奥地利"],
                "keywords_en": ["BBC", "France", "Germany", "Russia", "RT", "ARD", "ZDF",
                               "ITV", "Sky", "Euronews", "Euro", "BBC"]
            },
            "america": {
                "keywords": ["美国", "加拿大", "墨西哥", "巴西", "阿根廷", "CNN", "FOX",
                           "ABC", "CBS", "NBC", "HBO", "ESPN", "Discovery"],
                "keywords_en": ["USA", "America", "CNN", "FOX", "ABC", "CBS", "NBC", "HBO",
                               "ESPN", "Discovery", "National Geographic", "Canada"]
            },
            "other": {
                "keywords": ["印度", "中东", "非洲", "澳洲", "纽西兰", "体育", "新闻",
                           "纪录", "电影", "儿童", "音乐", "动漫", "解说", "游戏",
                           "赛事", "咪咕", "轮播"],
                "keywords_en": ["India", "Africa", "Australia", "New Zealand", "Sports",
                               "News", "Documentary", "Movie", "Kids", "Music", "Al Jazeera",
                               "Esports", "Bilibili", "bilibili", "huya", "douyu", "虎牙", "斗鱼",
                               "Migu", "migu", "Anime", "Cartoon", "Music"]
            }
        }
    
    def extract_channel_name(self, url: str, source: str = "") -> str:
        """从URL或来源提取频道名称"""
        name = ""
        if source:
            name = source
        else:
            name = url.split('/')[-1]
            name = re.sub(r'\.(m3u8|m3u|ts)$', '', name, flags=re.IGNORECASE)
            name = re.sub(r'[_-]', ' ', name)
        
        if '?' in name:
            name = name.split('?')[0]
        
        return name.strip() or "Unknown"
    
    def classify(self, source: Dict) -> str:
        url = source.get('url', '')
        name = source.get('channel_name', '') or source.get('blogger', '')
        
        combined_text = f"{url} {name}".lower()
        
        scores = {}
        for category, rules in self.rules.items():
            score = 0
            keywords = rules.get('keywords', []) + rules.get('keywords_en', [])
            for kw in keywords:
                if kw.lower() in combined_text:
                    score += 1
            scores[category] = score
        
        if scores and max(scores.values()) > 0:
            return max(scores, key=scores.get)
        else:
            return "other"
    
    def classify_all(self, sources: List[Dict]) -> Dict[str, List[Dict]]:
        """对所有源进行分类"""
        categorized = {
            "china": [],
            "asia": [],
            "europe": [],
            "america": [],
            "other": []
        }
        
        for source in sources:
            category = self.classify(source)
            source['category'] = category
            if not source.get('channel_name'):
                source['channel_name'] = self.extract_channel_name(
                    source['url'],
                    source.get('blogger', '')
                )
            categorized[category].append(source)
        
        for category, items in categorized.items():
            logger.info(f"{category}: {len(items)} sources")
        
        return categorized
    
    def generate_m3u(self, sources: List[Dict], category: str) -> str:
        """生成M3U格式内容"""
        lines = ['#EXTM3U', '']
        
        for source in sources:
            name = source.get('channel_name', 'Unknown')
            url = source['url']
            protocol = source.get('protocol', 'http')
            
            lines.append(f'#EXTINF:-1 tvg-name="{name}" tvg-language="{category}",{name}')
            lines.append(url)
            lines.append('')
        
        return '\n'.join(lines)
    
    def save_categorized(self, categorized: Dict[str, List[Dict]]):
        """保存分类后的源"""
        sources_dir = Path('sources')
        metadata = []
        
        for category, sources in categorized.items():
            if not sources:
                continue
            
            category_dir = sources_dir / category
            category_dir.mkdir(parents=True, exist_ok=True)
            
            output_file = category_dir / 'live.m3u'
            m3u_content = self.generate_m3u(sources, category)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(m3u_content)
            
            for source in sources:
                metadata.append({
                    'name': source.get('channel_name'),
                    'url': source['url'],
                    'category': category,
                    'protocol': source.get('protocol', 'http'),
                    'checked_at': source.get('checked_at', datetime.now().isoformat())
                })
        
        metadata_file = sources_dir / 'metadata.json'
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved categorized sources to {sources_dir}")
