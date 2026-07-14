"""Notifications + Audit logs — thin persistence layer."""
import logging
import uuid
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger("notify")


def _now_iso() -> str: return datetime.now(timezone.utc).isoformat()


class NotificationService:
    def __init__(self, db: AsyncIOMotorDatabase, workspace_id: str):
        self.db = db
        self.workspace_id = workspace_id

    async def push(self, *, user_id: str, kind: str, title: str, body: str = "",
                    lead_id: str | None = None) -> dict:
        doc = {
            "id": uuid.uuid4().hex, "workspace_id": self.workspace_id,
            "user_id": user_id, "kind": kind, "title": title, "body": body,
            "lead_id": lead_id, "read": False, "created_at": _now_iso(),
        }
        try: await self.db.notifications.insert_one(dict(doc))
        except Exception: logger.exception("push notification failed")
        return doc

    async def push_all(self, *, user_ids: list[str], **kw) -> None:
        for uid in user_ids: await self.push(user_id=uid, **kw)

    async def list(self, user_id: str, limit: int = 30, unread_only: bool = False) -> list[dict]:
        q = {"workspace_id": self.workspace_id, "user_id": user_id}
        if unread_only: q["read"] = False
        return await self.db.notifications.find(q, {"_id": 0}) \
            .sort("created_at", -1).to_list(limit)

    async def mark_read(self, user_id: str, notif_id: str) -> None:
        await self.db.notifications.update_one(
            {"id": notif_id, "user_id": user_id, "workspace_id": self.workspace_id},
            {"$set": {"read": True}},
        )

    async def mark_all_read(self, user_id: str) -> None:
        await self.db.notifications.update_many(
            {"user_id": user_id, "workspace_id": self.workspace_id, "read": False},
            {"$set": {"read": True}},
        )

    async def unread_count(self, user_id: str) -> int:
        return await self.db.notifications.count_documents(
            {"workspace_id": self.workspace_id, "user_id": user_id, "read": False}
        )


class AuditService:
    def __init__(self, db: AsyncIOMotorDatabase, workspace_id: str, user: dict):
        self.db = db
        self.workspace_id = workspace_id
        self.user = user

    async def log(self, *, action: str, resource_type: str, resource_id: str | None = None,
                   old_value: dict | None = None, new_value: dict | None = None) -> None:
        doc = {
            "id": uuid.uuid4().hex, "workspace_id": self.workspace_id,
            "user_id": self.user["id"], "user_email": self.user["email"],
            "action": action, "resource_type": resource_type, "resource_id": resource_id,
            "old_value": old_value or {}, "new_value": new_value or {},
            "at": _now_iso(),
        }
        try: await self.db.audit_logs.insert_one(dict(doc))
        except Exception: logger.exception("audit log failed")

    async def list(self, limit: int = 200, resource_type: str | None = None,
                    action: str | None = None) -> list[dict]:
        q: dict = {"workspace_id": self.workspace_id}
        if resource_type: q["resource_type"] = resource_type
        if action: q["action"] = action
        return await self.db.audit_logs.find(q, {"_id": 0}) \
            .sort("at", -1).to_list(limit)
