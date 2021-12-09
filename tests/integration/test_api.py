# Copyright 2021 Universität Tübingen, DKFZ and EMBL
# for the German Human Genome-Phenome Archive (GHGA)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Test the api module"""

import nest_asyncio
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from metadata_search_service.api.main import app
from metadata_search_service.config import Config, get_config
from tests.fixtures import initialize_test_db  # noqa: F401,F811

nest_asyncio.apply()


def get_config_override():
    return Config(db_url="mongodb://localhost:27017", db_name="metadata-store-test")


app.dependency_overrides[get_config] = get_config_override
client = TestClient(app)


def test_index():
    """Test the index endpoint"""

    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == status.HTTP_200_OK
    assert response.text == '"Index for Metadata Search Service."'


@pytest.mark.parametrize(
    "query,document_type,return_facets,skip,limit,conditions",
    [
        (
            {"query": "*"},
            "Dataset",
            False,
            0,
            10,
            {
                "data": {
                    "title": [
                        "DATA_SET_Coverage_bias_sensitivity_of_variant_calling_for_4_WG_seq_tech",
                        "Whole genome bisufite sequencing for smoking and non-smoking mother-child pairs",
                    ]
                },
                "facets": {},
            },
        ),
        (
            {"query": "*"},
            "Dataset",
            True,
            0,
            10,
            {
                "data": {
                    "title": [
                        "DATA_SET_Coverage_bias_sensitivity_of_variant_calling_for_4_WG_seq_tech",
                        "Whole genome bisufite sequencing for smoking and non-smoking mother-child pairs",
                    ]
                },
                "facets": {
                    "type": {
                        "sample": 1,
                        "Whole genome sequencing": 1,
                        "Exome sequencing": 2,
                        "Methylation profiling by high-throughput sequencing": 1,
                    }
                },
            },
        ),
        (
            {"query": "*"},
            "Dataset",
            True,
            0,
            1,
            {
                "data": {
                    "title": [
                        "DATA_SET_Coverage_bias_sensitivity_of_variant_calling_for_4_WG_seq_tech"
                    ]
                },
                "facets": {
                    "type": {
                        "sample": 1,
                        "Whole genome sequencing": 1,
                        "Exome sequencing": 2,
                        "Methylation profiling by high-throughput sequencing": 1,
                    }
                },
            },
        ),
        (
            {"query": "*"},
            "Study",
            True,
            0,
            10,
            {
                "data": {
                    "title": [
                        "Coverage bias and sensitivity of variant calling for four whole-genome sequencing technologies",
                        "Epigenomic alterations define lethal CIMP-positive ependymomas of infancy",
                    ]
                },
                "facets": {
                    "type": {"Other": 3, "Whole Genome Sequencing": 1, "Epigenetics": 1}
                },
            },
        ),
        (
            {"query": "*", "filters": [{"key": "type", "value": "Exome sequencing"}]},
            "Dataset",
            True,
            0,
            10,
            {
                "data": {
                    "title": [
                        "Exome sequencing of serially transplanted genetically marked IC-enriched primary PDAC cultures.",
                        "Schwannomatosis WES data",
                    ]
                },
                "facets": {"type": {"Exome sequencing": 2}},
            },
        ),
        (
            {
                "query": "*",
                "filters": [
                    {"key": "type", "value": "Exome sequencing"},
                    {"key": "has_study.type", "value": "Other"},
                ],
            },
            "Dataset",
            True,
            0,
            10,
            {
                "data": {"title": ["Schwannomatosis WES data"]},
                "facets": {"type": {"Exome sequencing": 1}},
            },
        ),
        (
            {"query": "pancreatic cancer"},
            "Dataset",
            True,
            0,
            10,
            {
                "data": {
                    "title": [
                        "Exome sequencing of serially transplanted genetically marked IC-enriched primary PDAC cultures.",
                    ]
                },
                "facets": {"type": {"Exome sequencing": 1}},
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_search(
    initialize_test_db,  # noqa: F811
    query,
    document_type,
    return_facets,
    skip,
    limit,
    conditions,
):
    url = f"/rpc/search?document_type={document_type}&return_facets={return_facets}&skip={skip}&limit={limit}"
    response = client.post(
        url,
        json=query,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["hits"]) > 0
    if conditions["data"]:
        data_keys = conditions["data"].keys()
        for i in range(0, len(data["hits"])):
            hit = data["hits"][i]
            doc = hit["content"]
            for key in data_keys:
                if i >= len(conditions["data"][key]):
                    break
                assert doc[key] == conditions["data"][key][i]

    if return_facets:
        assert len(data["facets"]) > 0
        facets = {}
        if conditions["facets"]:
            for facet in data["facets"]:
                facets[facet["key"]] = {
                    x["option"]: x["count"] for x in facet["options"]
                }
            for facet_name in conditions["facets"]:
                assert facet_name in facets
                for key, value in conditions["facets"][facet_name].items():
                    assert (
                        key in facets[facet_name] and facets[facet_name][key] == value
                    )
