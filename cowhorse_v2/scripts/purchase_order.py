import pandas as pd
from datetime import datetime
from sharedlib.db_helper.db_ops import DBHelper, get_now
from sharedlib.rbac_helper.role_permissions_check import RBACGatekeeper

db = DBHelper()
gatekeeper = RBACGatekeeper()

def validate_pr_status(pr_id):
    """Checks if PR exists and status is 'Approved' (ID: 4)."""
    pr_df = db.extract("purchase_request", conditions={"pr_id": pr_id})
    if pr_df.empty:
        return False
    
    # Check if status_id is 4 (Approved)
    return int(pr_df.iloc[0]['status_id']) == 4

def generate_next_po_id():
    """Generates next PO ID in PO_YYYYMM_XXXXX format."""
    po_df = db.extract("purchase_order")
    now = datetime.now()
    prefix = f"PO_{now.strftime('%Y%m')}_"
    
    if po_df.empty:
        return f"{prefix}00001"
    
    # Filter POs from the current month to find the max sequence
    current_month_pos = po_df[po_df['po_id'].str.contains(prefix)]
    if current_month_pos.empty:
        return f"{prefix}00001"
    
    # Extract numeric part, increment, and re-pad
    last_id = current_month_pos['po_id'].sort_values().iloc[-1]
    last_num = int(last_id.split('_')[-1])
    next_num = last_num + 1
    return f"{prefix}{next_num:05d}"

def create_po(pr_id, proc_item, user_id):
    """
    Converts a PR into one or more POs based on the proc_item structure.
    proc_item example: [{"ITM_001": 10, "ITM_002": 5}, {"ITM_003": 2}]
    Returns a list of created po_id strings.
    """
    # 1. Validate PR status
    if not validate_pr_status(pr_id):
        print(f"Validation failed for {pr_id}. PR must be 'Approved'.")
        return False

    # Load item master once to lookup supplier_ids quickly
    item_master = db.extract("item", fields=["item_id", "supplier_id"])

    # 2. Process each PO in the list
    created_pos = []
    for po_items_dict in proc_item:
        new_po_id = generate_next_po_id()
        
        # Get supplier_id from the first item in this PO group
        first_item_id = list(po_items_dict.keys())[0]
        supplier_row = item_master[item_master['item_id'] == first_item_id]
        if supplier_row.empty:
            continue
        supplier_id = supplier_row.iloc[0]['supplier_id']

        # A. Create PO Header
        new_po_header = pd.DataFrame([{
            "po_id": new_po_id,
            "status": 5, # Awaiting Supplier Acceptance
            "supplier_id": supplier_id,
            "created_at": get_now(),
            "created_by": user_id
        }])
        db.load("purchase_order", new_po_header, mode='append')
        created_pos.append(new_po_id)

        # B. Create Bridge Records
        bridge_entries = []
        for item_id, qty in po_items_dict.items():
            bridge_entries.append({
                "doc_id": new_po_id,
                "item_id": item_id,
                "quantity": qty
            })
        
        bridge_df = pd.DataFrame(bridge_entries)
        db.load("purchase_item_bridge", bridge_df, mode='append')

    # 3. Clean up PR items from bridge table
    # We use our delete helper to remove the PR records since they are now POs
    db.delete("purchase_item_bridge", conditions={"doc_id": pr_id})
    
    # Optionally: Update PR status to 'Converted' or similar if you add that status
    print(f"Success: {pr_id} converted into {len(proc_item)} Purchase Orders.")
    return created_pos

def get_po_ticket(user_id):
    """Retrieves PO tickets with enriched status and role names."""
    role = gatekeeper.get_user_role(user_id)
    
    if role == "Supplier":
        po_df = db.extract("purchase_order", conditions={"supplier_id": user_id})
    elif role == "Warehouse Personnel":
        # Warehouse sees Order Accepted (6), Shipped (7), Arrived (8), Received (9)
        po_df = db.extract("purchase_order")
        if not po_df.empty:
            # Ensure status is treated as int for the comparison
            po_df = po_df[po_df['status'].astype(int).isin([6, 7, 8, 9])]
    else:
        return "Error: Access Denied. Unauthorized role."

    if po_df.empty: return []

    # 1. Join with dim_status
    status_df = db.extract("dim_status")
    po_df['status'] = po_df['status'].astype(str)
    status_df['status_id'] = status_df['status_id'].astype(str)
    
    merged_df = po_df.merge(status_df, left_on="status", right_on="status_id", how="left")
    
    # 2. Join with User/Role for creator enrichment
    user_df = db.extract("user", fields=["user_id", "role_id"])
    role_df = db.extract("dim_role", fields=["role_id", "role_name"])
    user_df['role_id'] = user_df['role_id'].astype(str)
    role_df['role_id'] = role_df['role_id'].astype(str)
    user_with_role = user_df.merge(role_df, on='role_id', how='left')

    merged_df = merged_df.merge(user_with_role[['user_id', 'role_name']], left_on='created_by', right_on='user_id', how='left')
    merged_df = merged_df.rename(columns={'role_name': 'creator_role'})

    # After merge: status_x is from po (the ID), status_y is from dim_status (the Name)
    # Wait, in the new schema, dim_status has 'status_name'. So it won't be status_y.
    # If the column name in dim_status is 'status_name', it's directly available.
    if 'user_id' in merged_df.columns: merged_df = merged_df.drop(columns=['user_id'])
    
    result = merged_df[['po_id', 'status', 'status_name', 'created_at', 'creator_role']]
    return result.to_dict(orient='records')

def get_po_details(user_id, po_id):
    """Retrieves full details for a specific PO with enriched status and role names."""
    role = gatekeeper.get_user_role(user_id)
    
    po_header_df = db.extract("purchase_order", conditions={"po_id": po_id})
    if po_header_df.empty: return "Error: Purchase Order not found."

    po_data = po_header_df.iloc[0]
    if role == "Supplier":
        if po_data['supplier_id'] != user_id:
            return "Error: Access Denied. You are not the supplier for this PO."
    elif role == "Warehouse Personnel":
        if int(po_data['status']) not in [6, 7, 8, 9]:
            return "Error: Access Denied. This PO is not in a state accessible to Warehouse."
    else:
        return "Error: Access Denied. Unauthorized role."

    # Enrichment
    status_df = db.extract("dim_status")
    po_header_df['status'] = po_header_df['status'].astype(str)
    status_df['status_id'] = status_df['status_id'].astype(str)
    po_header_df = po_header_df.merge(status_df[['status_id', 'status_name']], left_on='status', right_on='status_id', how='left')

    user_df = db.extract("user", fields=["user_id", "role_id"])
    role_df = db.extract("dim_role", fields=["role_id", "role_name"])
    user_df['role_id'] = user_df['role_id'].astype(str)
    role_df['role_id'] = role_df['role_id'].astype(str)
    user_with_role = user_df.merge(role_df, on='role_id', how='left')

    po_header_df = po_header_df.merge(user_with_role[['user_id', 'role_name']], left_on='created_by', right_on='user_id', how='left')
    po_header_df = po_header_df.rename(columns={'role_name': 'creator_role'})

    bridge_df = db.extract("purchase_item_bridge", conditions={"doc_id": po_id})
    item_master = db.extract("item", fields=["item_id", "item_name", "unit_price"])
    details_df = bridge_df.merge(item_master, on="item_id", how="left")
    
    po_details = po_header_df.iloc[0].to_dict()
    po_details['items'] = details_df[['item_id', 'item_name', 'quantity', 'unit_price']].to_dict(orient='records')
    
    return po_details

def update_po_status(supplier_id, po_id, status_name):
    """
    Updates the status of a PO based on the status name (e.g., 'Order Shipped').
    """
    if not gatekeeper.is_authorized(supplier_id, "update_po_status"):
        return ("Error: Access Denied. You do not have permission to update PO status.")
    
    # 1. Resolve status_name to status_id
    status_df = db.extract("dim_status", conditions={"status_name": status_name})
    if status_df.empty:
        return f"Error: Status '{status_name}' is not valid."
    
    new_status_id = status_df.iloc[0]['status_id']
    
    # 2. Verify PO exists
    po_check = db.extract("purchase_order", conditions={"po_id": po_id})
    if po_check.empty:
        return "Error: Purchase Order not found."
    
    # 3. Update the database
    db.modify("purchase_order", {"status": int(new_status_id)}, {"po_id": po_id})
    return True