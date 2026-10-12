import os
import sqlite3
import uuid

from tests.conftest import h


def make_project(api, **kw):
    body = {"name": "Keller Barndo", "budget_total": "100000", **kw}
    r = api.post("/projects", json=body, headers=h("manager"))
    assert r.status_code == 201, r.text
    return r.json()


# ---------- auth / RBAC ----------
def test_health_is_public(client):
    assert client.get("/health").json()["status"] == "ok"


def test_missing_and_bad_keys(client):
    assert client.get("/projects").status_code == 401
    assert client.get("/projects", headers={"X-API-Key": "nope"}).status_code == 401


def test_role_enforcement(client):
    assert client.post("/projects", json={"name": "x"}, headers=h("field")).status_code == 403
    p = make_project(client)
    assert client.delete(f"/projects/{p['id']}", headers=h("manager")).status_code == 403
    assert client.get("/feedback", headers=h("manager")).status_code == 403
    assert client.delete(f"/projects/{p['id']}", headers=h("admin")).status_code == 204


# ---------- projects & client PII ----------
def test_project_without_client_is_clean(client):
    p = make_project(client)
    assert p["client"] is None
    assert p["alert_level"] == "none"


def test_client_pii_encrypted_at_rest_and_redacted_for_viewers(client, tmp_path):
    p = make_project(
        client,
        client={
            "name": "Jane Builder",
            "phone": "817-555-0100",
            "email": "jane@example.com",
            "site_address": "123 Ranch Rd, Keller TX",
        },
    )
    assert p["client"]["email"] == "jane@example.com"

    # Viewer sees a redacted version.
    v = client.get(f"/projects/{p['id']}", headers=h("viewer")).json()["client"]
    assert v["redacted"] is True and v["email"] is None and "Jane" not in (v["name"] or "")

    # Raw database never contains plaintext PII.
    db_path = os.environ["DATABASE_URL"].split("sqlite:///", 1)[1]
    raw = sqlite3.connect(db_path).execute("select name, phone, email, site_address from clients").fetchone()
    for value in raw:
        assert value.startswith("v1:")
    dump = "".join(raw)
    assert "Jane" not in dump and "555" not in dump and "Ranch" not in dump


def test_upsert_and_remove_client(client):
    p = make_project(client)
    r = client.put(f"/projects/{p['id']}/client", json={"company": "Acme Homes"}, headers=h("manager"))
    assert r.status_code == 200 and r.json()["company"] == "Acme Homes"
    assert client.delete(f"/projects/{p['id']}/client", headers=h("manager")).status_code == 204
    assert client.get(f"/projects/{p['id']}", headers=h("manager")).json()["client"] is None


def test_invalid_email_rejected(client):
    r = client.post("/projects", json={"name": "x", "client": {"email": "not-an-email"}}, headers=h("manager"))
    assert r.status_code == 422


# ---------- budget & alerts ----------
def test_budget_flow_and_alert_events(client):
    p = make_project(client)
    pid = p["id"]

    def add(cost_type, amount, role="manager", **kw):
        r = client.post(
            f"/projects/{pid}/costs", json={"cost_type": cost_type, "amount": amount, **kw}, headers=h(role)
        )
        assert r.status_code == 201, r.text
        return r.json()

    add("material", "40000", role="field", phase="slab")
    add("labor", "20000", role="field", phase="framing")
    s = client.get(f"/projects/{pid}/budget", headers=h("viewer")).json()
    assert s["burn_rate_pct"] == "60.00" and s["alert_level"] == "none"

    add("purchase_order", "25000")  # 85% -> warning
    s = client.get(f"/projects/{pid}/budget", headers=h("viewer")).json()
    assert s["burn_rate_pct"] == "85.00" and s["alert_level"] == "warning"

    add("remaining_estimate", "20000")  # P_total 105k -> CV < 0 -> critical
    s = client.get(f"/projects/{pid}/budget", headers=h("viewer")).json()
    assert s["cost_variance"] == "-5000.00" and s["alert_level"] == "critical"

    alerts = client.get(f"/projects/{pid}/alerts", headers=h("viewer")).json()
    assert [a["level"] for a in alerts] == ["critical", "warning"]

    # Raising the budget clears the alert and logs that too.
    client.patch(f"/projects/{pid}", json={"budget_total": "200000"}, headers=h("manager"))
    assert client.get(f"/projects/{pid}", headers=h("viewer")).json()["alert_level"] == "none"
    assert len(client.get(f"/projects/{pid}/alerts", headers=h("viewer")).json()) == 3


def test_field_cannot_log_committed_or_estimates(client):
    p = make_project(client)
    for t in ("purchase_order", "unbilled_subcontract", "remaining_estimate"):
        r = client.post(f"/projects/{p['id']}/costs", json={"cost_type": t, "amount": "1"}, headers=h("field"))
        assert r.status_code == 403


def test_negative_amount_rejected(client):
    p = make_project(client)
    r = client.post(f"/projects/{p['id']}/costs", json={"cost_type": "labor", "amount": "-5"}, headers=h("manager"))
    assert r.status_code == 422


def test_offline_replay_is_idempotent(client):
    p = make_project(client)
    cid = str(uuid.uuid4())
    body = {"id": cid, "cost_type": "material", "amount": "1000"}
    assert client.post(f"/projects/{p['id']}/costs", json=body, headers=h("field")).status_code == 201
    assert client.post(f"/projects/{p['id']}/costs", json=body, headers=h("field")).status_code == 200
    assert len(client.get(f"/projects/{p['id']}/costs", headers=h("viewer")).json()) == 1
    other = make_project(client, name="Other")
    assert client.post(f"/projects/{other['id']}/costs", json=body, headers=h("field")).status_code == 409


def test_update_and_delete_cost_recomputes(client):
    p = make_project(client)
    c = client.post(
        f"/projects/{p['id']}/costs", json={"cost_type": "labor", "amount": "90000"}, headers=h("manager")
    ).json()
    assert client.get(f"/projects/{p['id']}", headers=h("viewer")).json()["alert_level"] == "warning"
    client.patch(f"/projects/{p['id']}/costs/{c['id']}", json={"amount": "10"}, headers=h("manager"))
    assert client.get(f"/projects/{p['id']}", headers=h("viewer")).json()["alert_level"] == "none"
    assert client.delete(f"/projects/{p['id']}/costs/{c['id']}", headers=h("manager")).status_code == 204
    assert client.get(f"/projects/{p['id']}/costs", headers=h("viewer")).json() == []


def test_dashboard(client):
    a = make_project(client, name="A", status="active")
    make_project(client, name="B")
    client.post(f"/projects/{a['id']}/costs", json={"cost_type": "labor", "amount": "100000"}, headers=h("manager"))
    d = client.get("/dashboard", headers=h("viewer")).json()
    assert d["project_count"] == 2 and d["active_count"] == 1 and d["critical_count"] == 1
    assert d["recent_alerts"][0]["level"] == "critical"


def test_updated_since_sync(client):
    make_project(client, name="Old")
    stamp = client.get("/projects", headers=h("viewer")).json()[0]["updated_at"]
    make_project(client, name="New")
    names = [p["name"] for p in client.get("/projects", params={"updated_since": stamp}, headers=h("viewer")).json()]
    assert names == ["New"]


# ---------- storage ----------
def test_storage_provision_local(client, tmp_path):
    p = make_project(client, name='Smith "Barndo": Phase/1')
    r = client.post(f"/projects/{p['id']}/storage/provision", headers=h("admin"))
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["folder_name"] == f"{p['id']} - Smith -Barndo- Phase-1"
    for sub in ("Blueprints", "Site_Photos", "Invoices_Receipts", "Client_Docs"):
        assert (tmp_path / "storage" / out["folder_name"] / sub).is_dir()
    # idempotent
    assert client.post(f"/projects/{p['id']}/storage/provision", headers=h("admin")).status_code == 200
    assert client.get(f"/projects/{p['id']}", headers=h("viewer")).json()["storage_provider"] == "local"


# ---------- feedback ----------
def test_feedback_loop(client):
    r = client.post(
        "/feedback",
        json={
            "feedback_type": "bug",
            "message": "Budget screen crashes",
            "severity": "high",
            "screen": "Budget",
            "app_version": "0.1.0",
        },
        headers=h("field"),
    )
    assert r.status_code == 201
    fid = r.json()["id"]
    assert (
        client.post("/feedback", json={"feedback_type": "bug", "message": "x"}, headers=h("viewer")).status_code == 403
    )
    assert len(client.get("/feedback", headers=h("admin")).json()) == 1
    client.patch(f"/feedback/{fid}", json={"status": "resolved"}, headers=h("admin"))
    stats = client.get("/feedback/stats", headers=h("admin")).json()
    assert stats == {"total": 1, "by_type": {"bug": 1}, "by_status": {"resolved": 1}}
