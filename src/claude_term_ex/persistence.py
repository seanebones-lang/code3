"""SQLite-based session persistence for Claude-Terminal-Ex."""

import aiosqlite
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
import logging

from claude_term_ex.config import DB_PATH, MAX_CONTEXT_TOKENS, TOKEN_ESTIMATE_CHARS

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages chat sessions and message persistence."""
    
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.current_session_id: Optional[str] = None
        self._db: Optional[aiosqlite.Connection] = None
    
    async def initialize(self):
        """Initialize database connection and create tables."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self.db_path))
        await self._create_tables()
        logger.info(f"Database initialized at {self.db_path}")
    
    async def close(self):
        """Close database connection."""
        if self._db:
            await self._db.close()
    
    async def _create_tables(self):
        """Create database tables if they don't exist."""
        async with self._db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL
            )
        """):
            pass
        
        async with self._db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                tool_name TEXT,
                tool_result TEXT,
                tokens INTEGER,
                created_at TIMESTAMP NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """):
            pass
        
        async with self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_session ON messages(session_id)
        """):
            pass
        
        async with self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_session_role ON messages(session_id, role)
        """):
            pass
        
        await self._db.commit()
    
    async def create_session(self) -> str:
        """Create a new session and return its ID."""
        session_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        async with self._db.execute(
            "INSERT INTO sessions (id, created_at, updated_at) VALUES (?, ?, ?)",
            (session_id, now, now)
        ):
            pass
        
        await self._db.commit()
        self.current_session_id = session_id
        logger.info(f"Created new session: {session_id}")
        return session_id
    
    async def load_session(self, session_id: str) -> bool:
        """Load an existing session."""
        async with self._db.execute(
            "SELECT id FROM sessions WHERE id = ?",
            (session_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                self.current_session_id = session_id
                logger.info(f"Loaded session: {session_id}")
                return True
        return False
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count from text."""
        return len(text) // TOKEN_ESTIMATE_CHARS
    
    async def add_message(
        self,
        role: str,
        content: str,
        tool_name: Optional[str] = None,
        tool_result: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None
    ):
        """Add a message to the current session."""
        if not self.current_session_id and not session_id:
            await self.create_session()
        
        sid = session_id or self.current_session_id
        tokens = self._estimate_tokens(content)
        now = datetime.utcnow()
        
        tool_result_json = json.dumps(tool_result) if tool_result else None
        
        async with self._db.execute(
            """INSERT INTO messages 
               (session_id, role, content, tool_name, tool_result, tokens, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (sid, role, content, tool_name, tool_result_json, tokens, now)
        ):
            pass
        
        # Update session timestamp
        async with self._db.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (now, sid)
        ):
            pass
        
        await self._db.commit()
    
    async def get_messages(
        self,
        session_id: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve messages for a session, respecting token limits."""
        sid = session_id or self.current_session_id
        if not sid:
            return []
        
        # Get all messages
        async with self._db.execute(
            """SELECT role, content, tool_name, tool_result, tokens, created_at
               FROM messages
               WHERE session_id = ?
               ORDER BY created_at ASC""",
            (sid,)
        ) as cursor:
            rows = await cursor.fetchall()
        
        messages = []
        total_tokens = 0
        
        # Build messages list, tracking token count
        for row in rows:
            role, content, tool_name, tool_result_json, tokens, created_at = row
            total_tokens += tokens or 0
            
            msg = {
                "role": role,
                "content": content,
                "created_at": created_at,
            }
            
            if tool_name:
                msg["tool_name"] = tool_name
            if tool_result_json:
                msg["tool_result"] = json.loads(tool_result_json)
            
            messages.append(msg)
        
        # Truncate if over limit
        if total_tokens > MAX_CONTEXT_TOKENS:
            logger.warning(
                f"Session {sid} exceeds token limit ({total_tokens}/{MAX_CONTEXT_TOKENS}). "
                "Truncating oldest messages."
            )
            
            # Remove oldest messages until under limit
            truncated = []
            current_tokens = 0
            
            for msg in reversed(messages):
                msg_tokens = self._estimate_tokens(msg["content"])
                if current_tokens + msg_tokens > MAX_CONTEXT_TOKENS:
                    break
                truncated.insert(0, msg)
                current_tokens += msg_tokens
            
            messages = truncated
        
        if limit:
            messages = messages[-limit:]
        
        return messages
    
    async def get_session_token_count(self, session_id: Optional[str] = None) -> int:
        """Get total token count for a session."""
        sid = session_id or self.current_session_id
        if not sid:
            return 0
        
        async with self._db.execute(
            "SELECT SUM(tokens) FROM messages WHERE session_id = ?",
            (sid,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] or 0 if row else 0
    
    async def list_sessions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """List recent sessions."""
        async with self._db.execute(
            """SELECT id, created_at, updated_at,
                      (SELECT COUNT(*) FROM messages WHERE session_id = sessions.id) as message_count
               FROM sessions
               ORDER BY updated_at DESC
               LIMIT ?""",
            (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
        
        return [
            {
                "id": row[0],
                "created_at": row[1],
                "updated_at": row[2],
                "message_count": row[3],
            }
            for row in rows
        ]
