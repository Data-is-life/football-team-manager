"""One real, reproducible offseason fixture shared by API and UI trade checks."""
from app.main import CareerRequest,career_action
from app.lineups import lineup_context
from app.preseason import run
from app.trades import evaluate,player_value


def trading_fixture():
    seed=1234
    args=dict(run_seed=seed,lineup_rules=41,rebuild_team='seattle',draft_rounds=6)
    draft=career_action('seattle',CareerRequest(action='draft',auto_draft=True,**args))
    request=dict(args,manual_picks=draft['manual_picks'])
    market=career_action('seattle',CareerRequest(action='free_agency',**request))
    actions=[{'kind':'drop','player_id':p['id']} for p in market['profile']['roster'] if p.get('renewal_offer') or p.get('contract_offer')]+[{'kind':'finish','player_id':''}]
    review=career_action('seattle',CareerRequest(action='free_agency',free_agency=actions,**request))
    plan=review['payroll_floor_adjustment'];pre=[{'kind':'raise','player_id':plan['player_id']}] if plan else []
    request.update(free_agency=actions,pre_camp_actions=pre,training_camp=True)
    camp=career_action('seattle',CareerRequest(action='camp',**request))
    root=lineup_context((),seed,41,rebuild_team='seattle')
    _,context=run('seattle',1,seed,tuple(draft['manual_picks']),(),root,6,
        tuple((a['kind'],a['player_id']) for a in actions),tuple((a['kind'],a['player_id']) for a in pre),True)
    by_id={p.id:p for _,ps in context for p in ps}
    options=camp['trading']
    proposal=None
    for team in options['teams']:
        for own in options['own_players']:
            for theirs in team['players']:
                if own['position']!=theirs['position'] or own['rating']<=theirs['rating']:continue
                decision=evaluate(context,'seattle',team['id'],own['id'],theirs['id'])
                if decision['accepted']:
                    proposal=dict(kind='swap',other_team=team['id'],give_id=own['id'],receive_id=theirs['id']);break
            if proposal:break
        if proposal:break
    if proposal is None:raise AssertionError('Fixture has no accepted offer')
    checkpoint=dict(version=42,welcomeDismissed=True,ownerUpdateDismissed=0,draftRounds=6,careerStartWeek=17,lineupChanges=[],contracts=False,teamId='seattle',runSeed=seed,season=1,week=17,lineupRules=41,developmentStart=1,rebuildTeam='seattle',priorStandings={},history=[],draftChoices=draft['manual_picks'],dropped=[],rosterActions=[],freeAgency=actions,preCampActions=pre,trainingCamp=True,career=[],playoffRound=4)
    return dict(request=request,camp=camp,checkpoint=checkpoint,proposal=proposal)

if __name__=='__main__':
    import json
    print(json.dumps(trading_fixture()))
