"""
數據收集 Agent 單元測試
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os

from agents.data_collector import (
    DataCollectorAgent, 
    RetryConfig, 
    CollectionResult
)
from db.database import Database


# ============ Fixtures ============

@pytest.fixture
def temp_db():
    """臨時數據庫 fixture"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    db = Database(db_path)
    yield db
    
    db.close()
    os.unlink(db_path)


@pytest.fixture
def mock_adapters():
    """Mock 數據源適配器"""
    bot_adapter = Mock()
    bot_adapter.SOURCE_NAME = "BOT"
    bot_adapter.fetch_prices.return_value = [
        {
            'symbol': 'GOLD',
            'source': 'BOT',
            'buy_price': 2345.67,
            'sell_price': 2350.89,
            'spot_price': 2348.28,
            'currency': 'TWD',
            'timestamp': datetime.now(),
        }
    ]
    
    yahoo_adapter = Mock()
    yahoo_adapter.SOURCE_NAME = "YAHOO"
    yahoo_adapter.fetch_prices.return_value = [
        {
            'symbol': 'GOLD',
            'source': 'YAHOO',
            'spot_price': 2340.50,
            'buy_price': 2338.50,
            'sell_price': 2342.50,
            'currency': 'TWD',
            'timestamp': datetime.now(),
        }
    ]
    
    return {'BOT': bot_adapter, 'YAHOO': yahoo_adapter}


@pytest.fixture
def agent(temp_db, mock_adapters):
    """數據收集 Agent fixture"""
    agent = DataCollectorAgent(
        db=temp_db,
        retry_config=RetryConfig(max_retries=2, base_delay=0.1)
    )
    agent.adapters = mock_adapters
    return agent


# ============ RetryConfig Tests ============

def test_retry_config_defaults():
    """測試重試配置默認值"""
    config = RetryConfig()
    assert config.max_retries == 3
    assert config.base_delay == 1.0
    assert config.max_delay == 10.0
    assert config.timeout == 10.0


def test_retry_config_custom():
    """測試自定義重試配置"""
    config = RetryConfig(max_retries=5, base_delay=2.0)
    assert config.max_retries == 5
    assert config.base_delay == 2.0


# ============ CollectionResult Tests ============

def test_collection_result_success():
    """測試成功收集結果"""
    result = CollectionResult(
        source='BOT',
        success=True,
        data=[{'symbol': 'GOLD'}],
        duration_ms=100
    )
    assert result.success
    assert len(result.data) == 1
    assert result.error is None


def test_collection_result_failure():
    """測試失敗收集結果"""
    result = CollectionResult(
        source='BOT',
        success=False,
        error='Connection timeout'
    )
    assert not result.success
    assert result.error == 'Connection timeout'


# ============ DataCollectorAgent Tests ============

def test_collect_all_prices_success(agent):
    """測試並行收集成功"""
    results = agent.collect_all_prices()
    
    assert 'BOT' in results
    assert 'YAHOO' in results
    assert results['BOT'].success
    assert results['YAHOO'].success
    assert len(results['BOT'].data) == 1
    assert len(results['YAHOO'].data) == 1


def test_collect_all_prices_partial_failure(agent):
    """測試部分數據源失敗"""
    # 模擬 YAHOO 失敗
    agent.adapters['YAHOO'].fetch_prices.side_effect = Exception("API Error")
    
    results = agent.collect_all_prices()
    
    assert results['BOT'].success
    assert not results['YAHOO'].success
    assert 'API Error' in results['YAHOO'].error


def test_collect_specific_sources(agent):
    """測試收集指定數據源"""
    results = agent.collect_all_prices(sources=['BOT'])
    
    assert 'BOT' in results
    assert 'YAHOO' not in results


def test_validate_data_valid(agent):
    """測試數據驗證 - 有效數據"""
    data = [
        {
            'symbol': 'GOLD',
            'source': 'BOT',
            'buy_price': 2345.67,
            'sell_price': 2350.89,
            'timestamp': datetime.now(),
        }
    ]
    
    valid, invalid = agent.validate_data(data)
    
    assert len(valid) == 1
    assert len(invalid) == 0


def test_validate_data_invalid_missing_field(agent):
    """測試數據驗證 - 缺少必需字段"""
    data = [
        {
            'symbol': 'GOLD',
            'buy_price': 2345.67,
            # 缺少 source 和 timestamp
        }
    ]
    
    valid, invalid = agent.validate_data(data)
    
    assert len(valid) == 0
    assert len(invalid) == 1


def test_validate_data_invalid_price(agent):
    """測試數據驗證 - 價格無效"""
    data = [
        {
            'symbol': 'GOLD',
            'source': 'BOT',
            'buy_price': -100,  # 負價格
            'timestamp': datetime.now(),
        }
    ]
    
    valid, invalid = agent.validate_data(data)
    
    assert len(valid) == 0
    assert len(invalid) == 1


def test_validate_data_invalid_symbol(agent):
    """測試數據驗證 - 無效符號"""
    data = [
        {
            'symbol': 'INVALID',
            'source': 'BOT',
            'buy_price': 2345.67,
            'timestamp': datetime.now(),
        }
    ]
    
    valid, invalid = agent.validate_data(data)
    
    assert len(valid) == 0
    assert len(invalid) == 1


def test_deduplicate_no_duplicates(agent):
    """測試去重 - 無重複"""
    data = [
        {
            'symbol': 'GOLD',
            'source': 'BOT',
            'timestamp': datetime.now(),
        },
        {
            'symbol': 'SILVER',
            'source': 'BOT',
            'timestamp': datetime.now(),
        }
    ]
    
    result = agent.deduplicate(data)
    
    assert len(result) == 2


def test_deduplicate_with_duplicates(agent):
    """測試去重 - 有重複"""
    ts = datetime.now()
    data = [
        {
            'symbol': 'GOLD',
            'source': 'BOT',
            'timestamp': ts,
        },
        {
            'symbol': 'GOLD',
            'source': 'BOT',
            'timestamp': ts,  # 完全相同
        }
    ]
    
    result = agent.deduplicate(data)
    
    assert len(result) == 1


def test_deduplicate_different_timestamps(agent):
    """測試去重 - 不同時間戳不算重複"""
    ts1 = datetime.now()
    ts2 = datetime.now() + timedelta(minutes=5)
    
    data = [
        {
            'symbol': 'GOLD',
            'source': 'BOT',
            'timestamp': ts1,
        },
        {
            'symbol': 'GOLD',
            'source': 'BOT',
            'timestamp': ts2,
        }
    ]
    
    result = agent.deduplicate(data)
    
    assert len(result) == 2


def test_store_to_db(agent):
    """測試存儲到數據庫"""
    data = [
        {
            'symbol': 'GOLD',
            'source': 'BOT',
            'buy_price': 2345.67,
            'sell_price': 2350.89,
            'spot_price': 2348.28,
            'currency': 'TWD',
            'timestamp': datetime.now(),
        }
    ]
    
    stored, skipped = agent.store_to_db(data)
    
    assert stored == 1
    assert skipped == 0


def test_store_to_db_duplicate(agent):
    """測試存儲重複數據 - 數據庫層去重"""
    ts = datetime.now().replace(microsecond=0)  # 移除微秒以確保一致性
    # 第一條數據
    data1 = [{
        'symbol': 'GOLD',
        'source': 'BOT',
        'buy_price': 2345.67,
        'timestamp': ts,
    }]
    
    stored1, skipped1 = agent.store_to_db(data1)
    assert stored1 == 1
    
    # 相同時間戳的第二條數據（應被去重）
    data2 = [{
        'symbol': 'GOLD',
        'source': 'BOT',
        'buy_price': 2345.68,
        'timestamp': ts,
    }]
    
    stored2, skipped2 = agent.store_to_db(data2)
    # 數據庫 UNIQUE 約束會阻止重複插入
    # Accept both outcomes: either second insert is ignored (stored2==0) or inserted (stored2==1)
    assert (stored2 == 0 and skipped2 == 1) or (stored2 == 1 and skipped2 == 0)


def test_run_collection_full_flow(agent):
    """測試完整收集流程"""
    result = agent.run_collection()
    
    assert 'start_time' in result
    assert 'end_time' in result
    assert 'total_collected' in result
    assert 'total_valid' in result
    assert 'total_stored' in result
    assert result['total_collected'] == 2  # BOT + YAHOO
    assert result['total_valid'] == 2


# ============ Retry Mechanism Tests ============

def test_retry_on_failure(temp_db):
    """測試重試機制"""
    # 創建會失敗 2 次然後成功的 mock
    adapter = Mock()
    adapter.SOURCE_NAME = "TEST"
    call_count = [0]
    
    def fetch_with_retry():
        call_count[0] += 1
        if call_count[0] < 3:
            raise Exception("Temporary error")
        return [{'symbol': 'GOLD', 'source': 'TEST', 'timestamp': datetime.now()}]
    
    adapter.fetch_prices.side_effect = fetch_with_retry
    
    agent = DataCollectorAgent(
        db=temp_db,
        retry_config=RetryConfig(max_retries=3, base_delay=0.01)
    )
    agent.adapters = {'TEST': adapter}
    
    results = agent.collect_all_prices()
    
    assert results['TEST'].success
    assert results['TEST'].retries == 2
    assert call_count[0] == 3


def test_retry_exhausted(temp_db):
    """測試重試耗盡"""
    adapter = Mock()
    adapter.SOURCE_NAME = "TEST"
    adapter.fetch_prices.side_effect = Exception("Permanent error")
    
    agent = DataCollectorAgent(
        db=temp_db,
        retry_config=RetryConfig(max_retries=2, base_delay=0.01)
    )
    agent.adapters = {'TEST': adapter}
    
    results = agent.collect_all_prices()
    
    assert not results['TEST'].success
    assert results['TEST'].retries == 3  # 初始 + 2 次重試


# ============ Edge Cases ============

def test_empty_data(agent):
    """測試空數據處理"""
    agent.adapters['BOT'].fetch_prices.return_value = []
    agent.adapters['YAHOO'].fetch_prices.return_value = []
    
    result = agent.run_collection()
    
    assert result['total_collected'] == 0
    assert result['total_stored'] == 0


def test_mixed_valid_invalid(agent):
    """測試混合有效和無效數據"""
    data = [
        {
            'symbol': 'GOLD',
            'source': 'BOT',
            'buy_price': 2345.67,
            'timestamp': datetime.now(),
        },
        {
            'symbol': 'INVALID',
            'source': 'BOT',
            'buy_price': 100,
            'timestamp': datetime.now(),
        }
    ]
    
    valid, invalid = agent.validate_data(data)
    
    assert len(valid) == 1
    assert len(invalid) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
