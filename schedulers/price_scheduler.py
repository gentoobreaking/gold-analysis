"""
價格數據定時調度器
支持 OpenClaw cron 和 Python schedule
"""
import time
import logging
import signal
import sys
from datetime import datetime
from typing import Callable, Optional
import schedule

from agents.data_collector import DataCollectorAgent

logger = logging.getLogger(__name__)


class PriceScheduler:
    """價格收集調度器"""
    
    def __init__(self, agent: DataCollectorAgent = None):
        """
        初始化調度器
        
        Args:
            agent: 數據收集 Agent 實例
        """
        self.agent = agent or DataCollectorAgent()
        self._running = False
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self):
        """設置信號處理器"""
        def handle_shutdown(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            self.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, handle_shutdown)
        signal.signal(signal.SIGTERM, handle_shutdown)
    
    def add_job(self, interval: str, job_func: Callable):
        """
        添加定時任務
        
        Args:
            interval: 間隔時間 (如 '5m', '1h', '1d')
            job_func: 任務函數
        """
        # 解析間隔
        unit = interval[-1].lower()
        value = int(interval[:-1])
        
        if unit == 's':  # 秒
            schedule.every(value).seconds.do(job_func)
        elif unit == 'm':  # 分鐘
            schedule.every(value).minutes.do(job_func)
        elif unit == 'h':  # 小時
            schedule.every(value).hours.do(job_func)
        elif unit == 'd':  # 天
            schedule.every(value).days.do(job_func)
        else:
            raise ValueError(f"Unknown interval unit: {unit}")
        
        logger.info(f"Scheduled job every {interval}")
    
    def setup_default_schedule(self):
        """設置默認調度計劃"""
        # 每 5 分鐘收集一次
        self.add_job('5m', self._collect_job)
        
        # 每小時整點收集
        schedule.every().hour.at(':00').do(self._collect_job)
        
        logger.info("Default schedule setup complete")
    
    def _collect_job(self):
        """收集任務"""
        try:
            logger.info("Starting scheduled collection...")
            result = self.agent.run_collection()
            
            logger.info(
                f"Collection completed: "
                f"{result['total_stored']} stored, "
                f"{len(result['errors'])} errors"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Collection job failed: {e}")
            return None
    
    def run_forever(self):
        """持續運行調度器"""
        self._running = True
        logger.info("Scheduler started, running forever...")
        
        while self._running:
            schedule.run_pending()
            time.sleep(1)
    
    def run_once(self):
        """執行一次調度"""
        logger.info("Running scheduler once...")
        return self._collect_job()
    
    def stop(self):
        """停止調度器"""
        self._running = False
        logger.info("Scheduler stopped")
    
    def close(self):
        """關閉資源"""
        self.stop()
        self.agent.close()


def create_openclaw_cron_config() -> dict:
    """
    創建 OpenClaw cron 配置
    
    Returns:
        OpenClaw cron 配置字典
    """
    return {
        "jobs": [
            {
                "id": "gold-price-collector",
                "schedule": "*/5 * * * *",  # 每 5 分鐘
                "command": "python -m agents.data_collector",
                "description": "收集黃金價格數據",
                "enabled": True
            },
            {
                "id": "gold-price-hourly",
                "schedule": "0 * * * *",  # 每小時整點
                "command": "python -m agents.data_collector",
                "description": "每小時收集黃金價格",
                "enabled": True
            }
        ]
    }


def run_with_schedule():
    """使用 schedule 庫運行"""
    scheduler = PriceScheduler()
    scheduler.setup_default_schedule()
    
    try:
        scheduler.run_forever()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        scheduler.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Price data scheduler')
    parser.add_argument(
        '--mode',
        choices=['once', 'schedule', 'config'],
        default='once',
        help='Run mode: once (single run), schedule (continuous), config (print OpenClaw config)'
    )
    parser.add_argument(
        '--interval',
        default='5m',
        help='Collection interval (e.g., 5m, 1h, 1d)'
    )
    
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    if args.mode == 'config':
        import json
        config = create_openclaw_cron_config()
        print(json.dumps(config, indent=2))
        
    elif args.mode == 'schedule':
        run_with_schedule()
        
    else:  # once
        scheduler = PriceScheduler()
        result = scheduler.run_once()
        print(f"Result: {result}")
        scheduler.close()
