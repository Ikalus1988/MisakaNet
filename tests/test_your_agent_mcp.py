from agents.your_agent import MCP_PROTOCOL_VERSION, YourAgent


def test_your_agent_legacy_contract_preserved():
    agent = YourAgent("YourAgent")
    assert agent.run("Task A") == "failure"
    assert agent.get_lesson("failure") is None
    assert agent.run("Task B", lesson="prior") == "success"
    assert agent.get_lesson("success") == "Lesson learned from success"


def test_your_agent_mcp_register_search_and_write_envelopes():
    recorded = []

    def fake_transport(url, payload, headers):
        recorded.append((url, payload, headers))
        name = payload["params"]["name"]
        if name == "misakanet_register":
            return {"jsonrpc": "2.0", "id": payload["id"], "result": {"node_id": "Misaka10999", "token": "tok_test_123"}}
        if name == "misakanet_search":
            return {"jsonrpc": "2.0", "id": payload["id"], "result": {"lessons": []}}
        if name == "misakanet_write_lesson":
            return {"jsonrpc": "2.0", "id": payload["id"], "result": {"lesson_id": "lesson-test-1", "status": "pending_review"}}
        return {"jsonrpc": "2.0", "id": payload["id"], "result": {"dedup_key": "dk-1"}}

    agent = YourAgent("test-mcp-agent", transport=fake_transport)
    reg = agent.register_mcp()
    assert agent.node_id == "Misaka10999"
    assert agent.token == "tok_test_123"
    assert recorded[0][2]["MCP-Protocol-Version"] == MCP_PROTOCOL_VERSION

    srch = agent.search_mcp("DroidGuard RemoteHandleImpl ByteArray bundle")
    assert srch["result"]["lessons"] == []

    wr = agent.write_lesson_mcp(
        title="Android Bundle.getString silently drops ByteArray entries in RemoteHandleImpl",
        problem="Play Integrity pia_express passes piaExpressDeviceKey as ByteArray in DroidGuardResultsRequest.bundle, which Bundle.getString returns null for.",
        fix="Inspect Bundle.get(key) runtime type and Base64-encode ByteArray entries under x-request-b64-<key>.",
        verification="Run RemoteDroidGuardPlayIntegrityTest round-trip assertions.",
        domain="android",
    )
    assert wr["result"]["lesson_id"] == "lesson-test-1"
    assert recorded[2][2]["Authorization"] == "Bearer tok_test_123"
