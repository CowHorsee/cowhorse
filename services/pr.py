from datetime import datetime

import pandas as pd

from services.sharedlib.rbac_helper.rbac_helper import RBACGatekeeper
from services.sharedlib.db_helper.db_helper import DBHelper, get_now, format_timestamps_to_gmt8
from services.sharedlib.email_helper import quick_send
from services.sharedlib.exceptions import (
    BadRequestException,
    ForbiddenException,
    NotFoundException,
)


db = DBHelper()
gatekeeper = RBACGatekeeper()

THRESHOLD_PERCENTAGE = 0.8


def generate_next_pr_id() -> str:
    pr_df = db.extract("purchase_request")
    now = datetime.now()
    prefix = f"PR_{now.strftime('%Y%m')}_"

    if pr_df.empty:
        return f"{prefix}00001"

    current_month_prs = pr_df[pr_df["pr_id"].str.startswith(prefix)]
    if current_month_prs.empty:
        return f"{prefix}00001"

    last_id = current_month_prs["pr_id"].max()
    last_num = int(str(last_id)[-5:])
    return f"{prefix}{(last_num + 1):05d}"


def procurement_alert(item_name: str | None, predicted_demand, justification: str | None):
    # Early validation: Check if item exists in item master
    item_master = db.extract("item", fields=["item_name"])
    if not item_name or item_master[item_master["item_name"].str.lower() == item_name.lower()].empty:
        raise BadRequestException(f"Error: Item '{item_name}' not found in the item list.")

    from services.warehouse import count_inventory

    current_stock = 0
    inventory_items = count_inventory(item_name)
    if inventory_items:
        for item in inventory_items:
            if item["item_name"].lower() == item_name.lower() or item["item_id"].lower() == item_name.lower():
                current_stock = item["quantity"]
                break

    if item_name and (float(predicted_demand) * THRESHOLD_PERCENTAGE) > current_stock:
        proc_item = [{item_name: int(float(predicted_demand) - current_stock)}]
        result = create_pr(user_id=None, proc_item=proc_item, justification=justification)

        if isinstance(result, dict) and "pr_id" in result:
            roles = db.extract("dim_role", conditions={"role_name": "Procurement Officer"})
            if not roles.empty:
                officer_role_id = roles.iloc[0]["role_id"]
                officers = db.extract("user", conditions={"role_id": int(officer_role_id)})
                officer_emails = officers["email"].tolist() if not officers.empty else []
                if officer_emails:
                    quick_send(
                        template_type="PROCUREMENT_ALERT",
                        recipient_email=officer_emails,
                        subject=f"AI Alert: Predicted Shortage for {item_name}",
                        item_name=item_name,
                        predicted_demand=predicted_demand,
                        current_stock=current_stock,
                        justification=justification,
                    )
        return result

    return "Stock level sufficient. No PR triggered."


def create_pr(user_id: str | None, proc_item: list[dict], justification: str | None):
    item_master = db.extract("item", fields=["item_id", "item_name"])
    
    aggregated_items = {}
    for item_dict in proc_item:
        for name, qty in item_dict.items():
            aggregated_items[name] = aggregated_items.get(name, 0) + qty

    invalid_items = []
    for name in aggregated_items.keys():
        if item_master[item_master["item_name"] == name].empty:
            invalid_items.append(name)
    if invalid_items:
        raise BadRequestException(f"Error: Invalid items found: {', '.join(invalid_items)}")

    new_pr_id = generate_next_pr_id()
    status_id = 2 if user_id else 1
    now_ts = get_now()

    new_pr_header = pd.DataFrame(
        [
            {
                "pr_id": new_pr_id,
                "status_id": status_id,
                "created_at": now_ts,
                "created_by": user_id,
                "last_modified_at": now_ts,
                "last_modified_by": user_id,
                "reviewed_at": None,
                "reviewed_by": None,
                "justification": justification,
            }
        ]
    )
    db.load("purchase_request", new_pr_header, mode="append")

    bridge_data = []
    for name, qty in aggregated_items.items():
        match = item_master[item_master["item_name"] == name]
        if not match.empty:
            bridge_data.append(
                {"doc_id": new_pr_id, "item_id": match.iloc[0]["item_id"], "quantity": qty}
            )

    if bridge_data:
        db.load("purchase_item_bridge", pd.DataFrame(bridge_data), mode="append")

    return {"pr_id": new_pr_id, "status": status_id, "items": bridge_data}


def accept_pr_suggestion(pr_id: str | None, officer_id: str | None) -> str:
    pr = db.extract("purchase_request", conditions={"pr_id": pr_id})
    if pr.empty:
        raise NotFoundException("Error: PR does not exist.")
    if int(pr.iloc[0]["status_id"]) != 1:
        raise BadRequestException("Error: Only AI suggestions can be accepted.")

    now_ts = get_now()
    updates = {
        "status_id": 2,
        "created_at": now_ts,
        "created_by": officer_id,
        "last_modified_at": now_ts,
        "last_modified_by": officer_id,
    }
    db.modify("purchase_request", updates, {"pr_id": pr_id})
    return f"PR {pr_id} successfully accepted by Officer."


def modify_pr(user_id: str | None, pr_id: str | None, proc_item: list[dict], justification: str | None) -> str:
    pr = db.extract("purchase_request", conditions={"pr_id": pr_id})
    if pr.empty:
        raise NotFoundException("Error: PR not found.")

    role = gatekeeper.get_user_role(user_id)
    current_status = int(pr.iloc[0]["status_id"])

    if role == "Procurement Officer" and current_status != 1:
        raise ForbiddenException("Error: Officers can only modify AI suggestions (Status 1).")
    if role == "Procurement Manager" and current_status != 2:
        raise ForbiddenException("Error: Managers can only modify submitted requests (Status 2).")

    full_df = db.extract("purchase_request")
    if not full_df.empty:
        for col in ["justification", "reviewed_at", "reviewed_by", "created_by", "last_modified_by"]:
            if col in full_df.columns:
                full_df[col] = full_df[col].astype(object)

        mask = full_df["pr_id"] == pr_id
        full_df.loc[mask, "justification"] = justification
        full_df.loc[mask, "last_modified_at"] = get_now()
        full_df.loc[mask, "last_modified_by"] = user_id
        if role == "Procurement Officer":
            full_df.loc[mask, "status_id"] = 2

        db.load("purchase_request", full_df, mode="overwrite")

    db.delete("purchase_item_bridge", {"doc_id": pr_id})
    item_master = db.extract("item", fields=["item_id", "item_name"])
    
    aggregated_items = {}
    for item_dict in proc_item:
        for name, qty in item_dict.items():
            aggregated_items[name] = aggregated_items.get(name, 0) + qty
            
    new_bridge = []
    for name, qty in aggregated_items.items():
        match = item_master[item_master["item_name"] == name]
        if not match.empty:
            new_bridge.append(
                {"doc_id": pr_id, "item_id": match.iloc[0]["item_id"], "quantity": qty}
            )
    if new_bridge:
        db.load("purchase_item_bridge", pd.DataFrame(new_bridge), mode="append")
    return f"PR {pr_id} updated successfully."


def _enrich_pr_records(pr_df: pd.DataFrame) -> list[dict]:
    if pr_df.empty:
        return []

    status_df = db.extract("dim_status")
    pr_df["status_id"] = pr_df["status_id"].astype(str)
    status_df["status_id"] = status_df["status_id"].astype(str)
    pr_df = pr_df.merge(status_df[["status_id", "status_name"]], on="status_id", how="left")

    user_df = db.extract("user", fields=["user_id", "role_id"])
    role_df = db.extract("dim_role", fields=["role_id", "role_name"])
    user_df["role_id"] = user_df["role_id"].astype(str)
    role_df["role_id"] = role_df["role_id"].astype(str)
    user_with_role = user_df.merge(role_df, on="role_id", how="left")
    pr_df = pr_df.merge(
        user_with_role[["user_id", "role_name"]],
        left_on="created_by",
        right_on="user_id",
        how="left",
    )
    pr_df = pr_df.rename(columns={"role_name": "creator_role"})
    if "user_id" in pr_df.columns:
        pr_df = pr_df.drop(columns=["user_id"])

    pr_df = format_timestamps_to_gmt8(pr_df, ["created_at", "last_modified_at", "reviewed_at"])
    return pr_df.to_dict(orient="records")


def get_pr_ticket(user_id: str | None, pr_id: str | None = None, status: str | None = None):
    role = gatekeeper.get_user_role(user_id)
    conditions: dict = {}
    if role == "Procurement Officer":
        conditions["created_by"] = user_id
    if pr_id:
        conditions["pr_id"] = pr_id
    if status:
        if status.isdigit():
            conditions["status_id"] = int(status)
        else:
            status_df = db.extract("dim_status")
            status_match = status_df[status_df["status_name"].str.lower() == status.lower()]
            if not status_match.empty:
                conditions["status_id"] = int(status_match.iloc[0]["status_id"])
            else:
                return []

    pr_df = db.extract("purchase_request", conditions=conditions)
    return _enrich_pr_records(pr_df)


def get_pr_list_by_user_id(user_id: str):
    pr_df = db.extract("purchase_request", conditions={"created_by": user_id})
    return _enrich_pr_records(pr_df)


def get_pr_details(user_id: str | None, pr_id: str | None):
    role = gatekeeper.get_user_role(user_id)
    conditions: dict = {"pr_id": pr_id}
    if role == "Procurement Officer":
        conditions["created_by"] = user_id

    header_df = db.extract("purchase_request", conditions=conditions)
    if header_df.empty:
        raise NotFoundException("Error: PR not found or unauthorized access.")

    status_df = db.extract("dim_status")
    header_df["status_id"] = header_df["status_id"].astype(str)
    status_df["status_id"] = status_df["status_id"].astype(str)
    header_df = header_df.merge(status_df[["status_id", "status_name"]], on="status_id", how="left")

    user_df = db.extract("user", fields=["user_id", "role_id"])
    role_df = db.extract("dim_role", fields=["role_id", "role_name"])
    user_df["role_id"] = user_df["role_id"].astype(str)
    role_df["role_id"] = role_df["role_id"].astype(str)
    user_with_role = user_df.merge(role_df, on="role_id", how="left")
    header_df = header_df.merge(
        user_with_role[["user_id", "role_name"]],
        left_on="created_by",
        right_on="user_id",
        how="left",
    )
    header_df = header_df.rename(columns={"role_name": "creator_role"})
    header_df = format_timestamps_to_gmt8(header_df, ["created_at", "last_modified_at", "reviewed_at"])

    items = db.extract("purchase_item_bridge", conditions={"doc_id": pr_id})
    return {"header": header_df.iloc[0].to_dict(), "items": items.to_dict(orient="records")}


def review_pr(pr_id: str | None, decision: str | None, manager_id: str | None):
    if not gatekeeper.is_authorized(manager_id, "review_pr"):
        raise ForbiddenException("Error: Access Denied.")

    pr = db.extract("purchase_request", conditions={"pr_id": pr_id})
    if pr.empty:
        raise NotFoundException("Error: PR not found.")
    if int(pr.iloc[0]["status_id"]) != 2:
        raise BadRequestException("Error: PR is not in a 'Pending Review' state.")

    decision_lower = (decision or "").lower()
    if decision_lower in ("approve", "approved", "accept", "accepted"):
        status_code = 4
    else:
        status_code = 3
    updates = {"status_id": status_code, "reviewed_at": get_now(), "reviewed_by": manager_id}

    full_df = db.extract("purchase_request")
    if not full_df.empty:
        for col in ["reviewed_at", "reviewed_by", "justification", "created_by", "last_modified_by"]:
            if col in full_df.columns:
                full_df[col] = full_df[col].astype(object)

        mask = full_df["pr_id"] == pr_id
        for col, val in updates.items():
            full_df.loc[mask, col] = val
        if "last_modified_at" in full_df.columns:
            full_df.loc[mask, "last_modified_at"] = get_now()
        if "last_modified_by" in full_df.columns:
            full_df.loc[mask, "last_modified_by"] = manager_id
        db.load("purchase_request", full_df, mode="overwrite")

    return f"PR {pr_id} has been {decision}ed."



