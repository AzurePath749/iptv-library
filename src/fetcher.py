# -*- coding: utf-8 -*-
import json
import re
import aiohttp
import asyncio
from pathlib import Path
from typing import List, Dict, Set
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Fetcher:
    def __init__(self, config: dict):
        self.config = config
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.raw_dir = Path('raw')
        self.raw_dir.mkdir(exist_ok=True)
        
    def load_bloggers(self) -> List[Dict]:
        """加载配置的博主列表"""
        bloggers_file = self.config.get('bloggers_file', 'bloggers.json')
        try:
            with open(bloggers_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return []
    
    async def fetch_raw(self, url: str, session: aiohttp.ClientSession) -> str:
        """获取原始内容"""
        try:
            async with session.get(url, headers=self.headers, timeout=30) as resp:
                if resp.status == 200:
                    return await resp.text()
                logger.warning(f"Failed to fetch {url}: {resp.status}")
                return ""
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return ""
    
    def extract_m3u_urls(self, content: str) -> List[str]:
        """从m3u内容提取直播URL"""
        urls = []
        for line in content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                if self._is_valid_url(line):
                    urls.append(line)
        return urls
    
    def _is_valid_url(self, url: str) -> bool:
        """验证是否为有效的直播源URL"""
        if not url.startswith(('http://', 'https://', 'rtmp://', 'rtsp://')):
            return False
        private_ip_patterns = [
            r'^192\.168\.\d+\.\d+',
            r'^10\.\d+\.\d+\.\d+',
            r'^172\.(1[6-9]|2\d|3[01])\.\d+\.\d+',
            r'^127\.\d+\.\d+\.\d+',
            r'^localhost',
        ]
        for pattern in private_ip_patterns:
            if re.match(pattern, url, re.I):
                return False
        return True
    
    def extract_repo_urls(self, content: str) -> List[str]:
        """从页面提取GitHub仓库URL"""
        repo_pattern = r'https://github\.com/[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+'
        return list(set(re.findall(repo_pattern, content)))
    
    async def fetch_from_blogger(self, blogger: Dict, session: aiohttp.ClientSession) -> List[Dict]:
        """从博主获取直播源"""
        sources = []
        name = blogger.get('name', 'unknown')
        urls = blogger.get('urls', [])
        
        for url in urls:
            content = await self.fetch_raw(url, session)
            if content:
                extracted_urls = self.extract_m3u_urls(content)
                for stream_url in extracted_urls:
                    sources.append({
                        'url': stream_url,
                        'source': url,
                        'blogger': name,
                        'added_time': datetime.now().isoformat(),
                        'protocol': self._get_protocol(stream_url)
                    })
        
        logger.info(f"Fetched {len(sources)} sources from {name}")
        return sources
    
    def _get_protocol(self, url: str) -> str:
        """获取协议类型"""
        if url.startswith('https://'):
            return 'https'
        elif url.startswith('http://'):
            return 'http'
        elif url.startswith('rtmp://'):
            return 'rtmp'
        elif url.startswith('rtsp://'):
            return 'rtsp'
        return 'unknown'
    
    async def fetch_all(self) -> List[Dict]:
        """从所有博主获取直播源"""
        bloggers = self.load_bloggers()
        all_sources = []
        
        async with aiohttp.ClientSession() as session:
            tasks = [self.fetch_from_blogger(b, session) for b in bloggers]
            results = await asyncio.gather(*tasks)
            for result in results:
                all_sources.extend(result)
        
        all_sources = self._deduplicate(all_sources)
        self._save_raw_sources(all_sources)
        return all_sources
    
    def _deduplicate(self, sources: List[Dict]) -> List[Dict]:
        """去重"""
        seen = set()
        unique = []
        for source in sources:
            url = source['url']
            if url not in seen:
                seen.add(url)
                unique.append(source)
        return unique
    
    def _save_raw_sources(self, sources: List[Dict]):
        """保存原始源"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = self.raw_dir / f'sources_{timestamp}.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(sources, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved {len(sources)} raw sources to {output_file}")
