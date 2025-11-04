import sqlite3
import os
from typing import Any, Optional, TypeVar, Union

T = TypeVar('T')

class CfgKeys:
    PLAYER_PLAY_MODE = "player_play_mode"  
    PLAYER_PLAY_DELAY_TIME = 'player_play_delay_time'
    MIDI_DIR = 'midi_dir'
    MIDI_LAST_CFG_ID = 'midi_last_cfg_id'

class CfgVals:
    PLAYER_PLAY_MODE_AUTO_NEXT = 'auto_next'
    PLAYER_PLAY_MODE_SINGLE_LOOP = 'single_loop'


class SQLiteConfigController:
    """精简版带类型校验的SQLite配置管理（单例模式）"""
    _instance = None

    def __new__(cls, db_path: str = None):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, db_path: str = None):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self.db_path = db_path or os.path.join(os.path.dirname(__file__), "config.db")
        self._init_table()

    def _init_table(self) -> None:
        """初始化配置表（仅执行一次）"""
        self._execute("""
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                type TEXT NOT NULL  -- 存储值的原始类型（int/float/bool/str）
            )
        """)

    def _execute(self, sql: str, params: tuple = (), commit: bool = True) -> Any:
        """通用数据库操作：执行SQL，自动处理连接和事务"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            result = cursor.execute(sql, params)
            if commit:
                conn.commit()
            return result

    # ------------------------------
    # 序列化/反序列化（精简版）
    # ------------------------------
    def _serialize(self, value: Any) -> tuple[str, str]:
        """序列化值并返回 (字符串, 类型名)"""
        if isinstance(value, int):
            return str(value), "int"
        elif isinstance(value, float):
            return str(value), "float"
        elif isinstance(value, bool):
            return "true" if value else "false", "bool"
        elif isinstance(value, str):
            return value, "str"
        raise TypeError(f"不支持的类型：{type(value)}")

    def _deserialize(self, value_str: str, target_type: type) -> Any:
        """按目标类型反序列化，失败返回None"""
        try:
            if target_type is int:
                return int(value_str)
            elif target_type is float:
                return float(value_str)
            elif target_type is bool:
                return value_str.lower() == "true"
            return value_str  # str类型直接返回
        except (ValueError, TypeError):
            return None

    def set(self, key: str, value: Union[str, int, float, bool]) -> None:
        """通用写入（自动识别类型）"""
        value_str, type_name = self._serialize(value)
        self._execute(
            "INSERT OR REPLACE INTO config (key, value, type) VALUES (?, ?, ?)",
            (key, value_str, type_name)
        )

    # ------------------------------
    # 类型化查询（按默认值推断类型）
    # ------------------------------
    def get(self, key: str, default: T) -> T:
        """根据默认值类型返回对应类型的配置"""
        result = self._execute("SELECT value FROM config WHERE key = ?", (key,), commit=False).fetchone()
        if not result:
            return default
        # 反序列化并返回（失败则用默认值）
        deserialized = self._deserialize(result[0], type(default))
        return deserialized if deserialized is not None else default

    # ------------------------------
    # 辅助方法（精简版）
    # ------------------------------
    def delete(self, key: str) -> bool:
        """删除配置，返回是否成功"""
        cursor = self._execute("DELETE FROM config WHERE key = ?", (key,))
        return cursor.rowcount > 0

    def exists(self, key: str) -> bool:
        """检查配置是否存在"""
        return self._execute(
            "SELECT 1 FROM config WHERE key = ? LIMIT 1", (key,), commit=False
        ).fetchone() is not None

    def get_type(self, key: str) -> Optional[str]:
        """获取配置的原始类型"""
        result = self._execute(
            "SELECT type FROM config WHERE key = ?", (key,), commit=False
        ).fetchone()
        return result[0] if result else None


# 全局配置对象
global_config_controller = SQLiteConfigController()