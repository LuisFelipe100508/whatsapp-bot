def test_health_endpoint_needs_no_database(client):
    # Sem a marca django_db: se a view tocasse o banco, o pytest bloquearia.
    response = client.get("/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}