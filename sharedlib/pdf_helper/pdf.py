import asyncio
import os
import io
import logging
from jinja2 import Environment, FileSystemLoader


async def generate_pdf(data, output_path=None):
    """
    Generates a PDF from a template using the provided data using Playwright.
    If output_path is provided, it saves the PDF there and returns the path.
    Otherwise, it returns the PDF bytes.
    """
    # 1. Setup Jinja2 to load templates from the current directory
    template_dir = os.path.dirname(os.path.abspath(__file__))
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template('pdf_template.html')

    # 2. Render HTML with dynamic data
    html_content = template.render(data)

    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        # Launch browser (Ensure 'playwright install chromium' has been run)
        try:
            browser = await p.chromium.launch(headless=True)
        except Exception as e:
            logging.error(f"Failed to launch Playwright browser. This is expected on some Azure Functions plans. Error: {e}")
            raise RuntimeError("PDF generation requires a server environment with Playwright browsers installed. If this is on Azure, consider a Linux Premium Plan with a Custom Container.") from e
        
        page = await browser.new_page()
        
        # Set content and wait for it to be ready
        await page.set_content(html_content, wait_until="networkidle")
        
        # Generate PDF
        pdf_bytes = await page.pdf(
            format="A4",
            print_background=True,
            margin={"top": "20px", "right": "20px", "bottom": "20px", "left": "20px"}
        )
        
        await browser.close()

    if output_path:
        out_dir = os.path.dirname(output_path)
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir)
            
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
        logging.info(f"PDF generated successfully at {output_path}")
        return output_path
    
    return pdf_bytes

def _enrich_items(doc_id):
    """Internal helper to get items with names and prices."""
    from sharedlib.db_helper.db_ops import DBHelper
    db = DBHelper()
    bridge = db.extract("purchase_item_bridge", conditions={"doc_id": doc_id})
    if bridge.empty:
        return []
    
    items_master = db.extract("item", fields=["item_id", "item_name", "unit_price"])
    merged = bridge.merge(items_master, on="item_id", how="left")
    
    return [
        {
            "name": row["item_name"],
            "quantity": row["quantity"],
            "unit_price": row["unit_price"]
        }
        for _, row in merged.iterrows()
    ]

async def generate_pr_doc(pr_id):
    """Enriches data and generates a PR PDF."""
    from sharedlib.db_helper.db_ops import DBHelper
    db = DBHelper()
    header = db.extract("purchase_request", conditions={"pr_id": pr_id})
    if header.empty:
        logging.error(f"PR {pr_id} not found for PDF generation")
        return None
    
    pr_data = header.iloc[0].to_dict()
    items = _enrich_items(pr_id)
    
    # Get user details
    user = db.extract("user", conditions={"user_id": pr_data.get("created_by")})
    officer_name = user.iloc[0]["user_name"] if not user.empty else "System / AI"
    officer_email = user.iloc[0]["email"] if not user.empty else None
    
    pdf_data = {
        "doc_type": "PR",
        "doc_id": pr_id,
        "date": pr_data.get("created_at")[:10] if pr_data.get("created_at") else None,
        "created_at": pr_data.get("created_at"),
        "officer_name": officer_name,
        "officer_email": officer_email,
        "items": items
    }
    
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "api", "purchase_request_pdf")
    output_path = os.path.join(output_dir, f"{pr_id}.pdf")
    
    return await generate_pdf(pdf_data, output_path=output_path)

async def generate_po_doc(po_id):
    """Enriches data and generates a PO PDF."""
    from sharedlib.db_helper.db_ops import DBHelper
    db = DBHelper()
    header = db.extract("purchase_order", conditions={"po_id": po_id})
    if header.empty:
        logging.error(f"PO {po_id} not found for PDF generation")
        return None
    
    po_data = header.iloc[0].to_dict()
    items = _enrich_items(po_id)
    
    # Get user details (Officer)
    user = db.extract("user", conditions={"user_id": po_data.get("created_by")})
    officer_name = user.iloc[0]["user_name"] if not user.empty else "System"
    officer_email = user.iloc[0]["email"] if not user.empty else None
    
    # Get Supplier details
    supplier = db.extract("supplier", conditions={"supplier_id": po_data.get("supplier_id")})
    supplier_contact = supplier.iloc[0]["contact_person"] if not supplier.empty else None
    supplier_email = supplier.iloc[0]["email"] if not supplier.empty else None
    
    pdf_data = {
        "doc_type": "PO",
        "doc_id": po_id,
        "date": po_data.get("created_at")[:10] if po_data.get("created_at") else None,
        "created_at": po_data.get("created_at"),
        "officer_name": officer_name,
        "officer_email": officer_email,
        "supplier_contact": supplier_contact,
        "supplier_email": supplier_email,
        "items": items
    }
    
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "api", "purchase_order_pdf")
    output_path = os.path.join(output_dir, f"{po_id}.pdf")
    
    return await generate_pdf(pdf_data, output_path=output_path)

# Example usage for manual testing if run directly
if __name__ == "__main__":
    test_data = {
        "doc_type": "PO",
        "doc_id": "TEST-123",
        "date": "2026-03-08",
        "items": [
            {"name": "Test Item", "quantity": 1, "unit_price": 100.0}
        ]
    }
    asyncio.run(generate_pdf(test_data, "test_output.pdf"))