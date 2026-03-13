from datetime import datetime

import pandas as pd

from services.sharedlib.rbac_helper.rbac_helper import RBACGatekeeper
from services.sharedlib.db_helper.db_helper import DBHelper, get_now
from services.sharedlib.exceptions import (
    BadRequestException,
    ForbiddenException,
    NotFoundException,
)


db = DBHelper()
gatekeeper = RBACGatekeeper()


def validate_pr_status(pr_id: str | None) -> bool:
    pr_df = db.extract("purchase_request", conditions={"pr_id": pr_id})
    if pr_df.empty:
        return False
    return int(pr_df.iloc[0]["status_id"]) == 4


def generate_next_po_id() -> str:
    po_df = db.extract("purchase_order")
    now = datetime.now()
    prefix = f"PO_{now.strftime('%Y%m')}_"

    if po_df.empty:
        return f"{prefix}00001"

    current_month_pos = po_df[po_df["po_id"].str.contains(prefix)]
    if current_month_pos.empty:
        return f"{prefix}00001"

    last_id = current_month_pos["po_id"].sort_values().iloc[-1]
    last_num = int(str(last_id).split("_")[-1])
    return f"{prefix}{(last_num + 1):05d}"


def create_po(pr_id: str | None, proc_item: list, user_id: str | None):
    if not validate_pr_status(pr_id):
        return False

    item_master = db.extract("item", fields=["item_id", "supplier_id"])
    created_pos: list[str] = []

    for po_items_dict in proc_item:
        new_po_id = generate_next_po_id()
        first_item_id = list(po_items_dict.keys())[0]
        supplier_row = item_master[item_master["item_id"] == first_item_id]
        if supplier_row.empty:
            continue
        supplier_id = supplier_row.iloc[0]["supplier_id"]

        new_po_header = pd.DataFrame(
            [
                {
                    "po_id": new_po_id,
                    "pr_id": pr_id,
                    "status": 5,
                    "supplier_id": supplier_id,
                    "created_at": get_now(),
                    "created_by": user_id,
                }
            ]
        )
        db.load("purchase_order", new_po_header, mode="append")
        created_pos.append(new_po_id)

        bridge_entries = []
        for item_id, qty in po_items_dict.items():
            bridge_entries.append({"doc_id": new_po_id, "item_id": item_id, "quantity": qty})
        db.load("purchase_item_bridge", pd.DataFrame(bridge_entries), mode="append")

    db.delete("purchase_item_bridge", conditions={"doc_id": pr_id})
    return created_pos


def get_po_ticket(user_id: str | None):
    role = gatekeeper.get_user_role(user_id)
    if role == "Supplier":
        po_df = db.extract("purchase_order", conditions={"supplier_id": user_id})
    elif role == "Warehouse Personnel":
        po_df = db.extract("purchase_order")
        if not po_df.empty:
            po_df = po_df[po_df["status"].astype(int).isin([6, 7, 8, 9])]
    elif role == "Procurement Officer":
        po_df = db.extract("purchase_order", conditions={"created_by": user_id})
    elif role == "Procurement Manager":
        # Managers see POs from PRs they approved
        all_pos = db.extract("purchase_order")
        if all_pos.empty:
            po_df = all_pos
        else:
            all_prs = db.extract("purchase_request")
            if all_prs.empty:
                po_df = pd.DataFrame()
            else:
                # Filter PRs approved by this manager
                my_prs = all_prs[all_prs["reviewed_by"] == user_id]
                # Join POs with these PRs
                po_df = all_pos.merge(my_prs[["pr_id"]], on="pr_id", how="inner")
    else:
        raise ForbiddenException("Error: Access Denied. Unauthorized role.")

    if po_df.empty:
        return []

    status_df = db.extract("dim_status")
    po_df["status"] = po_df["status"].astype(str)
    status_df["status_id"] = status_df["status_id"].astype(str)
    merged_df = po_df.merge(status_df, left_on="status", right_on="status_id", how="left")

    user_df = db.extract("user", fields=["user_id", "role_id"])
    role_df = db.extract("dim_role", fields=["role_id", "role_name"])
    user_df["role_id"] = user_df["role_id"].astype(str)
    role_df["role_id"] = role_df["role_id"].astype(str)
    user_with_role = user_df.merge(role_df, on="role_id", how="left")

    merged_df = merged_df.merge(
        user_with_role[["user_id", "role_name"]],
        left_on="created_by",
        right_on="user_id",
        how="left",
    )
    merged_df = merged_df.rename(columns={"role_name": "creator_role"})
    if "user_id" in merged_df.columns:
        merged_df = merged_df.drop(columns=["user_id"])

    # Ensure pr_id is included in the output
    cols = ["po_id", "pr_id", "status", "status_name", "created_at", "creator_role"]
    result = merged_df[[c for c in cols if c in merged_df.columns]]
    return result.to_dict(orient="records")


def get_po_details(user_id: str | None, po_id: str | None):
    role = gatekeeper.get_user_role(user_id)
    po_header_df = db.extract("purchase_order", conditions={"po_id": po_id})
    if po_header_df.empty:
        raise NotFoundException("Error: Purchase Order not found.")

    po_data = po_header_df.iloc[0]
    pr_id = po_data.get("pr_id")
    pr_header = db.extract("purchase_request", conditions={"pr_id": pr_id}) if pr_id else pd.DataFrame()

    authorized = False
    if role == "Supplier":
        authorized = po_data["supplier_id"] == user_id
    elif role == "Warehouse Personnel":
        authorized = int(po_data["status"]) in [6, 7, 8, 9]
    elif role == "Procurement Officer":
        authorized = po_data["created_by"] == user_id
    elif role == "Procurement Manager":
        authorized = not pr_header.empty and pr_header.iloc[0]["reviewed_by"] == user_id

    if not authorized:
        raise ForbiddenException("Error: Access Denied. You do not have permission to view this PO.")

    status_df = db.extract("dim_status")
    po_header_df["status"] = po_header_df["status"].astype(str)
    status_df["status_id"] = status_df["status_id"].astype(str)
    po_header_df = po_header_df.merge(
        status_df[["status_id", "status_name"]],
        left_on="status",
        right_on="status_id",
        how="left",
    )

    user_df = db.extract("user", fields=["user_id", "name", "email", "role_id"])
    role_df = db.extract("dim_role", fields=["role_id", "role_name"])
    user_df["role_id"] = user_df["role_id"].astype(str)
    role_df["role_id"] = role_df["role_id"].astype(str)
    user_with_role = user_df.merge(role_df, on="role_id", how="left")

    # PO Creator (Officer)
    po_header_df = po_header_df.merge(
        user_with_role[["user_id", "role_name", "name", "email"]],
        left_on="created_by",
        right_on="user_id",
        how="left",
    )
    po_header_df = po_header_df.rename(columns={"role_name": "creator_role", "name": "officer_name", "email": "officer_email"})

    po_details = po_header_df.iloc[0].to_dict()

    # Supplier Details
    supplier_df = db.extract("supplier", conditions={"supplier_id": po_data["supplier_id"]})
    if not supplier_df.empty:
        po_details["supplier"] = {"name": supplier_df.iloc[0]["name"], "email": supplier_df.iloc[0]["email"]}
    else:
        po_details["supplier"] = None

    # Officer (Details already fetched from po_header_df join)
    po_details["officer"] = {"name": po_details.get("officer_name"), "email": po_details.get("officer_email")}

    # Manager (PR Reviewer)
    if not pr_header.empty:
        reviewer_id = pr_header.iloc[0].get("reviewed_by")
        reviewer_user = user_df[user_df["user_id"] == reviewer_id]
        if not reviewer_user.empty:
            po_details["manager"] = {"name": reviewer_user.iloc[0]["name"], "email": reviewer_user.iloc[0]["email"]}
        else:
            po_details["manager"] = None
    else:
        po_details["manager"] = None

    bridge_df = db.extract("purchase_item_bridge", conditions={"doc_id": po_id})
    item_master = db.extract("item", fields=["item_id", "item_name", "unit_price"])
    details_df = bridge_df.merge(item_master, on="item_id", how="left")

    po_details["items"] = details_df[["item_id", "item_name", "quantity", "unit_price"]].to_dict(
        orient="records"
    )
    return po_details


def update_po_status(supplier_id: str | None, po_id: str | None, status_name: str | None):
    if not gatekeeper.is_authorized(supplier_id, "update_po_status"):
        raise ForbiddenException("Error: Access Denied. You do not have permission to update PO status.")

    status_df = db.extract("dim_status", conditions={"status_name": status_name})
    if status_df.empty:
        raise BadRequestException(f"Error: Status '{status_name}' is not valid.")

    new_status_id = status_df.iloc[0]["status_id"]
    po_check = db.extract("purchase_order", conditions={"po_id": po_id})
    if po_check.empty:
        raise NotFoundException("Error: Purchase Order not found.")

    db.modify("purchase_order", {"status": int(new_status_id)}, {"po_id": po_id})
    return True


