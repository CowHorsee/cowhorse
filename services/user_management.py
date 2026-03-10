import uuid

import bcrypt
import pandas as pd

from core.rbac import RBACGatekeeper
from db.table_storage import DBHelper, get_now
from integrations.email import quick_send


db = DBHelper()
gatekeeper = RBACGatekeeper()


def login(email: str | None, password_plain: str | None):
    user_df = db.extract("user", conditions={"email": email})
    if user_df.empty:
        return None, None, "Error: Email does not exist."

    user_data = user_df.iloc[0]
    stored_hash = str(user_data["password_hash"]).encode("utf-8")
    if password_plain and bcrypt.checkpw(password_plain.encode("utf-8"), stored_hash):
        role_df = db.extract("dim_role", conditions={"role_id": int(user_data["role_id"])})
        role_name = role_df.iloc[0]["role_name"] if not role_df.empty else "Unknown"
        return role_name, user_data["user_id"], "Login Successful"

    return None, None, "Error: Incorrect password."


def register(
    admin_id: str | None,
    email: str | None,
    name: str | None,
    role_name: str | None,
    password: str | None = None,
    user_id: str | None = None,
):
    if not gatekeeper.is_authorized(admin_id, "register"):
        return "Error: Access Denied."

    if not email or not name or not role_name:
        return "Error: Invalid input."

    if not db.extract("user", conditions={"email": email}).empty:
        return "Error: Email already registered."

    role_df = db.extract("dim_role", conditions={"role_name": role_name})
    if role_df.empty:
        return f"Error: Role '{role_name}' not found."
    role_id = int(role_df.iloc[0]["role_id"])

    raw_password = password if password else str(uuid.uuid4())[:8]
    password_hash = bcrypt.hashpw(raw_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    new_user = pd.DataFrame(
        [
            {
                "user_id": user_id if user_id else str(uuid.uuid4()),
                "name": name,
                "email": email,
                "password_hash": password_hash,
                "raw_password": raw_password,
                "role_id": role_id,
                "created_at": get_now(),
            }
        ]
    )
    db.load("user", new_user, mode="append")

    quick_send(
        template_type="ACCOUNT_CREATED",
        recipient_email=email,
        subject="Welcome to Team Cow Horse - Your Account Details",
        name=name,
        email=email,
        role_name=role_name,
        temp_password=raw_password,
    )

    return "Registration Successful"


def forget_password(user_id: str | None):
    user_df = db.extract("user", conditions={"user_id": user_id})
    if user_df.empty:
        return "Error: User not found."

    new_raw_pw = str(uuid.uuid4())[:8]
    new_hash = bcrypt.hashpw(new_raw_pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    db.modify("user", {"password_hash": new_hash}, {"user_id": user_id})

    user_email = user_df.iloc[0]["email"]
    quick_send(
        template_type="FORGET_PASSWORD",
        recipient_email=user_email,
        subject="Password Reset - Team Cow Horse",
        user_id=user_id,
        temp_password=new_raw_pw,
    )

    return "Success: Password has been reset."


def modify_role(admin_id: str | None, user_id: str | None, new_role_name: str | None):
    if not gatekeeper.is_authorized(admin_id, "modify_role"):
        return "Error: Access Denied."

    role_df = db.extract("dim_role", conditions={"role_name": new_role_name})
    if role_df.empty:
        return "Error: New role name is invalid."

    new_role_id = int(role_df.iloc[0]["role_id"])
    if db.extract("user", conditions={"user_id": user_id}).empty:
        return "Error: User not found."

    db.modify("user", {"role_id": new_role_id}, {"user_id": user_id})
    return "Success: User role updated."


def change_password(user_id: str | None, old_password: str | None, new_password: str | None):
    user_df = db.extract("user", conditions={"user_id": user_id})
    if user_df.empty:
        return "Error: User not found."

    user_data = user_df.iloc[0]
    stored_hash = str(user_data["password_hash"]).encode("utf-8")
    if old_password and new_password and bcrypt.checkpw(old_password.encode("utf-8"), stored_hash):
        new_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        db.modify("user", {"password_hash": new_hash}, {"user_id": user_id})
        return "Success: Password has been changed."

    return "Error: Incorrect old password."


def search_user(email: str | None = None, name: str | None = None, role_name: str | None = None):
    df = db.extract("user")
    if df.empty:
        return []

    if email:
        df = df[df["email"] == email]
    if name:
        df = df[df["name"].str.contains(name, case=False, na=False)]
    if role_name:
        roles = db.extract("dim_role")
        df = df.merge(roles, on="role_id")
        df = df[df["role_name"] == role_name]

    return df.to_dict(orient="records")
