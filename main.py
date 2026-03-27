# -*- coding: utf-8 -*-
import asyncio
import argparse
import logging
from pathlib import Path

from src.fetcher import Fetcher
from src.checker import Checker
from src.classifier import Classifier
from src.storage import Storage
from config import Config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class IPTVManager:
    def __init__(self):
        self.config = {
            'check_timeout': Config.check_timeout,
            'max_retries': Config.max_retries,
            'stability_days': Config.stability_days,
            'bloggers_file': Config.bloggers_file
        }
        self.fetcher = Fetcher(self.config)
        self.checker = Checker(self.config)
        self.classifier = Classifier(self.config)
        self.storage = Storage(self.config)
    
    async def fetch(self):
        """抓取直播源"""
        logger.info("Fetching sources from bloggers...")
        sources = await self.fetcher.fetch_all()
        logger.info(f"Fetched {len(sources)} unique sources")
        return sources
    
    async def check(self):
        """检查源可用性"""
        logger.info("Checking source availability...")
        results = await self.checker.check_all()
        return results
    
    def classify(self, sources: list):
        """分类并保存"""
        logger.info("Classifying sources...")
        categorized = self.classifier.classify_all(sources)
        self.classifier.save_categorized(categorized)
        
        for category, items in categorized.items():
            logger.info(f"  {category}: {len(items)} sources")
        
        return categorized
    
    async def run_full(self):
        """完整流程"""
        sources = await self.fetch()
        results = await self.check()
        
        valid_sources = [
            {**{'url': url}, **result} 
            for url, result in results.items() 
            if result.get('valid')
        ]
        
        for source in valid_sources:
            source['url'] = source['url']
            source['protocol'] = self._get_protocol(source['url'])
        
        self.classify(valid_sources)
        logger.info("Done!")
    
    def _get_protocol(self, url: str) -> str:
        if url.startswith('https://'):
            return 'https'
        elif url.startswith('http://'):
            return 'http'
        elif url.startswith('rtmp://'):
            return 'rtmp'
        elif url.startswith('rtsp://'):
            return 'rtsp'
        return 'unknown'
    
    def stats(self):
        """显示统计信息"""
        stats = self.storage.get_source_stats()
        logger.info("=== Source Statistics ===")
        logger.info(f"Total: {stats['total']}")
        logger.info(f"Valid: {stats['valid']}")
        logger.info(f"Invalid: {stats['invalid']}")
        logger.info("By Category:")
        for cat, count in stats.get('by_category', {}).items():
            logger.info(f"  {cat}: {count}")

async def main():
    parser = argparse.ArgumentParser(description='IPTV Source Manager')
    parser.add_argument('action', choices=['fetch', 'check', 'classify', 'run', 'stats'],
                       help='Action to perform')
    args = parser.parse_args()
    
    manager = IPTVManager()
    
    if args.action == 'fetch':
        await manager.fetch()
    elif args.action == 'check':
        await manager.check()
    elif args.action == 'classify':
        manager.classify([])
    elif args.action == 'run':
        await manager.run_full()
    elif args.action == 'stats':
        manager.stats()

if __name__ == '__main__':
    asyncio.run(main())