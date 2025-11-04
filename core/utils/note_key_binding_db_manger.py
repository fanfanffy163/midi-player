import sqlite3
import json
from typing import Dict, List, Optional

# --- 数据库管理器 ---

class NoteKeyBindingDBManager:
    """处理所有SQLite数据库操作"""
    def __init__(self, db_name="keybindings.db"):
        self.db_name = db_name
        self.conn = sqlite3.connect(self.db_name)
        self.create_table()

    def create_table(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS presets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    mappings TEXT NOT NULL
                );
            """)

    def save_preset(self, name: str, mappings: Dict[str, str]) -> bool:
        """保存或更新一个预设。"""
        mappings_json = json.dumps(mappings)
        try:
            with self.conn:
                self.conn.execute(
                    "INSERT OR REPLACE INTO presets (name, mappings) VALUES (?, ?)",
                    (name, mappings_json)
                )
            return True
        except sqlite3.Error as e:
            print(f"数据库保存错误: {e}")
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
            print(f"数据库删除错误: {e}")
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

    def __del__(self):
        self.conn.close()