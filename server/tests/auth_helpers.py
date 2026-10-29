from app.core.security import SESSION_COOKIE, create_access_token, csrf_token

PASSWORD = "fictional-test-password-123"


def auth_headers(db, user_id):
    token = create_access_token(user_id, db)
    db.commit()
    return {"Cookie": f"{SESSION_COOKIE}={token}", "X-CSRF-Token": csrf_token(token)}


def approve(client, headers, scope):
    response = client.post('/api/v1/auth/reauthenticate', headers=headers, json={"password": PASSWORD, "scope": scope})
    assert response.status_code == 200, response.text
    return {**headers, "X-Sensitive-Grant": response.json()["grant"]}
