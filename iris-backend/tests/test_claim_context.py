from pipeline.claim_context import incident_anchor, contextual_search_query, incident_evidence_gate


SOURCE = ('American marine biologist Dr. Kent Carpenter, whose scientific testimony supported '
          'the Philippines in its 2016 arbitration case against China, was shot and killed '
          'during a home invasion. The suspects remain at large.')


def test_referential_investigation_requires_its_incident_subject():
    anchor = incident_anchor('The suspects remain at large, and investigators are reviewing CCTV.', SOURCE)
    assert anchor['subject'] == 'Kent Carpenter'
    assert contextual_search_query('suspects CCTV', anchor) == 'Kent Carpenter suspects CCTV'
    for text in ['Probers review Jose Luis Yulo ambush footage.',
                 'The Senate shooting CCTV was turned over to police.']:
        assert not incident_evidence_gate({'text': text}, anchor)['matches']
    assert incident_evidence_gate({'text': 'Carpenter case investigators are pursuing leads.'}, anchor)['matches']
    assert not incident_evidence_gate({'text': 'Carpentering is unrelated.'}, anchor)['matches']


def test_standalone_ruling_does_not_require_victim_name():
    anchor = incident_anchor('The 2016 tribunal ruling rejected the nine-dash line.', SOURCE)
    assert anchor['subject'] is None
    assert incident_evidence_gate({'text': 'The tribunal rejected the claim.'}, anchor)['matches']


def test_ambiguous_or_absent_identity_is_not_invented():
    for source in ['', SOURCE + ' Jane Smith was killed in a different incident.']:
        anchor = incident_anchor('The suspects remain at large.', source)
        assert anchor['subject'] is None
        assert anchor['reason'] == 'unresolved_or_ambiguous_incident_subject'
