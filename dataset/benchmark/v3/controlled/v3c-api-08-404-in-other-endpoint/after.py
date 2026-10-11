from fastapi import FastAPI, HTTPException

app = FastAPI()
INVOICES = {}


@app.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: int):
    return INVOICES[invoice_id]


@app.delete("/invoices/{invoice_id}")
def delete_invoice(invoice_id: int):
    if invoice_id not in INVOICES:
        raise HTTPException(status_code=404, detail="invoice not found")
    del INVOICES[invoice_id]
    return {"deleted": invoice_id}
