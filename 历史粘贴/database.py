"""
数据库模块 — 管理剪贴板历史的 SQLite 存储
负责：建表、增删查、置顶切换、过期清理
"""

import sqlite3
import os
import threading
from datetime import datetime, timedelta


class ClipboardDatabase:
    """剪贴板历史数据库管理类（线程安全）"""

    def __init__(self):
        # 数据目录：%APPDATA%\ClipHistory
        self.data_dir = os.path.join(os.getenv("APPDATA"), "ClipHistory")
        self.images_dir = os.path.join(self.data_dir, "images")
        self.db_path = os.path.join(self.data_dir, "history.db")

        # 确保目录存在
        os.makedirs(self.images_dir, exist_ok=True)

        # 线程锁，保护数据库写入
        self._lock = threading.Lock()

        # 初始化数据库表
        self._init_db()

    def _get_connection(self):
        """获取数据库连接（每次新建，避免跨线程问题）"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")  # 写前日志，提升并发性能
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self):
        """初始化数据库表结构"""
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        content_type TEXT NOT NULL CHECK(content_type IN ('text', 'image')),
                        text_content TEXT,
                        image_path TEXT,
                        timestamp TEXT NOT NULL,
                        pinned INTEGER DEFAULT 0
                    )
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_timestamp
                    ON history(timestamp DESC)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_pinned
                    ON history(pinned)
                """)
                conn.commit()
            finally:
                conn.close()

    def add_text(self, text: str):
        """
        添加一条文字记录
        返回新记录的 id
        """
        if not text or not text.strip():
            return None

        timestamp = datetime.now().isoformat()

        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute(
                    "INSERT INTO history (content_type, text_content, timestamp) VALUES (?, ?, ?)",
                    ("text", text.strip(), timestamp)
                )
                conn.commit()
                return cursor.lastrowid
            finally:
                conn.close()

    def add_image(self, image) -> int | None:
        """
        添加一条图片记录
        image: PIL Image 对象
        返回新记录的 id，失败返回 None
        """
        if image is None:
            return None

        timestamp = datetime.now()
        timestamp_str = timestamp.isoformat()
        # 文件名：时间戳 + 毫秒，避免重名
        filename = timestamp.strftime("%Y%m%d_%H%M%S_%f") + ".png"
        image_path = os.path.join(self.images_dir, filename)

        try:
            image.save(image_path, "PNG")
        except Exception as e:
            print(f"[数据库] 保存图片失败: {e}")
            return None

        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute(
                    "INSERT INTO history (content_type, image_path, timestamp) VALUES (?, ?, ?)",
                    ("image", image_path, timestamp_str)
                )
                conn.commit()
                return cursor.lastrowid
            finally:
                conn.close()

    def get_records(self, search_query: str = "") -> list[dict]:
        """
        获取所有记录，支持搜索过滤
        返回：列表，置顶优先，时间降序
        """
        conn = self._get_connection()
        try:
            if search_query:
                # 搜索仅匹配文字内容
                sql = """
                    SELECT id, content_type, text_content, image_path, timestamp, pinned
                    FROM history
                    WHERE text_content LIKE ?
                    ORDER BY pinned DESC, timestamp DESC
                """
                rows = conn.execute(sql, (f"%{search_query}%",)).fetchall()
            else:
                sql = """
                    SELECT id, content_type, text_content, image_path, timestamp, pinned
                    FROM history
                    ORDER BY pinned DESC, timestamp DESC
                """
                rows = conn.execute(sql).fetchall()

            return [self._row_to_dict(row) for row in rows]
        finally:
            conn.close()

    def toggle_pin(self, record_id: int) -> bool:
        """
        切换置顶状态，返回新状态
        """
        with self._lock:
            conn = self._get_connection()
            try:
                # 先查当前状态
                row = conn.execute(
                    "SELECT pinned FROM history WHERE id = ?", (record_id,)
                ).fetchone()
                if row is None:
                    return False

                new_pinned = 0 if row[0] else 1
                conn.execute(
                    "UPDATE history SET pinned = ? WHERE id = ?",
                    (new_pinned, record_id)
                )
                conn.commit()
                return bool(new_pinned)
            finally:
                conn.close()

    def delete_record(self, record_id: int) -> bool:
        """
        删除一条记录，如果是图片则同时删除图片文件
        返回是否成功
        """
        with self._lock:
            conn = self._get_connection()
            try:
                # 先查记录
                row = conn.execute(
                    "SELECT content_type, image_path FROM history WHERE id = ?",
                    (record_id,)
                ).fetchone()
                if row is None:
                    return False

                content_type, image_path = row

                # 删除数据库记录
                conn.execute("DELETE FROM history WHERE id = ?", (record_id,))
                conn.commit()

                # 如果是图片，删除图片文件
                if content_type == "image" and image_path and os.path.exists(image_path):
                    try:
                        os.remove(image_path)
                    except OSError:
                        pass

                return True
            finally:
                conn.close()

    def cleanup_expired(self, retention_days: int):
        """
        清理超过保留天数的记录
        置顶记录不会被清理
        retention_days: 保留天数，0 表示不限制
        """
        if retention_days <= 0:
            return  # 不限制

        cutoff = (datetime.now() - timedelta(days=retention_days)).isoformat()

        with self._lock:
            conn = self._get_connection()
            try:
                # 先查出要删除的图片记录，以便删除文件
                rows = conn.execute(
                    "SELECT id, image_path FROM history WHERE timestamp < ? AND pinned = 0 AND content_type = 'image'",
                    (cutoff,)
                ).fetchall()

                # 删除图片文件
                for _, image_path in rows:
                    if image_path and os.path.exists(image_path):
                        try:
                            os.remove(image_path)
                        except OSError:
                            pass

                # 删除数据库记录
                conn.execute(
                    "DELETE FROM history WHERE timestamp < ? AND pinned = 0",
                    (cutoff,)
                )
                conn.commit()
            finally:
                conn.close()

    def get_count(self) -> int:
        """获取记录总数"""
        conn = self._get_connection()
        try:
            return conn.execute("SELECT COUNT(*) FROM history").fetchone()[0]
        finally:
            conn.close()

    def get_last_text(self) -> str | None:
        """获取最近一条文字记录的内容（用于去重）"""
        conn = self._get_connection()
        try:
            row = conn.execute(
                "SELECT text_content FROM history WHERE content_type='text' ORDER BY timestamp DESC LIMIT 1"
            ).fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    @staticmethod
    def _row_to_dict(row) -> dict:
        """将数据库行转换为字典"""
        return {
            "id": row[0],
            "content_type": row[1],
            "text_content": row[2],
            "image_path": row[3],
            "timestamp": row[4],
            "pinned": bool(row[5]),
        }


# 模块级自测
if __name__ == "__main__":
    db = ClipboardDatabase()
    print(f"数据库路径: {db.db_path}")
    print(f"图片目录: {db.images_dir}")

    # 测试添加文字
    rid = db.add_text("Hello, 这是一条测试文字")
    print(f"添加文字记录 id={rid}")

    # 测试查询
    records = db.get_records()
    print(f"当前记录数: {len(records)}")
    for r in records:
        print(f"  [{r['id']}] {r['content_type']} | pinned={r['pinned']} | {r['timestamp']}")

    # 测试搜索
    results = db.get_records("测试")
    print(f"搜索'测试'结果: {len(results)} 条")

    # 测试置顶
    db.toggle_pin(rid)
    r = db.get_records()[0]
    print(f"置顶后第一条: pinned={r['pinned']}")

    # 测试清理
    db.cleanup_expired(30)
    print("清理完成（保留30天）")

    print("\n数据库模块自测通过！")
