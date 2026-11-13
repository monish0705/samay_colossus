"""Real production React + FastAPI + SQLite; disposable TEST_ONLY private purchases."""

import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from run_sale_e2e import ROOT, free_port, ready


def main():
    from playwright.sync_api import expect, sync_playwright

    for stream in [sys.stdout, sys.stderr]:
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    backend_port, frontend_port = free_port(), free_port()
    password = "TEST_ONLY-" + secrets.token_urlsafe(18)
    env = {
        **os.environ,
        "SAMAY_SALE_E2E_ADMIN_PASSWORD": password,
        "SAMAY_BACKEND_URL": f"http://127.0.0.1:{backend_port}",
        "VITE_API_BASE_URL": "/backend",
    }
    reports = ROOT / "reports"
    errors = []
    steps = []
    headers = {"X-SAMAY-Action": "1"}
    with (
        tempfile.TemporaryDirectory(prefix="samay-private-purchasing-TEST_ONLY-") as directory,
        (reports / "private-purchasing-browser-server.log").open("w", encoding="utf-8") as log,
    ):
        backend = subprocess.Popen(
            [sys.executable, "tests/http_fixture_server.py", "--folder", directory, "--port", str(backend_port)],
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=log,
        )
        frontend = None
        try:
            ready(f"http://127.0.0.1:{backend_port}/api/health", backend)
            frontend = subprocess.Popen(
                [
                    shutil.which("node"),
                    str(ROOT / "frontend/node_modules/vite/bin/vite.js"),
                    "preview",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(frontend_port),
                    "--strictPort",
                ],
                cwd=ROOT / "frontend",
                env=env,
                stdout=log,
                stderr=log,
            )
            base = f"http://127.0.0.1:{frontend_port}"
            ready(base, frontend)
            with sync_playwright() as p:
                launch = {"headless": True}
                if os.getenv("SAMAY_E2E_CHROMIUM"):
                    launch["executable_path"] = os.environ["SAMAY_E2E_CHROMIUM"]
                browser = p.chromium.launch(**launch)
                owner = browser.new_context(viewport={"width": 1440, "height": 1000}, timezone_id="Asia/Kolkata")
                farmer = browser.new_context(timezone_id="Asia/Kolkata")
                admin = browser.new_context()
                owner.add_init_script("localStorage.setItem('samay-language','en')")
                page = owner.new_page()
                page.on("pageerror", lambda e: errors.append(str(e)))

                def call(context, path, body=None, key=False, method=None):
                    h = {**headers, **({"Idempotency-Key": secrets.token_hex(16)} if key else {})}
                    url = base + "/backend/api/v1" + path
                    result = context.request.fetch(url, method=method or ("POST" if body is not None else "GET"), headers=h, data=body)
                    assert result.ok, (result.status, result.text(), path)
                    return result.json()

                call(admin, "/auth/login", {"email": "admin@example.test", "password": password})
                for context, email in [(owner, "business@example.test"), (farmer, "farmer@example.test")]:
                    call(context, "/auth/register", {"name": "TEST_ONLY private purchasing account", "email": email, "password": password})
                crop = next(c for c in call(owner, "/commodities") if c["name"] == "Tomato")
                today = datetime.now(ZoneInfo("Asia/Kolkata"))
                arrival = today + timedelta(days=2)
                expiry = today + timedelta(days=7)
                for kind in ["PRIVATE_BUYER", "PRIVATE_MANDI"]:
                    payload = {
                        "business_type": kind,
                        "name": "TEST_ONLY " + kind,
                        "contact_name": "TEST_ONLY contact",
                        "phone": "+919000000000",
                        "email": "business@example.test",
                        "address": "TEST_ONLY private address",
                        "district": "Kolar",
                        "state": "Karnataka",
                        "registration_details": "TEST_ONLY registration evidence",
                        "verification_information": "TEST_ONLY independent verification evidence",
                        "document_references": ["TEST_ONLY secure reference"],
                        "commodity_ids": [crop["id"]],
                        **(
                            {"buyer_type": "INDIVIDUAL_TRADER"} if kind == "PRIVATE_BUYER" else {"operating_hours": "TEST_ONLY 09:00-17:00"}
                        ),
                    }
                    business = call(owner, "/business/register", payload, key=True)
                    call(
                        admin,
                        f"/admin/businesses/{business['id']}/verify",
                        {
                            "version": business["version"],
                            "state": "VERIFIED",
                            "evidence": "TEST_ONLY independently checked contact and business identity",
                            "contact_verified": True,
                            "registration_checked": True,
                            "documents_required": True,
                        },
                    )
                    role = "PRIVATE_BUYER" if kind == "PRIVATE_BUYER" else "PRIVATE_MANDI_OWNER"
                    call(owner, "/business/active-role", {"mode": "BUSINESS", "business_id": business["id"], "role": role})
                    page.goto(base + f"/business/{'buyer' if kind == 'PRIVATE_BUYER' else 'mandi'}/{business['id']}")
                    expect(page.get_by_role("button", name="Create New Buying Offer", exact=True)).to_be_visible()
                    page.get_by_role("button", name="Create New Buying Offer", exact=True).click()
                    page.get_by_role("combobox", name="Crop", exact=True).select_option(str(crop["id"]))

                    def fill(values):
                        for label, value in values.items():
                            page.get_by_label(label, exact=True).fill(value)

                    fill(
                        {
                            "Variety": "local",
                            "Grade or quality requirement": "faq",
                            "Crop condition": "TEST_ONLY fresh",
                            "Acceptable quality standards": "TEST_ONLY clean produce",
                            "Total quantity required (quintals)": "100",
                            "Minimum farmer quantity (quintals)": "1",
                            "Maximum farmer quantity (quintals)": "100",
                            "Maximum daily intake (quintals)": "100",
                        }
                    )
                    page.get_by_role("button", name="Continue", exact=True).click()
                    page.get_by_role("combobox", name="Price type", exact=True).select_option("NEGOTIABLE")
                    fill(
                        {
                            "Offered price (INR/quintal)": "1000.25",
                            "Minimum negotiable price (INR/quintal)": "900",
                            "Maximum offered price (INR/quintal)": "1200",
                            "Price basis": "TEST_ONLY INR/quintal after inspection",
                            "Offer starts (your local time)": (today - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
                            "Offer expires (your local time)": expiry.strftime("%Y-%m-%dT%H:%M"),
                            "Price valid until (your local time)": expiry.strftime("%Y-%m-%dT%H:%M"),
                        }
                    )
                    page.get_by_role("button", name="Continue", exact=True).click()
                    fill({"Service or pickup area": "TEST_ONLY local area"})
                    page.get_by_role("button", name="Continue", exact=True).click()
                    fill(
                        {
                            "Unloading charge (INR)": "5",
                            "Weighment arrangements": "TEST_ONLY certified scale",
                            "Arrival dates (YYYY-MM-DD, comma separated)": arrival.date().isoformat(),
                            "Payment methods (comma separated)": "TEST_ONLY bank transfer",
                            "Payment timing": "TEST_ONLY after weighment",
                            "Payment terms": "TEST_ONLY explicit business payment terms",
                            "Known deductions": "TEST_ONLY unloading charge",
                            "Contact availability": "TEST_ONLY business hours",
                        }
                    )
                    page.get_by_role("button", name="Continue", exact=True).click()
                    expect(page.get_by_text("Review every term before saving.", exact=False)).to_be_visible()
                    page.get_by_role("button", name="Save buying offer", exact=True).click()
                    expect(page.get_by_role("button", name="Publish offer", exact=True)).to_be_visible()
                    page.get_by_role("button", name="Publish offer", exact=True).click()
                    expect(page.get_by_role("button", name="Pause offer", exact=True)).to_be_visible()
                    offers = call(owner, f"/business/offers?business_id={business['id']}")
                    offer = offers[0]
                    request = call(
                        farmer,
                        f"/private-purchases/offers/{offer['id']}/requests",
                        {
                            "offer_version": offer["version"],
                            "available_quantity": "30",
                            "quantity": "20",
                            "expected_price": "1000",
                            "variety": "local",
                            "grade": "faq",
                            "arrival_at": arrival.isoformat(),
                            "quality_confirmed": True,
                            "terms_confirmed": True,
                            "contact_consent": False,
                            "message": "TEST_ONLY request to exact offer",
                        },
                        key=True,
                    )
                    page.get_by_role("button", name="Refresh purchasing records", exact=True).click()
                    page.get_by_role("button", name="Incoming Farmer Requests", exact=True).click()
                    expect(page.get_by_role("heading", name=request["public_id"], exact=True)).to_be_visible()
                    page.get_by_role("combobox", name="Response action", exact=True).select_option("counteroffer")
                    fill(
                        {
                            "Accepted quantity (quintals)": "15",
                            "Confirmed price (INR/quintal)": "1025.50",
                            "Response expiry (your local time)": (today + timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M"),
                            "Confirm payment terms": "TEST_ONLY frozen agreed payment terms",
                            "Response explanation": "TEST_ONLY inspected lot terms",
                        }
                    )
                    page.once("dialog", lambda dialog: dialog.accept())
                    page.get_by_role("button", name="Send response", exact=True).click()
                    expect(page.get_by_text("COUNTEROFFERED", exact=True)).to_be_visible()
                    req = next(r for r in call(farmer, "/private-purchases/requests") if r["id"] == request["id"])
                    assert req["responses"][0]["quantity"] == "15.000"
                    call(farmer, f"/private-purchases/requests/{req['id']}/confirm", {"version": req["version"]})
                    page.get_by_role("button", name="Refresh purchasing records", exact=True).click()
                    page.get_by_role("button", name="Overview", exact=True).click()
                    expect(page.get_by_text("85.000", exact=True)).to_be_visible()
                    a = call(owner, f"/business/analytics?business_id={business['id']}")
                    assert a["confirmed_quantity"] == "15.000" and a["completed_purchases"] == 0
                    page.get_by_role("button", name="My Buying Offers", exact=True).click()
                    page.get_by_role("button", name="Edit offer", exact=True).click()
                    page.get_by_role("button", name="Continue", exact=True).click()
                    expect(page.get_by_label("Offered price (INR/quintal)", exact=True)).to_have_value("1000.25")
                    page.get_by_label("Offered price (INR/quintal)", exact=True).fill("1100")
                    for _ in range(3):
                        page.get_by_role("button", name="Continue", exact=True).click()
                    page.get_by_role("button", name="Save buying offer", exact=True).click()
                    expect(page.get_by_role("button", name="Edit offer", exact=True)).to_be_visible()
                    frozen = next(r for r in call(farmer, "/private-purchases/requests") if r["id"] == request["id"])
                    assert (
                        frozen["responses"][0]["price"] == "1025.50"
                        and frozen["responses"][0]["terms"]["payment_terms"] == "TEST_ONLY frozen agreed payment terms"
                    )
                    saved = call(owner, f"/business/offers/{offer['id']}")
                    assert len(saved["price_history"]) == 2 and saved["quantity_remaining"] == "85.000"
                    page.get_by_role("button", name="Details and revision history", exact=True).click()
                    expect(page.get_by_role("heading", name="Price history", exact=True)).to_be_visible()
                    page.screenshot(path=str(reports / f"private-purchasing-{kind.lower()}.png"), full_page=True, animations="disabled")
                    page.get_by_role("button", name="ಕನ್ನಡ", exact=True).click()
                    page.get_by_role("button", name="ಅವಲೋಕನ", exact=True).click()
                    expect(page.get_by_text("85.000", exact=True)).to_be_visible()
                    page.set_viewport_size({"width": 390, "height": 844})
                    page.wait_for_function("document.querySelector('.sidebar').getBoundingClientRect().right <= 0")
                    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                    page.screenshot(
                        path=str(reports / f"private-purchasing-{kind.lower()}-mobile-kn.png"), full_page=True, animations="disabled"
                    )
                    page.get_by_role("button", name="English", exact=True).click()
                    page.set_viewport_size({"width": 1440, "height": 1000})
                    steps.append(
                        kind
                        + ": real UI draft/publish, exact-offer request, business counteroffer, farmer API confirmation, revision preserves agreement, mobile Kannada same quantities"
                    )
                assert not errors, errors
                browser.close()
            result = {
                "status": "passed",
                "scope": "Prompt 2 only; isolated TEST_ONLY accounts, no external payment/verification claims",
                "steps": steps,
                "page_errors": errors,
                "farmer_discovery_ui_implemented": False,
                "appointments_or_actual_sales_claimed": False,
            }
            (reports / "private-purchasing-browser.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(json.dumps(result, indent=2))
        finally:
            for process in [frontend, backend]:
                if process:
                    process.terminate()
                    process.wait(timeout=20)


if __name__ == "__main__":
    main()
