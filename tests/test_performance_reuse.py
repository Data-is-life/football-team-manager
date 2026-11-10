"""Golden outputs captured from main before the performance refactor."""
from dataclasses import asdict, is_dataclass
from hashlib import sha256
import json
from pathlib import Path
from unittest import TestCase

from app.career import offseason, training_camp
from app.draft import build_draft
from app.free_agency import free_agency, free_agency_order
from app.lineups import lineup_context
from app.player_contracts import contract_expired


def digest(value):
    return sha256(json.dumps(value,default=lambda x:asdict(x) if is_dataclass(x) else x,
                             sort_keys=True,separators=(',',':')).encode()).hexdigest()


def market_fixture(seed=1234,rules=30):
    root=lineup_context((),seed,rules,rebuild_team='seattle')
    board,_=build_draft('seattle',1,seed,roster_context=root,auto_pick=True,draft_rounds=6)
    choices=tuple(board['manual_picks'])
    _,camp=training_camp('seattle',1,seed,choices,(),root,6)
    drops=tuple(p.id for p in dict(camp)['seattle'] if p.rookie_offer or contract_expired(p,2))
    actions=tuple(('drop',identity) for identity in drops)
    args=('seattle',1,seed,choices,drops,(),root,6,actions)
    _,context=offseason(*args)
    order=free_agency_order(1,seed,(),root)
    return args,context,order


def baseline_cases():
    for seed in (1234,5678):
        for rules in (1,28,29,30):
            root=lineup_context((),seed,rules)
            rounds=4 if rules==1 else 6
            board,_=build_draft('seattle',1,seed,roster_context=root,auto_pick=True,draft_rounds=rounds)
            for count in (0,3):
                choices=tuple(board['manual_picks'][:count])
                yield f'draft-{seed}-{rules}-{count}',lambda s=seed,c=root,n=rounds,p=choices:build_draft('seattle',1,s,p,roster_context=c,auto_pick=not p,draft_rounds=n,return_league=True)
        for rules in (29,30):
            args,context,order=market_fixture(seed,rules)
            opened,_=free_agency('seattle',1,seed,context,order)
            player=next(p['id'] for p in opened['available'] if p['affordable'])
            cases={'open':(), 'wave7':tuple(('pass','') for _ in range(6)),
                   'finish':(('finish',''),), 'sign-pass':(('sign',player),('pass',''))}
            for name,actions in cases.items():
                yield f'market-{seed}-{rules}-{name}',lambda s=seed,c=context,o=order,a=actions:free_agency('seattle',1,s,c,o,a)


class PerformanceParityTests(TestCase):
    def test_outputs_match_before_optimization(self):
        expected=json.loads(Path(__file__).with_name('performance_baseline.json').read_text())['sha256']
        seen=set()
        for name,operation in baseline_cases():
            with self.subTest(case=name):
                seen.add(name)
                self.assertEqual(digest(operation()),expected[name])
        self.assertEqual(seen,set(expected))

    def test_draft_metadata_is_bounded_by_prospect_count(self):
        from unittest.mock import patch
        from app.draft import CLASS_SIZE
        from app.ratings import rating_payload
        context=lineup_context((),1234,30)
        with patch('app.draft.rating_payload',wraps=rating_payload) as ratings:
            result=build_draft('seattle',1,1234,roster_context=context,
                               auto_pick=True,draft_rounds=6,return_league=True)
        self.assertLessEqual(ratings.call_count,CLASS_SIZE+38)
        expected=json.loads(Path(__file__).with_name('performance_baseline.json').read_text())['sha256']
        self.assertEqual(digest(result),expected['draft-1234-30-0'])

    def test_market_reuses_payroll_and_potential_without_changing_output(self):
        from unittest.mock import patch
        from app.player_contracts import cap_payroll,contract_potential
        _,context,order=market_fixture()
        with patch('app.free_agency.cap_payroll',wraps=cap_payroll) as payroll:
            with patch('app.free_agency.contract_potential',wraps=contract_potential) as potential:
                result=free_agency('seattle',1,1234,context,order,(('finish',''),))
        self.assertLessEqual(payroll.call_count,2*len(order))
        self.assertLessEqual(potential.call_count,len(context.free_agents))
        expected=json.loads(Path(__file__).with_name('performance_baseline.json').read_text())['sha256']
        self.assertEqual(digest(result),expected['market-1234-30-finish'])

    def test_preparation_cache_is_immutable_isolated_and_invalidates(self):
        from dataclasses import FrozenInstanceError,replace
        from app.career import prepare_free_agency
        from app.main import career_action,CareerRequest
        args,_,_=market_fixture()
        prepare_free_agency.cache_clear()
        first=prepare_free_agency(*args)
        self.assertIs(first,prepare_free_agency(*args))
        with self.assertRaises(FrozenInstanceError): first.season=99
        request=CareerRequest(action='free_agency',season=1,run_seed=1234,lineup_rules=30,
            rebuild_team='seattle',draft_rounds=6,manual_picks=list(args[3]),dropped=list(args[4]),
            training_camp=True,roster_actions=[dict(kind=k,player_id=i) for k,i in args[8]])
        response=career_action('seattle',request)
        original=digest(response)
        response['available'].clear()
        response['profile']['roster'][0]['name']='Changed only in response'
        self.assertEqual(digest(career_action('seattle',request)),original)
        self.assertEqual(prepare_free_agency.cache_info().misses,1)
        root=args[6]; identity,state=root.development[0]
        changed=replace(root,development=((identity,replace(state,potential=state.potential-1)),)+root.development[1:])
        different=prepare_free_agency(*args[:6],changed,*args[7:])
        self.assertIsNot(first,different)
        self.assertEqual(prepare_free_agency.cache_info().misses,2)
        self.assertEqual(prepare_free_agency.cache_info().maxsize,32)
