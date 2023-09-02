from loguru import logger
from .connector import DatabaseConnector
from source.utils.models import User, VpnConfigDB
from datetime import datetime
from source.data import config


class Selector(DatabaseConnector):
    def __init__(self) -> None:
        super().__init__()
        logger.debug("Selector object was initialized")

    async def get_user_by_id(self, user_id: int) -> User:
        (
            username,
            is_banned,
            subscription_end_date,
            created_at,
        ) = await self._get_user_base_info_by_id(user_id)
        if not created_at:
            raise ValueError(f"User {user_id} not found")
        created_configs_count = await self._get_created_configs_count_by_user_id(
            user_id
        )
        bonus_configs_count = await self._get_bonus_configs_count_by_user_id(user_id)
        unused_configs_count = (
            config.default_max_configs_count
            + bonus_configs_count
            - created_configs_count
        )
        is_active_subscription: bool = subscription_end_date >= datetime.now().date()
        user = User(
            user_id=user_id,
            username=username,
            is_not_banned="🟢" if not is_banned else "🔴",
            is_active_subscription="🟢" if is_active_subscription else "🔴",
            subscription_end_date=subscription_end_date,
            configs_count=created_configs_count,
            bonus_configs_count=bonus_configs_count,
            unused_configs_count=unused_configs_count,
            created_at=created_at,
        )
        return user

    async def _get_user_base_info_by_id(
        self, user_id: int
    ) -> tuple[str, bool, datetime, datetime] | tuple[None, None, None, None]:
        query = f"""--sql
            SELECT username, is_banned, subscription_end_date, created_at
            FROM users
            WHERE user_id = {user_id};
        """
        result = await self._execute_query(query)
        if result == []:
            logger.error(f"User {user_id} not found")
            return None, None, None, None
        username, is_banned, subscription_end_date, created_at = result[0]
        logger.debug(f"User {user_id} base info was fetched")
        return username, is_banned, subscription_end_date, created_at

    async def _get_created_configs_count_by_user_id(self, user_id: int) -> int:
        query = f"""--sql
            SELECT COUNT(*)
            FROM vpn_configs
            WHERE user_id = {user_id};
        """
        result = await self._execute_query(query)
        logger.debug(
            f"Created configs count for user {user_id} was fetched: {result[0][0]}"
        )
        return result[0][0]

    async def _get_bonus_configs_count_by_user_id(self, user_id: int) -> int:
        query = f"""--sql
            SELECT bonus_config_count
            FROM bonus_configs_for_users
            WHERE user_id = {user_id};
        """
        result = await self._execute_query(query)
        logger.debug(f"Bonus configs count for user {user_id} was fetched: {result}")
        return result[0][0] if result else 0

    async def is_user_registered(self, user_id: int) -> bool:
        query = f"""--sql
            SELECT EXISTS(
                SELECT 1
                FROM users
                WHERE user_id = {user_id}
            );
        """
        result = await self._execute_query(query)
        logger.debug(f"User {user_id} exist: {result[0][0]}")
        return result[0][0]

    async def is_user_have_any_config(self, user_id: int) -> bool:
        query = f"""--sql
            SELECT EXISTS(
                SELECT 1
                FROM vpn_configs
                WHERE user_id = {user_id}
            );
        """
        result = await self._execute_query(query)
        logger.debug(f"User {user_id} have any config: {result[0][0]}")
        return result[0][0]

    async def get_user_config_names_and_uuids(
        self, user_id: int
    ) -> list[VpnConfigDB] | None:
        query = f"""--sql
            SELECT id, config_name, config_uuid
            FROM vpn_configs
            WHERE user_id = {user_id};
        """
        result = await self._execute_query(query)
        logger.debug(f"User {user_id} configs: {result}")
        if not result:
            return None
        return [
            VpnConfigDB(
                config_id=record[0],
                user_id=user_id,
                config_name=record[1],
                config_uuid=record[2],
            )
            for record in result
        ]

    async def how_much_more_configs_user_can_create(self, user_id: int) -> int:
        bonus_configs_count = await self._get_bonus_configs_count_by_user_id(user_id)
        created_configs_count = await self._get_created_configs_count_by_user_id(
            user_id
        )
        unused_configs_count = (
            config.default_max_configs_count
            + bonus_configs_count
            - created_configs_count
        )
        logger.debug(f"User {user_id} can create {unused_configs_count} more configs")
        return unused_configs_count
