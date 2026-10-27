"""Item C: cross-domain context helpers join cost, governance, reliability and adoption as grounded facts."""
from src import cross_domain as cd
from src.data import get_models, get_telemetry


def test_normalize_provider_maps_telemetry_labels_to_canonical():
    assert cd.normalize_provider('Azure OpenAI') == 'Azure'
    assert cd.normalize_provider('AWS Bedrock') == 'AWS'
    assert cd.normalize_provider('GCP Vertex AI') == 'GCP'
    assert cd.normalize_provider('Azure') == 'Azure'


def test_provider_context_is_grounded_cost_and_governance():
    pc = cd.provider_context('Azure OpenAI')
    assert pc['provider'] == 'Azure'
    assert isinstance(pc['high_risk'], int) and isinstance(pc['review_due'], int)
    assert ('%' in pc['variance']) or (pc['variance'] == 'N/A')


def test_model_context_discloses_no_telemetry_match():
    row = get_models().iloc[0].copy()
    row['name'] = 'A Model Not In Telemetry 9Z'
    ctx = cd.model_context(row)
    assert ctx['Operational Footprint (telemetry)'] == 'No telemetry match for this model name'
    assert 'chargeback variance' in ctx['Provider Context (cost & governance)']


def test_error_context_joins_provider_and_discloses_unmatched_model():
    tel = get_telemetry(demo=True)
    ctx = cd.error_context(tel, 'Azure OpenAI', 'A Model Not In Governance 9Z')
    assert 'Leading provider context (cost & governance)' in ctx
    assert ctx['Leading model governance match'].endswith('not matched to the governance inventory')
