import asyncio
import logging
import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from services.sharedlib.db_helper.table_storage import DBHelper


async def generate_pdf(data: dict, output_path: str | None = None):
    template_dir = Path(__file__).resolve().parent
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    template = env.get_template("pdf_template.html")
    html_content = template.render(**data)

    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True)
        except Exception as exc:
            logging.error(f"Failed to launch Playwright browser: {exc}")
            raise RuntimeError(
                "PDF generation requires Playwright browsers installed."
            ) from exc

        page = await browser.new_page()
        await page.set_content(html_content, wait_until="networkidle")
        pdf_bytes = await page.pdf(
            format="A4",
            print_background=True,
            margin={"top": "20px", "right": "20px", "bottom": "20px", "left": "20px"},
        )
        await browser.close()

    if output_path:
        out_dir = os.path.dirname(output_path)
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir)
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
        return output_path

    return pdf_bytes


def _enrich_items(doc_id: str):
    db = DBHelper()
    bridge = db.extract("purchase_item_bridge", conditions={"doc_id": doc_id})
    if bridge.empty:
        return []
    items_master = db.extract("item", fields=["item_id", "item_name", "unit_price"])
    merged = bridge.merge(items_master, on="item_id", how="left")
    return [
        {
            "name": row.get("item_name"),
            "quantity": row.get("quantity"),
            "unit_price": row.get("unit_price"),
        }
        for _, row in merged.iterrows()
    ]


async def generate_pr_doc(pr_id: str):
    db = DBHelper()
    header = db.extract("purchase_request", conditions={"pr_id": pr_id})
    if header.empty:
        return None
    pr_data = header.iloc[0].to_dict()
    items = _enrich_items(pr_id)
    user = db.extract("user", conditions={"user_id": pr_data.get("created_by")})
    officer_name = user.iloc[0].get("name") if not user.empty else "System / AI"
    officer_email = user.iloc[0].get("email") if not user.empty else None

    pdf_data = {
        "doc_type": "PR",
        "doc_id": pr_id,
        "date": pr_data.get("created_at")[:10] if pr_data.get("created_at") else None,
        "created_at": pr_data.get("created_at"),
        "officer_name": officer_name,
        "officer_email": officer_email,
        "items": items,
    }
    output_dir = Path(__file__).resolve().parents[1] / "generated" / "purchase_request_pdf"
    output_path = str(output_dir / f"{pr_id}.pdf")
    return await generate_pdf(pdf_data, output_path=output_path)


async def generate_po_doc(po_id: str):
    db = DBHelper()
    header = db.extract("purchase_order", conditions={"po_id": po_id})
    if header.empty:
        return None
    po_data = header.iloc[0].to_dict()
    items = _enrich_items(po_id)
    user = db.extract("user", conditions={"user_id": po_data.get("created_by")})
    officer_name = user.iloc[0].get("name") if not user.empty else "System"
    officer_email = user.iloc[0].get("email") if not user.empty else None

    supplier = db.extract("supplier", conditions={"supplier_id": po_data.get("supplier_id")})
    supplier_contact = supplier.iloc[0].get("contact_person") if not supplier.empty else None
    supplier_email = supplier.iloc[0].get("email") if not supplier.empty else None

    pdf_data = {
        "doc_type": "PO",
        "doc_id": po_id,
        "date": po_data.get("created_at")[:10] if po_data.get("created_at") else None,
        "created_at": po_data.get("created_at"),
        "officer_name": officer_name,
        "officer_email": officer_email,
        "supplier_contact": supplier_contact,
        "supplier_email": supplier_email,
        "items": items,
    }
    output_dir = Path(__file__).resolve().parents[1] / "generated" / "purchase_order_pdf"
    output_path = str(output_dir / f"{po_id}.pdf")
    return await generate_pdf(pdf_data, output_path=output_path)


if __name__ == "__main__":
    asyncio.run(generate_pdf({"doc_type": "TEST", "doc_id": "TEST"}, "test_output.pdf"))
