"""Regression tests for OSLC prefixed queries and JSON-LD result parsing."""

import httpx
import pytest
import respx

from elm_mcp import oslc
from elm_mcp.auth import close_client

BASE = "https://elm.example.com"


@pytest.fixture(autouse=True)
async def cleanup(monkeypatch):
    monkeypatch.setattr("elm_mcp.config.settings.elm_url", BASE)
    yield
    await close_client()

RM_ROOTSERVICES_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<rdf:Description xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
    xmlns:oslc_rm="http://open-services.net/xmlns/rm/1.0/">
    <oslc_rm:rmServiceProviders rdf:resource="{BASE}/rm/catalog"/>
</rdf:Description>"""

RM_CATALOG_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
    xmlns:oslc="http://open-services.net/ns/core#"
    xmlns:dcterms="http://purl.org/dc/terms/">
    <oslc:ServiceProvider>
        <dcterms:title>RM Proj</dcterms:title>
        <oslc:services rdf:resource="{BASE}/rm/oslc_rm/_proj1/services.xml"/>
    </oslc:ServiceProvider>
</rdf:RDF>"""

RM_SERVICE_XML = ""  # _find_query_base derives /views from oscl_rm project id


def _jsonld_payload():
    resource = f"{BASE}/rm/resources/BI_1"
    query = f"{BASE}/rm/views?oslc.query=true&projectURL={BASE}/rm/rm-projects/_proj1"
    return {
        resource: {
            "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": [
                {"type": "uri", "value": "http://open-services.net/ns/rm#Requirement"}
            ],
            "http://purl.org/dc/terms/title": [{"type": "literal", "value": "Mapping"}],
        },
        query: {
            "http://www.w3.org/2000/01/rdf-schema#member": [
                {"type": "uri", "value": resource}
            ]
        },
        query + "&oslc.where=test": {
            "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": [
                {"type": "uri", "value": "http://open-services.net/ns/core#ResponseInfo"}
            ],
            "http://purl.org/dc/terms/title": [{"type": "literal", "value": "Query Results: 1"}],
        },
    }


@respx.mock
async def test_query_resources_sends_oslc_prefix():
    """A prefixed oslc.where is declared via oslc.prefix (ELM rejects otherwise)."""
    respx.post(f"{BASE}/jts/j_security_check").mock(return_value=httpx.Response(200))
    respx.get(f"{BASE}/rm/rootservices").mock(
        return_value=httpx.Response(200, text=RM_ROOTSERVICES_XML)
    )
    respx.get(f"{BASE}/rm/catalog").mock(
        return_value=httpx.Response(200, text=RM_CATALOG_XML)
    )
    query_url = f"{BASE}/rm/views"
    route = respx.get(query_url).mock(
        return_value=httpx.Response(200, json=_jsonld_payload())
    )

    results = await oslc.query_resources(
        "rm", "RM Proj", 'dcterms:identifier="358661"'
    )
    request = route.calls[0].request
    assert "oslc.prefix" in request.url.params
    assert "dcterms=<http://purl.org/dc/terms/>" in request.url.params["oslc.prefix"]
    assert len(results) == 1
    assert results[0]["rdf:about"] == f"{BASE}/rm/resources/BI_1"
    assert results[0]["title"] == ["Mapping"]


def test_parse_query_results_skips_metadata():
    """ResponseInfo / RequirementCollection nodes are not returned as artifacts."""
    results = oslc._parse_query_results(_jsonld_payload())
    assert len(results) == 1
    assert results[0]["rdf:about"] == f"{BASE}/rm/resources/BI_1"


def test_parse_query_results_simple_shapes():
    """CCM/QM simple oslc:results and rdfs:member shapes still work."""
    simple = {"oslc:results": [{"rdf:about": f"{BASE}/ccm/wi/1", "dcterms:title": "WI"}]}
    assert oslc._parse_query_results(simple) == simple["oslc:results"]
    members = {"rdfs:member": [{"rdf:about": f"{BASE}/ccm/wi/2"}]}
    assert oslc._parse_query_results(members) == members["rdfs:member"]


def test_parse_query_results_jsonld_no_membership():
    """Without rdfs:member, any typed non-metadata node is an artifact."""
    data = {
        f"{BASE}/rm/resources/BI_2": {
            "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": [
                {"type": "uri", "value": "http://open-services.net/ns/rm#Requirement"}
            ],
            "http://purl.org/dc/terms/title": [{"type": "literal", "value": "T"}],
        }
    }
    results = oslc._parse_query_results(data)
    assert len(results) == 1
    assert results[0]["title"] == ["T"]
