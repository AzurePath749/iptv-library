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

VIDEO_CONTENT_TYPES = {
    'video', 'application/octet-stream', 'application/x-mpegurl',
    'application/vnd.apple.mpegurl', 'application/x-m3u8',
    'application/mpegurl', 'audio'
}

class Checker:
    def __init__(self, config: dict):
        self.config = config
        self.timeout = config.get('check_timeout', 5)
        self.max_retries = config.get('max_retries', 1)
        self.log_dir = Path('logs')
        self.log_dir.mkdir(exist_ok=True)

    def _is_valid_stream(self, url: str, content: bytes, content_type: str) -> bool:
        if not content:
            return False

        ct_lower = content_type.lower() if content_type else ''

        if ct_lower and not any(ct_lower.startswith(v) for v in VIDEO_CONTENT_TYPES):
            return False

        text = content[:2048].decode('utf-8', errors='ignore')

        if '.m3u8' in url or '#EXTM3U' in text or '#EXTINF' in text:
            if re.search(r'#EXTINF.*?,', text) and (re.search(r'\.ts(?:\?\S*)?$', text, re.M) or re.search(r'\.m3u8(?:\?\S*)?$', text, re.M) or 'SEGMENT' in text):
                return True
            if re.search(r'#EXTINF', text):
                return True

        if content[:3] == b'\x00\x00\x00' and len(content) > 4:
            if content[4] in (0x00, 0x01, 0x09, 0x17, 0x1c, 0x1e):
                return True

        if b'GDFDFG' in content[:8] or b'PK\x03\x04' in content[:4]:
            return False

        if len(content) > 16 and content[4:8] in [b'ftyp', b'moov', b'mdat', b'free', b'skip', b'wide', b'pnot']:
            return True

        return len(content) > 512

    async def check_single(self, source: Dict, session: aiohttp.ClientSession) -> Tuple[str, bool, float]:
        url = source['url']
        retries = 0

        while retries <= self.max_retries:
            try:
                start_time = asyncio.get_event_loop().time()
                protocol = source.get('protocol', 'http')

                if protocol in ('http', 'https'):
                    headers = {'Range': 'bytes=0-4095', 'User-Agent': 'VLC/3.0.18'}

                    async with session.get(url, headers=headers, timeout=self.timeout, allow_redirects=True) as resp:
                        elapsed = asyncio.get_event_loop().time() - start_time

                        if resp.status in (200, 206, 301, 302, 303, 304):
                            content_type = resp.headers.get('Content-Type', '')
                            try:
                                content = await resp.read()
                            except Exception:
                                content = b''

                            if self._is_valid_stream(url, content, content_type):
                                return url, True, elapsed
                            else:
                                retries += 1
                                if retries <= self.max_retries:
                                    await asyncio.sleep(0.5)
                                    continue
                                return url, False, elapsed
                        else:
                            retries += 1
                            if retries <= self.max_retries:
                                await asyncio.sleep(0.5)
                                continue
                            return url, False, elapsed
                else:
                    elapsed = asyncio.get_event_loop().time() - start_time
                    return url, True, elapsed

            except asyncio.TimeoutError:
                elapsed = asyncio.get_event_loop().time() - start_time
                retries += 1
                if retries <= self.max_retries:
                    await asyncio.sleep(0.5)
                    continue
                return url, False, elapsed

            except Exception as e:
                elapsed = asyncio.get_event_loop().time() - start_time
                retries += 1
                if retries <= self.max_retries:
                    await asyncio.sleep(0.5)
                    continue
                return url, False, elapsed

        return url, False, self.timeout

    async def check_batch(self, sources: List[Dict]) -> Dict[str, Dict]:
        results = {}
        semaphore = asyncio.Semaphore(30)
        timeout = aiohttp.ClientTimeout(total=5, connect=3)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async def check_with_semaphore(source):
                async with semaphore:
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
        raw_dir = Path('raw')
        if not raw_dir.exists():
            return []

        latest_file = max(raw_dir.glob('sources_*.json'), default=None)
        if not latest_file:
            return []

        with open(latest_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    async def check_all(self) -> Dict[str, Dict]:
        sources = self.load_raw_sources()
        logger.info(f"Checking {len(sources)} sources...")

        results = await self.check_batch(sources)

        valid_count = sum(1 for r in results.values() if r['valid'])
        logger.info(f"Valid: {valid_count}/{len(results)}")

        self._save_results(results)
        return results

    def _save_results(self, results: Dict):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = self.log_dir / f'check_results_{timestamp}.json'

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved check results to {output_file}")

    def get_valid_sources(self, results: Dict) -> List[Dict]:
        valid = []
        for url, result in results.items():
            if result['valid']:
                source = results[url].copy()
                valid.append(source)
        return valid
