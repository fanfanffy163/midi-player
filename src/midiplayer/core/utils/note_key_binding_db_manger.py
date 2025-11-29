import json
import sqlite3
from typing import Dict, List, Optional

from loguru import logger

from .utils import Utils

# --- 数据库管理器 ---


class DBManager:
    """处理所有SQLite数据库操作"""

    def __init__(self, db_name=str(Utils.user_path("db.db"))):
        self.db_name = db_name
        self.conn = sqlite3.connect(self.db_name)
        self.create_table()

    def create_table(self):
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS presets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    mappings TEXT NOT NULL
                );
                """
            )

            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS track_settings (
                    file_path TEXT PRIMARY KEY,
                    active_tracks TEXT
                );
                """
            )

    def save_preset(self, name: str, mappings: Dict[str, str]) -> bool:
        """保存或更新一个预设。"""
        mappings_json = json.dumps(mappings)
        try:
            with self.conn:
                self.conn.execute(
                    "INSERT OR REPLACE INTO presets (name, mappings) VALUES (?, ?)",
                    (name, mappings_json),
                )
            return True
        except sqlite3.Error as e:
            logger.opt(exception=e).error(f"数据库保存错误: {e}")
            return False

    def load_preset(self, name: str) -> Optional[Dict[str, str]]:
        """根据名称加载一个预设。"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT mappings FROM presets WHERE name = ?", (name,))
        row = cursor.fetchone()
        if row:
            return json.loads(row[0])
        return None

    def delete_preset(self, name: str) -> bool:
        """删除一个预设。"""
        try:
            with self.conn:
                self.conn.execute("DELETE FROM presets WHERE name = ?", (name,))
            return True
        except sqlite3.Error as e:
            logger.opt(exception=e).error(f"数据库删除错误: {e}")
            return False

    def list_presets(self, search_query: str = "") -> List[str]:
        """列出所有预设名称，可选地根据查询进行过滤。"""
        cursor = self.conn.cursor()
        if search_query:
            query = "SELECT name FROM presets WHERE name LIKE ? ORDER BY name"
            cursor.execute(query, (f"%{search_query}%",))
        else:
            query = "SELECT name FROM presets ORDER BY name"
            cursor.execute(query)

        return [row[0] for row in cursor.fetchall()]

    def duplicate_preset(self, old_name: str, new_name: str) -> bool:
        """复制一个预设。"""
        mappings = self.load_preset(old_name)
        if mappings is None:
            return False

        if self.load_preset(new_name) is not None:
            # 新名称已存在
            return False

        return self.save_preset(new_name, mappings)

    def get_active_tracks(self, file_path: str) -> list[int] | None:
        """获取某首歌的激活音轨列表，如果没有记录返回 None"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT active_tracks FROM track_settings WHERE file_path = ?",
                (file_path,),
            )
            row = cursor.fetchone()
            if row:
                # 数据库里存的是 "[1, 2, 3]" 这种字符串，取出来转回 list
                return json.loads(row[0])
        except Exception as e:
            logger.error(f"读取音轨配置失败: {e}")
        return None

    def save_active_tracks(self, file_path: str, tracks: list[int]):
        """保存或更新音轨配置"""
        try:
            tracks_json = json.dumps(tracks)
            with self.conn:
                # INSERT OR REPLACE: 如果路径存在就更新，不存在就插入
                self.conn.execute(
                    """
                    INSERT OR REPLACE INTO track_settings (file_path, active_tracks)
                    VALUES (?, ?)
                """,
                    (file_path, tracks_json),
                )
        except Exception as e:
            logger.error(f"保存音轨配置失败: {e}")

    def __del__(self):
        self.conn.close()
