"""Regression tests for the RM get_requirement fix (2026-11-18).

Bug 1: IBM ELM DOORS Next resource endpoints only serve rdf+xml; a JSON
       GET gets 415 (CRRRS6402E). get_resource must fall back and parse RDF.
Bug 2: a raw httpx.HTTPStatusError escaping an MCP tool crashes the stdio
       server. The @tool boundary must translate HTTP errors into ToolError.
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from mcp.server.mcpserver.exceptions import ToolError

from elm_mcp import oslc, server

BASE = "https://elm.example.com"
URI = BASE + "/rm/resources/TX_TEST"

RM_RDFXML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
    '         xmlns:dcterms="http://purl.org/dc/terms/"'
    '         xmlns:jazz_rm="http://jazz.net/ns/rm#"'
    '         xmlns:oslc="http://open-services.net/ns/core#">'
    '  <rdf:Description rdf:about="' + URI + '">'
    '    <rdf:type rdf:resource="http://open-services.net/ns/rm#Requirement"/>'
    '    <dcterms:identifier rdf:datatype="http://www.w3.org/2001/XMLSchema#string">403669</dcterms:identifier>'
    '    <dcterms:title rdf:parseType="Literal">Test requirement</dcterms:title>'
    '    <jazz_rm:primaryText rdf:parseType="Literal"><div xmlns="http://www.w3.org/1999/xhtml"><p>Body</p></div></jazz_rm:primaryText>'
    '    <oslc:instanceShape rdf:resource="' + BASE + '/rm/types/OT_TEST"/>'
    '  </rdf:Description>'
    '</rdf:RDF>'
)


@pytest.fixture(autouse=True)
async def _reset_client():
    from elm_mcp.auth import close_client

    yield
    await close_client()


def test_rdfxml_to_resource_dict_parses_requirement():
    data = oslc._rdfxml_to_resource_dict(RM_RDFXML, URI)
    assert data["rdf:about"] == URI
    assert data["dcterms:identifier"] == "403669"
    assert data["dcterms:title"] == "Test requirement"
    assert "Body" in data["jazz_rm:primaryText"]
    assert data["oslc:instanceShape"] == {"rdf:resource": BASE + "/rm/types/OT_TEST"}


async def test_get_resource_falls_back_to_rdfxml_on_415():
    client = AsyncMock()
    client.get.side_effect = [
        httpx.Response(415, json={"detailedMessage": "CRRRS6402E"}, request=httpx.Request("GET", URI)),
        httpx.Response(200, text=RM_RDFXML, headers={"content-type": "application/rdf+xml"}, request=httpx.Request("GET", URI)),
    ]
    with patch("elm_mcp.oslc.get_client", new=AsyncMock(return_value=client)):
        data = await oslc.get_resource(URI)
    assert client.get.await_count == 2
    assert data["dcterms:identifier"] == "403669"


async def test_get_resource_keeps_json_path_when_supported():
    client = AsyncMock()
    client.get.return_value = httpx.Response(200, json={"dcterms:title": "WI"}, request=httpx.Request("GET", URI))
    with patch("elm_mcp.oslc.get_client", new=AsyncMock(return_value=client)):
        data = await oslc.get_resource(URI)
    assert client.get.await_count == 1
    assert data == {"dcterms:title": "WI"}


async def test_tool_boundary_translates_httpstatuserror_to_toolerror():
    req = httpx.Request("GET", URI)
    err = httpx.HTTPStatusError("415", request=req, response=httpx.Response(415, request=req))

    @server.tool
    async def _boom():
        raise err

    with pytest.raises(ToolError, match="415"):
        await _boom()


async def test_tool_boundary_translates_httperror_to_toolerror():
    err = httpx.ConnectError("connection closed")

    @server.tool
    async def _boom():
        raise err

    with pytest.raises(ToolError, match="connection error"):
        await _boom()
