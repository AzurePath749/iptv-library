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
        logger.info("Fetching sources from bloggers...")
        sources = await self.fetcher.fetch_all()
        logger.info(f"Fetched {len(sources)} unique sources")
        return sources
    
    async def check(self):
        logger.info("Checking source availability...")
        results = await self.checker.check_all()
        valid_count = sum(1 for r in results.values() if r.get('valid'))
        logger.info(f"Valid: {valid_count}/{len(results)}")
        return results
    
    def classify(self, sources: list):
        logger.info("Classifying sources...")
        categorized = self.classifier.classify_all(sources)
        self.classifier.save_categorized(categorized)
        
        for category, items in categorized.items():
            logger.info(f"  {category}: {len(items)} sources")
        
        return categorized
    
    async def run_full(self):
        sources = await self.fetch()
        results = await self.checker.check_batch(sources)
        
        valid_sources = [
            {**source, 'checked_at': results[url]['checked_at']}
            for url, source_dict in {s['url']: s for s in sources}.items()
            for url, result in results.items()
            if result.get('valid') and url in {s['url'] for s in sources}
        ]
        
        url_to_source = {s['url']: s for s in sources}
        valid_sources = []
        for url, result in results.items():
            if result.get('valid') and url in url_to_source:
                source = {**url_to_source[url]}
                source['checked_at'] = result.get('checked_at', '')
                source['response_time'] = result.get('response_time', 0)
                valid_sources.append(source)
        
        logger.info(f"Found {len(valid_sources)} valid sources")
        self.classify(valid_sources)
        logger.info("Done!")
    
    def stats(self):
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
        sources = manager.checker.load_raw_sources()
        manager.classify(sources)
    elif args.action == 'run':
        await manager.run_full()
    elif args.action == 'stats':
        manager.stats()

if __name__ == '__main__':
    asyncio.run(main())
