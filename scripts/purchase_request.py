import pandas as pd
from datetime import datetime
from sharedlib.rbac_helper.role_permissions_check import RBACGatekeeper
from sharedlib.db_helper.db_ops import DBHelper, get_now
from sharedlib.email_helper.email import quick_send

db = DBHelper()
gatekeeper = RBACGatekeeper()

# --- Constants ---
THRESHOLD_PERCENTAGE = 0.8  # 80%

def generate_next_pr_id():
    """Generates next PR ID in PR_YYYYMM_XXXXX format."""
    pr_df = db.extract("purchase_request")
    now = datetime.now()
    prefix = f"PR_{now.strftime('%Y%m')}_"
    
    if pr_df.empty:
        return f"{prefix}00001"
    
    # Filter by current month prefix to reset counter monthly
    current_month_prs = pr_df[pr_df['pr_id'].str.startswith(prefix)]
    if current_month_prs.empty:
        return f"{prefix}00001"
    
    # Get max ID, slice last 5, and increment
    last_id = current_month_prs['pr_id'].max()
    last_num = int(last_id[-5:])
    return f"{prefix}{ (last_num + 1):05d}"

# --- Core Functions ---

def procurement_alert(item_name, predicted_demand, justification):
    """AI Trigger: Automatically creates a PR if stock is below threshold."""
    # 1. Get current stock
    from scripts.uat_warehouse_management import count_inventory
    current_stock = count_inventory(item_name)
    
    # 2. Check threshold
    if (predicted_demand * THRESHOLD_PERCENTAGE) > current_stock:
        proc_item = {item_name: int(predicted_demand - current_stock)}
        result = create_pr(user_id=None, proc_item=proc_item, justification=justification)
        
        # Integration 3: Send AI Procurement Alert to all Officers
        if isinstance(result, dict) and "pr_id" in result:
            db = DBHelper()
            # Get All Officers
            roles = db.extract("dim_role", conditions={"role_name": "Procurement Officer"})
            if not roles.empty:
                officer_role_id = roles.iloc[0]['role_id']
                officers = db.extract("user", conditions={"role_id": int(officer_role_id)})
                officer_emails = officers['email'].tolist() if not officers.empty else []
                
                if officer_emails:
                    quick_send(
                        template_type="PROCUREMENT_ALERT",
                        recipient_email=officer_emails[0],
                        subject=f"AI Alert: Predicted Shortage for {item_name}",
                        cc_emails=officer_emails[1:],
                        item_name=item_name,
                        predicted_demand=predicted_demand,
                        current_stock=current_stock,
                        justification=justification
                    )
        return result
    
    return "Stock level sufficient. No PR triggered."

def create_pr(user_id, proc_item, justification):
    """Creates a PR header and bridge entries. Status 1 for AI, 2 for Officer."""
    # A. Validate Items
    item_master = db.extract("item", fields=["item_id", "item_name"])
    invalid_items = []
    for name in proc_item.keys():
        if item_master[item_master['item_name'] == name].empty:
            invalid_items.append(name)
    
    if invalid_items:
        return f"Error: Invalid items found: {', '.join(invalid_items)}"

    # B. Create PR Header
    new_pr_id = generate_next_pr_id()
    status_id = 2 if user_id else 1
    now_ts = get_now()

    new_pr_header = pd.DataFrame([{
        "pr_id": new_pr_id,
        "status_id": status_id,
        "created_at": now_ts,
        "created_by": user_id,
        "last_modified_at": now_ts,
        "last_modified_by": user_id,
        "reviewed_at": None,
        "reviewed_by": None,
        "justification": justification
    }])
    db.load("purchase_request", new_pr_header, mode='append')

    # C. Create Bridge Entries
    bridge_data = []
    
    for name, qty in proc_item.items():
        # Lookup item_id from name
        match = item_master[item_master['item_name'] == name]
        if not match.empty:
            bridge_data.append({
                "doc_id": new_pr_id,
                "item_id": match.iloc[0]['item_id'],
                "quantity": qty
            })
    
    if bridge_data:
        db.load("purchase_item_bridge", pd.DataFrame(bridge_data), mode='append')

    return {"pr_id": new_pr_id, "status": status_id, "items": bridge_data}

def accept_pr_suggestion(pr_id, officer_id):
    """Officer accepts an AI suggestion (Status 1 -> 2)."""
    pr = db.extract("purchase_request", conditions={"pr_id": pr_id})
    
    if pr.empty: return "Error: PR does not exist."
    if int(pr.iloc[0]['status_id']) != 1: return "Error: Only AI suggestions can be accepted."

    now_ts = get_now()
    updates = {
        "status_id": 2,
        "created_at": now_ts,
        "created_by": officer_id,
        "last_modified_at": now_ts,
        "last_modified_by": officer_id
    }
    db.modify("purchase_request", updates, {"pr_id": pr_id})
    return f"PR {pr_id} successfully accepted by Officer."

def modify_pr(user_id, pr_id, proc_item, justification):
    """Allows Officers to modify AI suggestions, or Managers to modify Officer requests."""
    pr = db.extract("purchase_request", conditions={"pr_id": pr_id})
    if pr.empty: return "Error: PR not found."
    
    role = gatekeeper.get_user_role(user_id)
    current_status = int(pr.iloc[0]['status_id'])
    
    # Validation Logic
    if role == "Procurement Officer" and current_status != 1:
        return "Error: Officers can only modify AI suggestions (Status 1)."
    if role == "Procurement Manager" and current_status != 2:
        return "Error: Managers can only modify submitted requests (Status 2)."

    # 1. Update Header
    updates = {
        "justification": justification,
        "last_modified_at": get_now(),
        "last_modified_by": user_id
    }
    if role == "Procurement Officer": updates["status_id"] = 2
    
    # Manually apply update to ensure dtype consistency and bypass LossySetitemError
    full_df = db.extract("purchase_request")
    if not full_df.empty:
        # Cast critical columns to object BEFORE any assignment to prevent LossySetitemError (float64 -> object)
        for col in ["justification", "reviewed_at", "reviewed_by", "created_by", "last_modified_by"]:
            if col in full_df.columns:
                full_df[col] = full_df[col].astype(object)
        
        mask = full_df['pr_id'] == pr_id
        for col, val in updates.items():
            full_df.loc[mask, col] = val
            
        full_df.loc[mask, 'last_modified_at'] = get_now()
        full_df.loc[mask, 'last_modified_by'] = user_id

        db.load("purchase_request", full_df, mode='overwrite')

    # 2. Update Items (Delete old bridge records and insert new ones)
    db.delete("purchase_item_bridge", {"doc_id": pr_id})
    
    item_master = db.extract("item", fields=["item_id", "item_name"])
    new_bridge = []
    for name, qty in proc_item.items():
        match = item_master[item_master['item_name'] == name]
        if not match.empty:
            new_bridge.append({"doc_id": pr_id, "item_id": match.iloc[0]['item_id'], "quantity": qty})
    
    if new_bridge:
        db.load("purchase_item_bridge", pd.DataFrame(new_bridge), mode='append')
    return f"PR {pr_id} updated successfully."

def get_pr_ticket(user_id, pr_id=None, status=None):
    """Retrieves PR tickets with enriched status and role names."""
    role = gatekeeper.get_user_role(user_id)
    
    conditions = {}
    if role == "Procurement Officer":
        conditions["created_by"] = user_id
    
    if pr_id: conditions["pr_id"] = pr_id
    if status: conditions["status_id"] = int(status) if status else None
    
    pr_df = db.extract("purchase_request", conditions=conditions)
    if pr_df.empty: return []

    # 1. Join with dim_status
    status_df = db.extract("dim_status")
    pr_df['status_id'] = pr_df['status_id'].astype(str)
    status_df['status_id'] = status_df['status_id'].astype(str)
    pr_df = pr_df.merge(status_df[['status_id', 'status_name']], on='status_id', how='left')

    # 2. Join with User and Role to get creator's role name
    user_df = db.extract("user", fields=["user_id", "role_id"])
    role_df = db.extract("dim_role", fields=["role_id", "role_name"])
    
    user_df['role_id'] = user_df['role_id'].astype(str)
    role_df['role_id'] = role_df['role_id'].astype(str)
    user_with_role = user_df.merge(role_df, on='role_id', how='left')

    pr_df = pr_df.merge(user_with_role[['user_id', 'role_name']], left_on='created_by', right_on='user_id', how='left')
    pr_df = pr_df.rename(columns={'role_name': 'creator_role'})
    
    # Drop redundant user_id from merge
    if 'user_id' in pr_df.columns: pr_df = pr_df.drop(columns=['user_id'])

    return pr_df.to_dict(orient='records')

def get_pr_details(user_id, pr_id):
    """Retrieves full PR details with enriched status and role names."""
    role = gatekeeper.get_user_role(user_id)
    
    conditions = {"pr_id": pr_id}
    if role == "Procurement Officer":
        conditions["created_by"] = user_id
        
    header_df = db.extract("purchase_request", conditions=conditions)
    if header_df.empty: return "Error: PR not found or unauthorized access."

    # Enrichment
    status_df = db.extract("dim_status")
    header_df['status_id'] = header_df['status_id'].astype(str)
    status_df['status_id'] = status_df['status_id'].astype(str)
    header_df = header_df.merge(status_df[['status_id', 'status_name']], on='status_id', how='left')

    user_df = db.extract("user", fields=["user_id", "role_id"])
    role_df = db.extract("dim_role", fields=["role_id", "role_name"])
    user_df['role_id'] = user_df['role_id'].astype(str)
    role_df['role_id'] = role_df['role_id'].astype(str)
    user_with_role = user_df.merge(role_df, on='role_id', how='left')

    header_df = header_df.merge(user_with_role[['user_id', 'role_name']], left_on='created_by', right_on='user_id', how='left')
    header_df = header_df.rename(columns={'role_name': 'creator_role'})

    items = db.extract("purchase_item_bridge", conditions={"doc_id": pr_id})
    return {"header": header_df.iloc[0].to_dict(), "items": items.to_dict(orient='records')}

def review_pr(pr_id, decision, manager_id):
    """Manager approves (4) or rejects (3) a PR."""
    if not gatekeeper.is_authorized(manager_id, "review_pr"):
        return "Error: Access Denied."

    pr = db.extract("purchase_request", conditions={"pr_id": pr_id})
    if pr.empty: return "Error: PR not found."
    if int(pr.iloc[0]['status_id']) != 2: return "Error: PR is not in a 'Pending Review' state."

    status_code = 4 if decision.lower() == "approve" else 3
    updates = {
        "status_id": status_code,
        "reviewed_at": get_now(),
        "reviewed_by": manager_id
    }
    
    # Manually apply update to ensure dtype consistency and bypass LossySetitemError
    full_df = db.extract("purchase_request")
    if not full_df.empty:
        # Cast critical columns to object BEFORE any assignment to prevent LossySetitemError (float64 -> object)
        for col in ["reviewed_at", "reviewed_by", "justification", "created_by", "last_modified_by"]:
            if col in full_df.columns:
                full_df[col] = full_df[col].astype(object)
        
        mask = full_df['pr_id'] == pr_id
        for col, val in updates.items():
            full_df.loc[mask, col] = val
            
        if 'last_modified_at' in full_df.columns:
            full_df.loc[mask, 'last_modified_at'] = get_now()
        if 'last_modified_by' in full_df.columns:
            full_df.loc[mask, 'last_modified_by'] = manager_id

        db.load("purchase_request", full_df, mode='overwrite')
        
    return f"PR {pr_id} has been {decision}ed."