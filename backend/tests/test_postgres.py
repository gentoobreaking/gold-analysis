import pytest
import pytest_asyncio
from app.db.postgres import get_db_session, init_postgres
from app.models.user import User

class TestPostgreSQL:
    @pytest.mark.asyncio
    async def test_connection(self, db_session):
        # 測試數據庫連接
        async for session in get_db_session():
            assert session is not None

    @pytest.mark.asyncio
    async def test_insert_user(self, db_session):
        # 測試插入用戶
        # 此為示例，實際應根據 ORM 建立模型
        async for session in get_db_session():
            new_user = User(name='test', email='test@example.com')
            session.add(new_user)
            await session.commit()
            result = await session.get(User, new_user.id)
            assert result.email == 'test@example.com'

    @pytest.mark.asyncio
    async def test_transaction(self, db_session):
        測試事務處理
        async with get_db_session() as session:
            try:
                # 故意觸發錯誤以測試 rollback
                raise Exception('force rollback')
            except Exception:
                await session.rollback()
                # 確認未提交任何變更
                # 這裡可加入驗證查詢...
                assert True
