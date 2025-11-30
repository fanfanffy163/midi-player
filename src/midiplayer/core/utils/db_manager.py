import json
import sqlite3
from typing import Optional

from loguru import logger

from midiplayer.core.utils.utils import Utils

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

    def save_preset(self, name: str, mappings: dict[str, str]) -> bool:
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

    def save_presets_batch(self, presets_list: list[dict]) -> dict[str, int]:
        """
        批量保存预设。

        返回:
            {"inserted": int, "updated": int, "failed": int}
        """
        inserted = 0
        updated = 0
        failed = 0

        if not presets_list:
            return {"inserted": 0, "updated": 0, "failed": 0}

        try:
            cursor = self.conn.cursor()

            # 1. 获取现有名称，仅用于统计是"新增"还是"覆盖"
            # 实际的覆盖操作由 SQL 处理
            cursor.execute("SELECT name FROM presets")
            existing_names = {row[0] for row in cursor.fetchall()}

            data_to_insert = []

            # 2. 准备数据
            for item in presets_list:
                name = item.get("name")
                mappings = item.get("mappings")

                if not name or mappings is None:
                    failed += 1
                    continue

                # 统计逻辑
                if name in existing_names:
                    updated += 1
                else:
                    inserted += 1

                # 无论是否存在，都添加到待执行列表
                try:
                    json_str = json.dumps(mappings)
                    data_to_insert.append((name, json_str))
                except Exception as e:
                    logger.error(f"序列化预设 '{name}' 失败: {e}")
                    failed += 1

            # 3. 开启事务并批量执行
            if data_to_insert:
                # 使用 INSERT OR REPLACE 实现：不存在则插入，存在则更新
                cursor.executemany(
                    "INSERT OR REPLACE INTO presets (name, mappings) VALUES (?, ?)",
                    data_to_insert,
                )

            # 提交事务
            self.conn.commit()

        except sqlite3.Error as e:
            logger.opt(exception=e).error(f"批量保存数据库错误: {e}")
            self.conn.rollback()
            # 事务回滚，所有操作都视为失败
            return {"inserted": 0, "updated": 0, "failed": len(presets_list)}

        return {"inserted": inserted, "updated": updated, "failed": failed}

    def load_preset(self, name: str) -> Optional[dict[str, str]]:
        """根据名称加载一个预设。"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT mappings FROM presets WHERE name = ?", (name,))
        row = cursor.fetchone()
        if row:
            return json.loads(row[0])
        return None

    def load_all_presets(self) -> list[dict]:
        """
        批量获取所有预设，用于导出。
        返回格式: [{"name": "预设A", "mappings": {...}}, ...]
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT name, mappings FROM presets")
            rows = cursor.fetchall()

            result = []
            for row in rows:
                try:
                    name = row[0]
                    # 解析 JSON 字符串
                    mappings_data = json.loads(row[1])

                    result.append({"name": name, "mappings": mappings_data})
                except Exception as e:
                    logger.error(f"解析预设 '{row[0]}' 失败: {e}")
                    continue
            return result
        except sqlite3.Error as e:
            logger.opt(exception=e).error(f"批量加载失败: {e}")
            return []

    def delete_preset(self, name: str) -> bool:
        """删除一个预设。"""
        try:
            with self.conn:
                self.conn.execute("DELETE FROM presets WHERE name = ?", (name,))
            return True
        except sqlite3.Error as e:
            logger.opt(exception=e).error(f"数据库删除错误: {e}")
            return False

    def list_presets(self, search_query: str = "") -> list[str]:
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
