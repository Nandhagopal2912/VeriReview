from web.orders import app


def test_unknown_order_is_404():
    client = app.test_client()
    assert client.get("/orders/999").status_code == 404
