# Medicine Authenticity Verification System using Blockchain

This project is a beginner-friendly Flask app that stores medicine registrations in a custom blockchain and verifies batches with a batch ID.

## Folder Structure

```text
blockchain_project/
|-- app.py
|-- blockchain.py
|-- requirements.txt
|-- README.md
|-- data/
|   `-- blockchain_data.json
|-- static/
|   |-- style.css
|   `-- qrcodes/
`-- templates/
    |-- base.html
    |-- index.html
    |-- add_medicine.html
    |-- verify.html
    `-- chain.html
```

## Features

- Custom blockchain with SHA256 hashing
- Block class with index, previous hash, timestamp, Merkle root, nonce, and hash
- Proof-of-Work mining
- Chain validation
- Medicine registration
- QR code generation for each batch
- Verification by batch ID
- Supply chain tracking for Distributor and Pharmacy updates
- Full traceability history for a batch
- Simple HTML/CSS UI

## How To Run

1. Open a terminal in the project folder.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the app:

```bash
python app.py
```

4. Open the browser:

```text
http://127.0.0.1:5000/
```

## Routes

- `/` - Home page
- `/add_medicine` - Add a medicine batch
- `/supply_chain` - Add distributor or pharmacy updates
- `/verify` - Verify a batch ID
- `/chain` - View the full blockchain

## Notes

- Mining difficulty is set to `3` so the app stays responsive.
- QR images are saved in `static/qrcodes/`.
- Blockchain data is saved in `data/blockchain_data.json`.
