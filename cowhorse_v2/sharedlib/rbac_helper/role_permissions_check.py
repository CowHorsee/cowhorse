import yaml
import os
import pandas as pd
from sharedlib.db_helper.db_ops import DBHelper

db = DBHelper()

class RBACGatekeeper:
    def __init__(self, yaml_path=None):
        self.permissions = {}
        if yaml_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            yaml_path = os.path.join(base_dir, "role_permissions.yaml")
            
        # Load the YAML configuration
        if os.path.exists(yaml_path):
            with open(yaml_path, "r") as f:
                config = yaml.safe_load(f)
                self.permissions = config.get("roles", {})

    def get_user_role(self, user_id):
        """
        Input: user_id (UUID)
        Logic: Joins 'user' and 'dim_role' tables on role_id
        Returns: String (Role Name) or None
        """
        # 1. Extract the user record
        user_df = db.extract("user", conditions={"user_id": user_id})
        
        if user_df.empty:
            return None

        # 2. Extract all roles
        roles_df = db.extract("dim_role")
        
        # 3. Join the tables on role_id
        # We ensure role_id is string type on both sides to avoid merge errors (e.g. str vs int64)
        user_df["role_id"] = user_df["role_id"].astype(str)
        roles_df["role_id"] = roles_df["role_id"].astype(str)
        
        merged_df = user_df.merge(roles_df, on="role_id", how="left")
        
        if merged_df.empty or pd.isna(merged_df.iloc[0]['role_name']):
            return None
            
        return merged_df.iloc[0]['role_name']

    def is_authorized(self, user_id, action):
        """
        A high-level check that combines role lookup and permission verification.
        """
        role = self.get_user_role(user_id)
        if not role:
            return False
            
        # Admins have master access
        if role == "Admin":
            return True
            
        allowed_actions = self.permissions.get(role, [])
        return action in allowed_actions