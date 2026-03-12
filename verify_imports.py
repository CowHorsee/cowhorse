# verify_imports.py
import os
import sys

# Add project root to sys.path to simulate normal execution if needed
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    print("Testing imports...")
    from services.sharedlib.db_helper.db_helper import DBHelper
    print("✓ DBHelper imported")
    from services.sharedlib.rbac_helper.role_permissions_check import RBACGatekeeper
    print("✓ RBACGatekeeper imported")
    from services.sharedlib.email_helper.email_helper import quick_send
    print("✓ quick_send imported")
    from services.sharedlib.pdf_helper.pdf import generate_pdf
    print("✓ generate_pdf imported")
    from services.scripts.user_management import login
    print("✓ user_management.login imported")
    from services.scripts.purchase_request import create_pr
    print("✓ purchase_request.create_pr imported")
    from api.schemas.base import ErrorResponse
    print("✓ ErrorResponse imported")
    
    print("\nAll major imports successful!")
except ImportError as e:
    print(f"\n✗ ImportError: {e}")
    sys.exit(1)
except Exception as e:
    print(f"\n✗ Unexpected error: {type(e).__name__}: {e}")
    sys.exit(1)
