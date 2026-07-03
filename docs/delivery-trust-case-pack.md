# Delivery Trust Case Pack

The Delivery Trust Case Pack is a portable, metadata-only evidence bundle for
external consumers. It lets a customer reviewer or platform Agent verify the
Delivery Trust Case matrix from the ZIP alone.

It packages:

- Delivery Trust Case fixtures;
- the `delivery-trust-case-v1` schema;
- JSON/HTML harness evidence;
- runner and verifier scripts;
- trust model and handoff docs;
- a ZIP-only consumer walkthrough report.

## Generate

```bash
python3 scripts/generate_delivery_trust_case_pack.py
python3 scripts/verify_delivery_trust_case_pack_consumer_walkthrough.py --write
```

## Verify

```bash
python3 scripts/generate_delivery_trust_case_pack.py --check
python3 scripts/verify_delivery_trust_case_pack_consumer_walkthrough.py --check
```

Verify as an external adopter from the ZIP alone:

```bash
python3 scripts/verify_delivery_trust_case_pack_consumer_walkthrough.py \
  --pack platform/generated/study-anything-delivery-trust-case-pack.zip
```

## Boundary

The pack proves deterministic metadata-only handoff gating. It does not prove
production approval, real customer delivery, customer outcome guarantee, general
model correctness, legal certification, or security certification.

The pack does not include raw source text, raw customer payloads, artifact
bodies, screenshots, attention streams, secrets, cookies, bearer tokens, signed
URLs, or user-owned Agent credentials.
