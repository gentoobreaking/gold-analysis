# @deprecated — backend/app is the canonical source of truth.
# Legacy duplicate; do not use for new development.
# See docs/CODEBASE_CONSOLIDATION.md.
"""
數據適配器模組
"""
from .bot_adapter import BotBankAdapter
from .yahoo_finance_adapter import YahooFinanceAdapter

__all__ = ['BotBankAdapter', 'YahooFinanceAdapter']
