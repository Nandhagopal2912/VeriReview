from fastapi import FastAPI, HTTPException

app = FastAPI()
INVOICES = {}


@app.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: int):
    return INVOICES[invoice_id]


@app.delete("/invoices/{invoice_id}")
def delete_invoice(invoice_id: int):
    del INVOICES[invoice_id]
    return {"deleted": invoice_id}
