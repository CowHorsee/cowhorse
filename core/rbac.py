from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import yaml

from services.sharedlib.db_helper.table_storage import DBHelper


class RBACGatekeeper:
    def __init__(self, yaml_path: str | None = None, db: DBHelper | None = None):
        self._db = db or DBHelper()
        self.permissions: dict[str, list[str]] = {}

        if yaml_path is None:
            base_dir = Path(__file__).resolve().parent
            yaml_path = str(base_dir / "role_permissions.yaml")

        if os.path.exists(yaml_path):
            with open(yaml_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            self.permissions = config.get("roles", {})

    def get_user_role(self, user_id: str | None) -> str | None:
        if not user_id:
            return None

        user_df = self._db.extract("user", conditions={"user_id": user_id})
        if user_df.empty:
            return None

        roles_df = self._db.extract("dim_role")
        if roles_df.empty:
            return None

        user_df["role_id"] = user_df["role_id"].astype(str)
        roles_df["role_id"] = roles_df["role_id"].astype(str)
        merged_df = user_df.merge(roles_df, on="role_id", how="left")

        if merged_df.empty or pd.isna(merged_df.iloc[0].get("role_name")):
            return None

        return str(merged_df.iloc[0]["role_name"])

    def is_authorized(self, user_id: str | None, action: str) -> bool:
        role = self.get_user_role(user_id)
        if not role:
            return False
        if role == "Admin":
            return True
        allowed_actions = self.permissions.get(role, [])
        return action in allowed_actions
