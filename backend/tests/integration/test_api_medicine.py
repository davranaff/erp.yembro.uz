from __future__ import annotations

import pytest

from tests.helpers import extract_data, make_auth_headers, run_crud_flow


MEDICINE_RESOURCES = [
    ("/api/v1/medicine/batches", "medicine_batch"),
    ("/api/v1/medicine/types", "medicine_type"),
]
HOME_BATCH_ID = "93111111-1111-1111-1111-111111111101"
FOREIGN_ORG_BATCH_ID = "90909090-9090-9090-9090-909090909090"


@pytest.mark.asyncio
@pytest.mark.parametrize("path,prefix", MEDICINE_RESOURCES)
async def test_medicine_crud_endpoints_are_protected_and_work(api_client, path: str, prefix: str) -> None:
    await run_crud_flow(api_client, path, prefix)


@pytest.mark.asyncio
async def test_medicine_batch_qr_generation_exposes_public_token_page(api_client) -> None:
    qr_response = await api_client.post(
        f"/api/v1/medicine/batches/{HOME_BATCH_ID}/qr",
        headers=make_auth_headers("medicine_batch"),
    )
    assert qr_response.status_code == 201, qr_response.text
    qr_payload = extract_data(qr_response)
    token = str(qr_payload["token"])

    assert qr_payload["batch_id"] == HOME_BATCH_ID
    assert qr_payload["public_url"].endswith(f"/public/medicine/{token}")
    assert str(qr_payload["image_data_url"]).startswith("data:image/png;base64,")

    get_qr_response = await api_client.get(
        f"/api/v1/medicine/batches/{HOME_BATCH_ID}/qr",
        headers=make_auth_headers("medicine_batch"),
    )
    assert get_qr_response.status_code == 200, get_qr_response.text
    get_qr_payload = extract_data(get_qr_response)
    assert get_qr_payload["token"] == token
    assert str(get_qr_payload["image_data_url"]).startswith("data:image/png;base64,")

    public_response = await api_client.get(f"/api/v1/medicine/public/batches/{token}")
    assert public_response.status_code == 200, public_response.text
    public_payload = extract_data(public_response)
    assert public_payload["id"] == HOME_BATCH_ID
    assert public_payload["medicine_type"]["name"]


@pytest.mark.asyncio
async def test_medicine_batch_qr_generation_is_scoped_to_actor_organization(api_client) -> None:
    response = await api_client.post(
        f"/api/v1/medicine/batches/{FOREIGN_ORG_BATCH_ID}/qr",
        headers=make_auth_headers("medicine_batch"),
    )
    assert response.status_code == 403, response.text


@pytest.mark.asyncio
async def test_public_medicine_sell_records_consumption_and_cash_transaction(api_client) -> None:
    """QR-page sell flow: selling through the public token should drop
    stock on the batch AND produce an income cash_transaction in the
    department's active cash account.
    """
    qr_response = await api_client.post(
        f"/api/v1/medicine/batches/{HOME_BATCH_ID}/qr",
        headers=make_auth_headers("medicine_batch"),
    )
    assert qr_response.status_code == 201, qr_response.text
    token = str(extract_data(qr_response)["token"])

    sell_quantity = 25.0
    sell_amount = 180000.0
    sell_response = await api_client.post(
        f"/api/v1/medicine/public/batches/{token}/sell",
        json={"quantity": sell_quantity, "amount": sell_amount, "note": "QR sale"},
    )
    assert sell_response.status_code == 201, sell_response.text

    # Consumption row landed for the batch.
    consumption_list = await api_client.get(
        f"/api/v1/medicine/consumptions?batch_id={HOME_BATCH_ID}&limit=10",
        headers=make_auth_headers("medicine_consumption"),
    )
    assert consumption_list.status_code == 200, consumption_list.text
    consumption_items = extract_data(consumption_list)["items"]
    matching_consumption = [
        row
        for row in consumption_items
        if str(row.get("purpose") or "").strip().lower() == "sale"
    ]
    assert matching_consumption, consumption_items
    assert float(matching_consumption[0]["quantity"]) == pytest.approx(
        sell_quantity, abs=1e-3
    )

    # Cash transaction landed with type=income, department=batch's dept.
    cash_list = await api_client.get(
        "/api/v1/finance/cash-transactions?limit=10",
        headers=make_auth_headers("cash_transaction"),
    )
    assert cash_list.status_code == 200, cash_list.text
    items = extract_data(cash_list)["items"]
    matching = [
        row
        for row in items
        if str(row.get("note") or "").strip() == "QR sale"
        and str(row.get("transaction_type") or "").strip().lower() == "income"
    ]
    assert matching, items
    assert float(matching[0]["amount"]) == pytest.approx(sell_amount, abs=1e-2)


@pytest.mark.asyncio
async def test_public_medicine_sell_rejects_more_than_remaining(api_client) -> None:
    qr_response = await api_client.post(
        f"/api/v1/medicine/batches/{HOME_BATCH_ID}/qr",
        headers=make_auth_headers("medicine_batch"),
    )
    assert qr_response.status_code == 201, qr_response.text
    token = str(extract_data(qr_response)["token"])

    response = await api_client.post(
        f"/api/v1/medicine/public/batches/{token}/sell",
        json={"quantity": 999999999, "amount": 1},
    )
    assert response.status_code == 400, response.text


@pytest.mark.asyncio
async def test_public_medicine_sell_rejects_invalid_token(api_client) -> None:
    response = await api_client.post(
        "/api/v1/medicine/public/batches/bogus-token/sell",
        json={"quantity": 1, "amount": 1},
    )
    assert response.status_code == 404, response.text


@pytest.mark.asyncio
async def test_medicine_batch_attachment_is_downloadable_via_public_token(api_client) -> None:
    qr_response = await api_client.post(
        f"/api/v1/medicine/batches/{HOME_BATCH_ID}/qr",
        headers=make_auth_headers("medicine_batch"),
    )
    assert qr_response.status_code == 201, qr_response.text
    token = str(extract_data(qr_response)["token"])

    upload_response = await api_client.post(
        f"/api/v1/medicine/batches/{HOME_BATCH_ID}/attachment",
        headers=make_auth_headers("medicine_batch"),
        files={"file": ("batch-manual.pdf", b"public-batch-manual-content", "application/pdf")},
    )
    assert upload_response.status_code == 201, upload_response.text
    upload_payload = extract_data(upload_response)
    assert upload_payload["filename"] == "batch-manual.pdf"

    public_details_response = await api_client.get(f"/api/v1/medicine/public/batches/{token}")
    assert public_details_response.status_code == 200, public_details_response.text
    public_details_payload = extract_data(public_details_response)
    attachment = public_details_payload["attachment"]
    assert attachment is not None
    assert attachment["url"] == f"/api/v1/medicine/public/batches/{token}/attachment"

    download_response = await api_client.get(str(attachment["url"]))
    assert download_response.status_code == 200, download_response.text
    assert download_response.content == b"public-batch-manual-content"
