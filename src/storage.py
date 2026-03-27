# -*- coding: utf-8 -*-
import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Storage:
    def __init__(self, config: dict):
        self.config = config
        self.sources_dir = Path('sources')
        self.metadata_file = self.sources_dir / 'metadata.json'
        self.stability_days = config.get('stability_days', 3)
        
    def load_metadata(self) -> List[Dict]:
        """加载元数据"""
        if not self.metadata_file.exists():
            return []
        
        with open(self.metadata_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def save_metadata(self, metadata: List[Dict]):
        """保存元数据"""
        self.sources_dir.mkdir(parents=True, exist_ok=True)
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    def update_source_status(self, url: str, is_valid: bool, check_time: str):
        """更新源状态"""
        metadata = self.load_metadata()
        
        found = False
        for source in metadata:
            if source['url'] == url:
                source['last_checked'] = check_time
                source['status'] = 'valid' if is_valid else 'invalid'
                found = True
                break
        
        if not found:
            metadata.append({
                'url': url,
                'status': 'valid' if is_valid else 'invalid',
                'first_seen': check_time,
                'last_checked': check_time,
                'consecutive_valid': 1 if is_valid else 0
            })
        
        self.save_metadata(metadata)
    
    def get_stable_sources(self) -> List[str]:
        """获取稳定源（连续N天可用）"""
        metadata = self.load_metadata()
        stable = []
        
        for source in metadata:
            if source.get('status') == 'valid':
                last_checked = source.get('last_checked', '')
                if last_checked:
                    try:
                        checked_date = datetime.fromisoformat(last_checked)
                        days_ago = (datetime.now() - checked_date).days
                        if days_ago <= 1:
                            stable.append(source['url'])
                    except:
                        pass
        
        return stable
    
    def get_history(self, url: str, days: int = 7) -> List[Dict]:
        """获取源的历史检查记录"""
        logs_dir = Path('logs')
        history = []
        
        if not logs_dir.exists():
            return history
        
        for log_file in sorted(logs_dir.glob('check_results_*.json'))[-days:]:
            with open(log_file, 'r', encoding='utf-8') as f:
                results = json.load(f)
                if url in results:
                    history.append(results[url])
        
        return history
    
    def get_source_stats(self) -> Dict:
        """获取源统计信息"""
        metadata = self.load_metadata()
        
        total = len(metadata)
        valid = sum(1 for s in metadata if s.get('status') == 'valid')
        invalid = sum(1 for s in metadata if s.get('status') == 'invalid')
        
        categories = {}
        for source in metadata:
            cat = source.get('category', 'other')
            categories[cat] = categories.get(cat, 0) + 1
        
        return {
            'total': total,
            'valid': valid,
            'invalid': invalid,
            'by_category': categories
        }
    
    def cleanup_old_logs(self, keep_days: int = 7):
        """清理旧日志"""
        logs_dir = Path('logs')
        if not logs_dir.exists():
            return
        
        cutoff = datetime.now() - timedelta(days=keep_days)
        
        for log_file in logs_dir.glob('*.json'):
            if log_file.stat().st_mtime < cutoff.timestamp():
                log_file.unlink()
                logger.info(f"Removed old log: {log_file}")
