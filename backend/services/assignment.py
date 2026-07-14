"""Lead assignment engine — rule-based with round-robin fallback."""
import logging
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger("assignment")


class AssignmentEngine:
    def __init__(self, db: AsyncIOMotorDatabase, workspace_id: str):
        self.db = db
        self.workspace_id = workspace_id

    async def _members(self) -> list[dict]:
        return await self.db.users.find(
            {"workspace_id": self.workspace_id, "role": {"$in": ["admin", "sales_manager", "sdr"]}},
            {"_id": 0, "password_hash": 0},
        ).to_list(200)

    async def assign(self, lead: dict) -> tuple[str | None, str]:
        """Returns (user_id, reason). None if no assignable member."""
        rules = await self.db.assignment_rules.find(
            {"workspace_id": self.workspace_id, "active": True}, {"_id": 0}
        ).sort("priority", 1).to_list(200)

        qual = lead.get("qualification") or {}
        score = qual.get("score")
        industry = (qual.get("industry") or "").lower()
        region = (lead.get("region") or "").lower()

        for r in rules:
            if r.get("region_match") and region != r["region_match"].lower(): continue
            if r.get("industry_match") and industry != r["industry_match"].lower(): continue
            if r.get("min_score") is not None and (score is None or score < r["min_score"]): continue
            if r.get("max_score") is not None and (score is None or score > r["max_score"]): continue

            target = r.get("assign_to_user_id")
            if target:
                user = await self.db.users.find_one({"id": target, "workspace_id": self.workspace_id}, {"_id": 0})
                if user:
                    parts = []
                    if r.get("region_match"): parts.append(f"region={r['region_match']}")
                    if r.get("industry_match"): parts.append(f"industry={r['industry_match']}")
                    if r.get("min_score") is not None: parts.append(f"score≥{r['min_score']}")
                    reason = f"Rule (priority {r['priority']}) matched: {', '.join(parts) or 'catch-all'} → {user['full_name']}"
                    return user["id"], reason
            # If rule matched but no user, fall through to round-robin

        # Round-robin
        members = await self._members()
        if not members: return None, "No assignable team members"
        cur = await self.db.workspaces.find_one({"id": self.workspace_id}, {"_id": 0})
        rr_index = (cur or {}).get("rr_index", 0)
        pick = members[rr_index % len(members)]
        await self.db.workspaces.update_one(
            {"id": self.workspace_id}, {"$set": {"rr_index": (rr_index + 1) % len(members)}}
        )
        return pick["id"], f"Round-robin → {pick['full_name']}"
