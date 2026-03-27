# -*- coding: utf-8 -*-
import asyncio
import aiohttp
import json
import re
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Checker:
    def __init__(self, config: dict):
        self.config = config
        self.timeout = config.get('check_timeout', 10)
        self.max_retries = config.get('max_retries', 2)
        self.log_dir = Path('logs')
        self.log_dir.mkdir(exist_ok=True)
        
    async def check_single(self, source: Dict, session: aiohttp.ClientSession) -> Tuple[str, bool, float]:
        """检查单个源是否可用"""
        url = source['url']
        retries = 0
        
        while retries <= self.max_retries:
            try:
                start_time = asyncio.get_event_loop().time()
                protocol = source.get('protocol', 'http')
                
                if protocol in ('http', 'https'):
                    async with session.head(url, timeout=self.timeout, allow_redirects=True) as resp:
                        elapsed = asyncio.get_event_loop().time() - start_time
                        if resp.status in (200, 301, 302, 303, 304):
                            return url, True, elapsed
                        else:
                            retries += 1
                            if retries <= self.max_retries:
                                await asyncio.sleep(1)
                                continue
                            return url, False, elapsed
                else:
                    elapsed = asyncio.get_event_loop().time() - start_time
                    return url, True, elapsed
                    
            except asyncio.TimeoutError:
                elapsed = asyncio.get_event_loop().time() - start_time
                logger.debug(f"Timeout checking {url}")
                retries += 1
                if retries <= self.max_retries:
                    await asyncio.sleep(1)
                    continue
                return url, False, elapsed
                
            except Exception as e:
                elapsed = asyncio.get_event_loop().time() - start_time
                logger.debug(f"Error checking {url}: {e}")
                retries += 1
                if retries <= self.max_retries:
                    await asyncio.sleep(1)
                    continue
                return url, False, elapsed
        
        return url, False, self.timeout
    
    async def check_batch(self, sources: List[Dict]) -> Dict[str, Dict]:
        """批量检查源"""
        results = {}
        semaphore = asyncio.Semaphore(10)
        
        async def check_with_semaphore(source):
            async with semaphore:
                async with aiohttp.ClientSession() as session:
                    return await self.check_single(source, session)
        
        tasks = [check_with_semaphore(s) for s in sources]
        batch_results = await asyncio.gather(*tasks)
        
        for url, is_valid, response_time in batch_results:
            results[url] = {
                'url': url,
                'valid': is_valid,
                'response_time': round(response_time, 2),
                'checked_at': datetime.now().isoformat()
            }
        
        return results
    
    def load_raw_sources(self) -> List[Dict]:
        """加载原始源"""
        raw_dir = Path('raw')
        if not raw_dir.exists():
            return []
        
        latest_file = max(raw_dir.glob('sources_*.json'), default=None)
        if not latest_file:
            return []
        
        with open(latest_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    async def check_all(self) -> Dict[str, Dict]:
        """检查所有源"""
        sources = self.load_raw_sources()
        logger.info(f"Checking {len(sources)} sources...")
        
        results = await self.check_batch(sources)
        
        valid_count = sum(1 for r in results.values() if r['valid'])
        logger.info(f"Valid: {valid_count}/{len(results)}")
        
        self._save_results(results)
        return results
    
    def _save_results(self, results: Dict):
        """保存检查结果"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = self.log_dir / f'check_results_{timestamp}.json'
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved check results to {output_file}")
    
    def get_valid_sources(self, results: Dict) -> List[Dict]:
        """获取有效源列表"""
        valid = []
        for url, result in results.items():
            if result['valid']:
                source = results[url].copy()
                valid.append(source)
        return valid
