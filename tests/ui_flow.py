"""Browser test of the real UI (headless Chromium). Needs API on :8000 and Vite on :5173.

Run:  .venv\\Scripts\\python -m tests.ui_flow <screenshot_dir>      then  python -m backend.admin reset
"""
import os
import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

UI = os.getenv("FD_UI", "http://localhost:5173")


def main(out: Path):
    out.mkdir(parents=True, exist_ok=True)
    errors = []
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        page = b.new_page(viewport={"width": 1440, "height": 900})
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        page.on("console", lambda m: m.type == "error" and errors.append(f"console: {m.text}"))
        def shot(name, full=False):
            page.wait_for_timeout(700)                      # let entry animations finish
            page.screenshot(path=str(out / f"{name}.png"), full_page=full)

        page.goto(f"{UI}/login")
        expect(page.get_by_text("Project & delivery managers")).to_be_visible(timeout=15000)
        shot("01_login")
        row = page.locator("button:has-text('Project Manager'), button:has-text('Delivery Manager')").first
        first_name = row.locator("div.font-medium").inner_text().split()[0]
        row.click()
        page.get_by_placeholder("Password").fill("wrong")
        page.get_by_role("button", name="Sign in").click()
        expect(page.get_by_text("Incorrect password")).to_be_visible(timeout=5000)
        errors.clear()                                      # the refused login logs a 401 in the console
        page.get_by_placeholder("Password").fill(first_name)
        page.get_by_role("button", name="Sign in").click()
        expect(page.get_by_text("Needs people first")).to_be_visible(timeout=15000)
        expect(page.get_by_text("Live", exact=True)).to_be_visible(timeout=10000)
        shot("02_dashboard", full=True)

        page.goto(f"{UI}/demands")
        expect(page.get_by_text("Open staffing demands")).to_be_visible()
        expect(page.get_by_role("button", name="My projects")).to_be_visible()
        shot("03_demands")
        page.locator("a[href^='/demands/PR']").first.click()
        expect(page.get_by_text("How the shortlist was built")).to_be_visible(timeout=15000)
        shot("04_recommendations", full=True)

        page.get_by_text("Why this score?").first.click()
        expect(page.get_by_text("Factor impact on predicted success")).to_be_visible()
        shot("05_why_this_score")

        page.get_by_role("button", name="Ask assistant").click()
        page.get_by_role("button", name="Who is the best fit?").click()
        expect(page.get_by_text("Rule engine").or_(page.get_by_text("AI · Groq")).first).to_be_visible(timeout=20000)
        box = page.locator("div.fixed.inset-y-0.right-0").bounding_box()
        assert box["y"] == 0 and box["height"] == 900, f"assistant drawer not pinned to the viewport: {box}"
        shot("06_assistant")
        page.locator("div.fixed.inset-y-0.right-0 button").first.click()          # close drawer

        page.get_by_placeholder("Type a name or skill…").fill("Kafka")
        page.locator("div.absolute.z-20 button").first.click()
        expect(page.get_by_text("meets every rule").or_(page.get_by_text("is not eligible")).first).to_be_visible(timeout=10000)

        page.get_by_role("button", name="Run what-if").click()
        expect(page.get_by_text("What-if mode")).to_be_visible(timeout=15000)
        shot("07_whatif")
        page.get_by_text("Back to real demand").click()

        def sign_in(name):
            page.get_by_title("Sign out").click()
            page.locator("button[aria-expanded]", has_text=name).click()
            page.get_by_placeholder("Password").fill(name.split()[0])
            page.get_by_role("button", name="Sign in").click()
            expect(page.get_by_text("Needs people first")).to_be_visible(timeout=15000)

        head = page.locator("header .leading-tight .font-medium").inner_text()
        page.get_by_role("button", name="Select", exact=True).first.click()
        page.get_by_role("button", name="Request allocation").click()
        expect(page.get_by_text("Approval needed from")).to_be_visible()
        page.get_by_placeholder("Why these people? Approvers see this, and it is stored in the audit trail.").fill("Best skill match and free from the start date")
        shot("08_request_dialog")
        page.get_by_role("button", name="Send for approval").click()
        expect(page.get_by_text("Waiting for approval").first).to_be_visible(timeout=15000)
        shot("09_request_sent")

        page.get_by_role("link", name="Go to notifications").click()
        expect(page.get_by_text("Needs people first")).to_be_visible(timeout=15000)
        page.get_by_role("button", name="Waiting").click()
        shot("10_waiting_on_names", full=True)
        chips = page.locator("[title*='manager']").all_inner_texts()
        approvers = [c.strip() for c in chips]
        assert approvers, "requester should see approver names"

        for name in approvers:
            sign_in(name)
            expect(page.get_by_role("button", name="Approve", exact=True)).to_be_visible(timeout=10000)
            shot(f"11_approver_{name.split()[0]}", full=True)
            page.get_by_role("button", name="Approve", exact=True).click()
            expect(page.get_by_text("Nothing waiting for your approval")).to_be_visible(timeout=10000)

        sign_in(head)
        page.get_by_role("button", name="Review & send").click()
        expect(page.get_by_text("Everyone has approved")).to_be_visible(timeout=10000)
        shot("12_review_send")
        page.get_by_role("button", name="Send & assign").click()
        expect(page.get_by_text("Email delivered").first).to_be_visible(timeout=15000)          # live toast
        shot("13_sent_live")

        page.goto(f"{UI}/audit")
        expect(page.get_by_text("approved").first).to_be_visible(timeout=10000)
        page.locator("button:has-text('approved')").first.click()
        expect(page.get_by_text("What the system recommended")).to_be_visible(timeout=10000)
        shot("10_audit")

        page.goto(f"{UI}/new")
        page.get_by_placeholder("e.g. Need 2 senior Java developers").fill(
            "Need 2 senior Java developers with Spring Boot, Kafka and PostgreSQL, 6+ years, from January for 8 months. "
            "Payments experience and Redis are nice to have.")
        page.get_by_role("button", name="Read my request").click()
        expect(page.get_by_text("Confirm the requirements")).to_be_visible(timeout=15000)
        shot("11_new_project_parsed", full=True)

        page.goto(f"{UI}/people")
        page.locator("a[href^='/people/NXT']").first.click()
        expect(page.get_by_text("Project history")).to_be_visible(timeout=10000)
        shot("12_person", full=True)

        page.goto(f"{UI}/model")
        expect(page.get_by_text("Evaluation & fairness")).to_be_visible(timeout=10000)
        shot("13_model_card", full=True)
        b.close()
    print("browser errors:", errors or "none")
    print("UI flow completed - screenshots in", out)
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "ui_screens"))
