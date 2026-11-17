"""Real rules-42 checkpoints for API and browser integration checks."""
from app.main import CareerRequest,career_action

def simple_fixture():
    args=dict(run_seed=1234,lineup_rules=42,rebuild_team='seattle',draft_rounds=6)
    d=career_action('seattle',CareerRequest(action='draft',auto_draft=True,**args))
    args['manual_picks']=d['manual_picks']
    own=career_action('seattle',CareerRequest(action='own_players',**args))
    actions=[]
    for p in own['profile']['roster']:
        if p.get('renewal_offer'): actions.append(dict(kind='drop',player_id=p['id']))
        elif p.get('contract_offer'): actions.append(dict(kind='sign',player_id=p['id']))
    actions.append(dict(kind='finish',player_id=''))
    checkpoint=dict(version=43,welcomeDismissed=True,ownerUpdateDismissed=0,draftRounds=6,careerStartWeek=17,lineupChanges=[],contracts=False,teamId='seattle',runSeed=1234,season=1,week=17,lineupRules=42,developmentStart=1,rebuildTeam='seattle',priorStandings={},history=[],draftChoices=d['manual_picks'],dropped=[],rosterActions=[],freeAgency=[],ownActions=[],career=[],playoffRound=4)
    return dict(request=args,own=own,actions=actions,checkpoint=checkpoint)

if __name__=='__main__':
    import json
    print(json.dumps(simple_fixture()))
