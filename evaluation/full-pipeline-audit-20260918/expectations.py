"""Reviewer expectations, not model verdicts or automatically certified gold labels."""
from collect import HERE, write

# A single case may have several legitimate claim units; no fixed card quotas.
ROWS = [
('A01','Imaginary nine-dash-line ownership','caution','Preserve imaginary/satirical framing; do not assert literal ownership or invent missing image context.',[],['screening']),
('A02','Padilla-Wamil hearing exchanges','verify','Preserve full attributed questions and replies, BARMM/terrorism, AOM/funds, evaluation correction, agent names and classified answer. Merge repeated utterances.', ['S01'],['translation','screening','claim_extraction','evidence_review']),
('A03','Kent Carpenter biography and killing','verify','Cover death, companion, investigation, police quote, 1975 work, written/oral testimony, tribunal ruling, Verde research, UNESCO advocacy and tributes. Exclude eulogy. Retain conflicting incident accounts and dates.', ['S03','S04','S17','S18'],['claim_extraction','evidence_review','technical']),
('A04','Bea Borres reunion and co-parenting denial','verify','Retain reunion and scope of attributed denial. Not co-parenting as a couple is narrower than no co-parenting at all.', ['S05'],['screening']),
('A05','Padilla Senate position and Duterte bail','verify','Retain Article 11 Section 2 attribution, impeachment statement, complete request to Senate with recipient, and bail amount/count/people. No opinion-to-fact conversion.', ['S15'],['claim_extraction','evidence_review']),
('A06','EDSA rehabilitation and Sonza criticism','verify','Keep damage, locations, project start, estimated P1.2 billion, Sonza criticism and time-bounded no-response assertion. Do not conflate project budgets or invent as-of date.', ['S07','S22'],['translation','screening']),
('A07','Padilla medicines and terrorism','verify','Keep the entire assertion and separately assess background/exposure, medicines, terrorism and claimed funds rationale. Security rationale alone does not prove medicines rationale.', ['S01'],['evidence_review','technical']),
('A08','Samaniego video game interview','verify','Preserve speaker, DZRH Special on Saturday July 4, quotations, online-contacts argument, more than 20 games, ratings argument and hypothetical cinema analogy. Other interview dates/stations are not the same event.', ['S08'],['translation','screening','claim_extraction','evidence_review']),
('A09','Peso closing exchange rate','verify','Preserve PHP62.513 per USD1, Wednesday September 9, and distinguish low level from day-on-day depreciation.', ['S20'],['translation','screening']),
('A10','Ten National Artists','verify','Retain announcement of ten artists and award description. Do not discard a documented announcement merely because recognition is forthcoming.', ['S11','S12'],['screening']),
('B01','Perez death investigation / NBI Matibag','verify','Keep reported death, investigation and named Matibag utterances tied to this death. Reporter credit is not a source condition. Reject unrelated NBI investigations.', [],['claim_extraction','attribution','evidence_review']),
('B02','Palace conviction threshold','verify','Verify the Palace statement on the conviction threshold; normalize Malacanang typography without weakening the specific assertion.', [],['attribution']),
('B03','Palace advice on confidential operations','verify','Keep the agency advice and Remulla reported plan with attribution. Distinguish announcement from completed operation.', [],[]),
('B04','ICC second detention review','verify','Keep second review, detention decision and court reasons, pending fitness decision, and first appearance date. Preserve reporting time and no invented verdict on technical failure.', [],['technical']),
('B05','Arrest after shooting ex-partner new companion','verify','Keep victim relationship, online-taunt motive and arrest as one incident. Do not accept a generic arrest from another shooting.', [],['evidence_review']),
('B06','Prediction about senator-judges motives','stop','Treat predicted bias/public mood and hoped-for justice as commentary, not a documented voting decision.', [],['screening']),
('B07','Vote wisely civic appeal','stop','Under the stated news-verification scope, generic advocacy/hypothetical hiring analogies are not concrete reported events.', [],['screening','claim_extraction']),
('B08','Solar boy nickname','caution','Do not resolve the nickname by guessing a formal name. Evaluative anonymous hearsay must not gain an invented speaker.', [],['claim_extraction','attribution']),
('B09','Rhetorical mugshot questions','stop','Do not invent an identified individual, detention event or missing photograph from this ambiguous rhetorical input.', [],[]),
('B10','Loren return speculation and imprisonment','verify','Separate speculation about future travel/motives from the reported former Speaker imprisonment in QC Payatas. Preserve the uncertainty.', [],['claim_extraction']),
('B11','BIR VAT on system loss','verify','Check the BIR tax action separately from congratulations and political appraisal.', [],[]),
('B12','Loren defense commentary','verify','Keep actual interview/reporting, advocacy references, attributed defenses, twice-impeached assertion and relevant historical factual statements. Do not turn analogies or criticism into established allegations.', [],['claim_extraction','evidence_review']),
('B13','Imagined Robin questions','stop','Retain anticipated hypothetical framing and all three questions. Do not verify that Robin actually asked them.', [],['screening','claim_extraction']),
('B14','Carpio detention and quorum quote','verify','Check that Carpio made the complete statement. Do not substitute a legal ruling on its underlying correctness.', [],[]),
('B15','Byeon Woo-seok fan meeting','verify','Retain Instagram action and specific tour, date including 2026, and venue. Treat different event/year/date as mismatch; exclude aesthetic praise.', ['R-fanmeet'],['retrieval']),
('B16','NASA galaxy composite image','out_of_scope','Under the user-stated Philippine scope, route to out of scope, not false/invalid; do not spend news-verification work on unrelated astronomy.', [],['screening']),
('C01','Baste subpoena','verify','Retain subpoena, trial relation, September 23 and unexplained-wealth allegation. Valid article/passage ownership is required.', [],['technical']),
('C02','Zuckerberg DICT budget','verify','Retain 2027 budget deferral, DICT, proposed summons and Facebook child-safety/violence rationale.', [],['technical']),
('C03','Eala and Wintour','verify','Cover NYFW Michael Kors seating and complete Wintour US Open utterance. Do not mix related embedded entertainment stories into the evidence.', ['R-eala'],['retrieval','article_extraction']),
('C04','DepEd longer OJT','verify','Cover employer feedback, proposed 80-160 to 640 hour increase and same-employer hiring prospects. Preserve proposal rather than completed implementation.', ['R-deped'],['retrieval']),
('C05','Rene Baterbonia UST','verify','Preserve no prior UST connection and family comfort with UST, without confusing Rene with his father.', ['R-rene'],['retrieval']),
('C06','Padilla plans and political warnings','verify','Retain no-future-election announcement, child/family rationale, endorsements and attributed quotations. Political warnings are per claim, including explicitly identified official speaker.', [],['political_flags']),
('C07','Moira September 17 media appearance','verify','Keep September 17 QC appearance, October 4 concert, and healing remarks connected to that appearance. Older interviews are not proof of that event; supplied concert article gives only partial reference coverage.', ['R-moira'],['evidence_review']),
('C08','VERA Poquiz false attribution','verify','Distinguish circulating allegation from assertion that it is fake. The allegation must not become an endorsed fact. Retrieve actual fact-check article, never a search page.', ['R-vera'],['retrieval','claim_extraction'])]


if __name__ == '__main__':
    write(HERE / 'expectations.json', [dict(zip(
        ['id','topic','route','expected_behavior','reference_ids','historical_issue_categories'], r)) for r in ROWS])
    print('Wrote expectations for', len(ROWS), 'previously examined development cases.')
