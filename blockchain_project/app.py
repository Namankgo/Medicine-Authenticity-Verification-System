import os
import re
from datetime import datetime
from urllib.parse import parse_qs, urlparse

import qrcode
from flask import Flask, flash, render_template, request
from werkzeug.utils import secure_filename

from blockchain import MedicineBlockchain


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data", "blockchain_data.json")
QR_FOLDER = os.path.join(BASE_DIR, "static", "qrcodes")

os.makedirs(QR_FOLDER, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "medicine-authenticity-demo-secret")

# Difficulty 3 keeps mining fast enough for a simple beginner project.
blockchain = MedicineBlockchain(difficulty=3, storage_path=DATA_FILE)


def extract_batch_id(raw_value):
    """
    Accept either:
    - a plain batch ID
    - pasted QR text containing a 'Batch ID:' line
    - a URL with ?batch_id=...
    """
    text = (raw_value or "").strip()
    if not text:
        return ""

    parsed_url = urlparse(text)
    if parsed_url.query:
        query_values = parse_qs(parsed_url.query)
        if "batch_id" in query_values and query_values["batch_id"]:
            return query_values["batch_id"][0].strip()

    query_values = parse_qs(text)
    if "batch_id" in query_values and query_values["batch_id"]:
        return query_values["batch_id"][0].strip()

    match = re.search(r"Batch\s*ID\s*[:=]\s*([A-Za-z0-9._-]+)", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    return text


def generate_qr_code(transaction):
    """Create a QR code image for the medicine batch and save it to static/qrcodes."""
    safe_batch = secure_filename(transaction["batch_id"]) or "batch"
    file_name = f"{safe_batch}_{transaction['transaction_id']}.png"
    file_path = os.path.join(QR_FOLDER, file_name)
    verification_url = f"{request.url_root.rstrip('/')}/verify?batch_id={transaction['batch_id']}"
    stage_name = transaction.get("stage", "Manufacturer")
    party_name = transaction.get("party_name") or transaction.get("manufacturer_name") or "Unknown"

    qr_text = (
        "Medicine Authenticity Verification\n"
        f"Medicine Name: {transaction['medicine_name']}\n"
        f"Batch ID: {transaction['batch_id']}\n"
        f"Stage: {stage_name}\n"
        f"Party: {party_name}\n"
        f"Registered At: {transaction['registered_at']}\n"
        f"Verify URL: {verification_url}\n"
        "Check this batch ID in the Flask app to verify authenticity."
    )

    qr = qrcode.QRCode(version=2, box_size=8, border=4)
    qr.add_data(qr_text)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    image.save(file_path)

    return file_name


def get_dashboard_data():
    """Collect the small set of values shown on the home page."""
    records = blockchain.get_all_records()
    return {
        "chain_valid": blockchain.is_chain_valid(),
        "total_blocks": max(len(blockchain.chain) - 1, 0),
        "total_medicines": len(records),
        "total_batches": blockchain.get_unique_batch_count(),
        "recent_records": records[:5],
    }


@app.context_processor
def inject_common_values():
    """Provide the current chain status to every template."""
    return {
        "chain_valid_global": blockchain.is_chain_valid(),
        "current_time": datetime.now().strftime("%d %b %Y, %I:%M %p"),
    }


@app.route("/")
def home():
    """Home page with project summary and recent medicine registrations."""
    return render_template("index.html", dashboard=get_dashboard_data())


@app.route("/add_medicine", methods=["GET", "POST"])
def add_medicine():
    """Register a medicine batch and mine it into the blockchain."""
    success_data = None

    if request.method == "POST":
        medicine_name = request.form.get("medicine_name", "").strip()
        batch_id = request.form.get("batch_id", "").strip()
        manufacturer_name = request.form.get("manufacturer_name", "").strip()

        if not medicine_name or not batch_id or not manufacturer_name:
            flash("Please fill in all fields before submitting.", "error")
        else:
            transaction = blockchain.create_transaction(
                medicine_name=medicine_name,
                batch_id=batch_id,
                manufacturer_name=manufacturer_name,
                qr_code_file="",
                stage="Manufacturer",
                party_name=manufacturer_name,
            )
            qr_code_file = generate_qr_code(transaction)
            transaction["qr_code_file"] = qr_code_file

            blockchain.add_transaction(transaction)
            new_block = blockchain.mine_pending_transactions()
            batch_history = blockchain.get_batch_history(batch_id)

            success_data = {
                "transaction": transaction,
                "block": new_block,
                "history": batch_history,
                "qr_image": f"qrcodes/{qr_code_file}",
                "verification_url": f"/verify?batch_id={transaction['batch_id']}",
            }
            flash("Medicine batch added and mined successfully.", "success")

    return render_template("add_medicine.html", success_data=success_data)


@app.route("/supply_chain", methods=["GET", "POST"])
def track_supply_chain():
    """Record distributor and pharmacy updates for an existing medicine batch."""
    success_data = None

    if request.method == "POST":
        medicine_name = request.form.get("medicine_name", "").strip()
        batch_id = request.form.get("batch_id", "").strip()
        stage = request.form.get("stage", "").strip()
        party_name = request.form.get("party_name", "").strip()
        from_party = request.form.get("from_party", "").strip()
        to_party = request.form.get("to_party", "").strip()
        notes = request.form.get("notes", "").strip()

        if not medicine_name or not batch_id or not stage or not party_name:
            flash("Please fill in the medicine, batch, stage, and party name.", "error")
        else:
            transaction = blockchain.create_transaction(
                medicine_name=medicine_name,
                batch_id=batch_id,
                manufacturer_name="",
                qr_code_file="",
                stage=stage,
                party_name=party_name,
                from_party=from_party,
                to_party=to_party,
                notes=notes,
            )

            blockchain.add_transaction(transaction)
            new_block = blockchain.mine_pending_transactions()
            batch_history = blockchain.get_batch_history(batch_id)

            success_data = {
                "transaction": transaction,
                "block": new_block,
                "history": batch_history,
            }
            flash(f"{stage} stage added to the blockchain successfully.", "success")

    return render_template("supply_chain.html", success_data=success_data)


@app.route("/verify", methods=["GET", "POST"])
def verify():
    """Verify a batch ID and show full traceability history."""
    result = None
    input_value = ""
    display_value = ""

    if request.method == "POST":
        input_value = request.form.get("batch_id", "")
    else:
        input_value = request.args.get("batch_id", "")

    if input_value:
        extracted_batch_id = extract_batch_id(input_value)
        found, history = blockchain.verify_batch(extracted_batch_id)
        display_value = extracted_batch_id
        result = {
            "batch_id": extracted_batch_id,
            "input_value": input_value,
            "is_genuine": found,
            "history": history,
        }

    return render_template("verify.html", result=result, batch_value=display_value or input_value)


@app.route("/chain")
def view_chain():
    """Display the full blockchain and whether it validates correctly."""
    return render_template(
        "chain.html",
        chain=blockchain.get_chain_data(),
        difficulty=blockchain.difficulty,
        is_valid=blockchain.is_chain_valid(),
    )


if __name__ == "__main__":
    run_port = int(os.environ.get("PORT", "5000"))
    run_host = os.environ.get("HOST", "127.0.0.1")
    run_debug = os.environ.get("DEBUG", "1").lower() not in {"0", "false", "no"}
    app.run(host=run_host, port=run_port, debug=run_debug)
