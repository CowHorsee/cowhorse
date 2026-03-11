import uuid
import bcrypt
import pandas as pd
from sharedlib.db_helper.db_ops import DBHelper, get_now
from sharedlib.rbac_helper.role_permissions_check import RBACGatekeeper
from sharedlib.email_helper.email import quick_send

db = DBHelper()
gatekeeper = RBACGatekeeper()

# --- Core Functions ---

def login(email, password_plain):
    """Checks credentials and returns role, user_id, and result message."""
    user_df = db.extract("user", conditions={"email": email})
    
    if user_df.empty:
        return None, None, "Error: Email does not exist."
    
    user_data = user_df.iloc[0]
    stored_hash = str(user_data['password_hash']).encode('utf-8')
    
    if bcrypt.checkpw(password_plain.encode('utf-8'), stored_hash):
        # Pass role_id as int to conditions to match inferred dtype in db_ops.py
        role_df = db.extract("dim_role", conditions={"role_id": int(user_data['role_id'])})
        role_name = role_df.iloc[0]['role_name'] if not role_df.empty else "Unknown"
        return role_name, user_data['user_id'], "Login Successful"
    else:
        return None, None, "Error: Incorrect password."

def register(admin_id, email, name, role_name, password=None, user_id=None):
    """Registers a new user and looks up role_id from dim_role.csv."""

    if not gatekeeper.is_authorized(admin_id, "register"):
        return "Error: Access Denied."

    # 1. Check duplicate
    if not db.extract("user", conditions={"email": email}).empty:
        return "Error: Email already registered."
    
    # 2. Look up role_id
    role_df = db.extract("dim_role", conditions={"role_name": role_name})
    if role_df.empty:
        return f"Error: Role '{role_name}' not found."
    role_id = int(role_df.iloc[0]['role_id'])
    
    # 3. Security
    raw_password = password if password else str(uuid.uuid4())[:8]
    password_hash = bcrypt.hashpw(raw_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    # 4. Save
    new_user = pd.DataFrame([{
        "user_id": user_id if user_id else str(uuid.uuid4()),
        "name": name,
        "email": email,
        "password_hash": password_hash,
        "raw_password": raw_password,
        "role_id": role_id,
        "created_at": get_now()
    }])
    
    db.load("user", new_user, mode='append')
    print(f"DEBUG: Temporary Password for {email} is: {raw_password}")

    # Send Welcome Email
    quick_send(
        template_type="ACCOUNT_CREATED",
        recipient_email=email,
        subject="Welcome to Team Cow Horse - Your Account Details",
        name=name,
        email=email,
        role_name=role_name,
        temp_password=raw_password
    )

    return "Registration Successful"

def forget_password(user_id):
    """Resets password for a user_id and prints the new one."""
    user_df = db.extract("user", conditions={"user_id": user_id})
    if user_df.empty:
        return "Error: User not found."
    
    new_raw_pw = str(uuid.uuid4())[:8]
    new_hash = bcrypt.hashpw(new_raw_pw.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    db.modify("user", {"password_hash": new_hash}, {"user_id": user_id})
    print(f"CONSOLE: User {user_id} password reset to: {new_raw_pw}")

    # Send Reset Email (to the user whose password was reset)
    user_email = user_df.iloc[0]['email']
    quick_send(
        template_type="FORGET_PASSWORD",
        recipient_email=user_email,
        subject="Password Reset - Team Cow Horse",
        user_id=user_id,
        temp_password=new_raw_pw
    )

    return "Success: Password has been reset."

def modify_role(admin_id, user_id, new_role_name):
    """Updates the user role by looking up the ID for the new role name."""

    if not gatekeeper.is_authorized(admin_id, "modify_role"):
        return "Error: Access Denied."

    role_df = db.extract("dim_role", conditions={"role_name": new_role_name})
    if role_df.empty:
        return "Error: New role name is invalid."
    
    new_role_id = int(role_df.iloc[0]['role_id'])
    
    if db.extract("user", conditions={"user_id": user_id}).empty:
        return "Error: User not found."
    
    db.modify("user", {"role_id": new_role_id}, {"user_id": user_id})
    return "Success: User role updated."

def change_password(user_id, old_password, new_password):
    """Verifies old password and updates to new password."""
    user_df = db.extract("user", conditions={"user_id": user_id})
    if user_df.empty:
        return "Error: User not found."
    
    user_data = user_df.iloc[0]
    stored_hash = str(user_data['password_hash']).encode('utf-8')
    
    if bcrypt.checkpw(old_password.encode('utf-8'), stored_hash):
        new_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        db.modify("user", {"password_hash": new_hash}, {"user_id": user_id})
        return "Success: Password has been changed."
    else:
        return "Error: Incorrect old password."

def search_user(email=None, name=None, role_name=None):
    """Searches user database with optional filters."""
    df = db.extract("user")
    if df.empty: return []

    if email:
        df = df[df['email'] == email]
    if name:
        df = df[df['name'].str.contains(name, case=False, na=False)]
    if role_name:
        roles = db.extract("dim_role")
        df = df.merge(roles, on="role_id")
        df = df[df['role_name'] == role_name]
    
    return df.to_dict(orient='records')