from dataclasses import replace
from unittest import TestCase
from app.lineups import lineup_context
from app.main import CareerRequest, career_action
from app.career import cpu_cuts
from app.player_contracts import PlayerContract, release_preview, record_release, contract_expired


class ReleasePreviewTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request = dict(season=1, run_seed=1234, lineup_rules=26, rebuild_team='seattle', draft_rounds=6)
        draft = career_action('seattle', CareerRequest(action='draft', auto_draft=True, **cls.request))
        cls.request.update(manual_picks=draft['manual_picks'], training_camp=True)
        cls.camp = career_action('seattle', CareerRequest(action='camp', **cls.request))

    def test_preview_matches_actual_signed_and_unsigned_transactions_without_mutation(self):
        before = self.camp['profile']
        for p in (next(p for p in before['roster'] if p.get('contract',{}).get('status')=='active'),
                  next(p for p in before['roster'] if p.get('contract_offer'))):
            with self.subTest(player=p['id']):
                preview = p['release_preview']
                self.assertTrue(preview['allowed'])
                after = career_action('seattle', CareerRequest(action='cuts', dropped=[p['id']],
                    roster_actions=[dict(kind='drop',player_id=p['id'])], **self.request))['profile']['payroll']
                self.assertEqual(preview['payroll_after'],after['total'])
                self.assertEqual(preview['cap_space_after'],after['cap_space'])
                self.assertEqual(preview['new_dead_cap'],after['dead_cap']-before['payroll']['dead_cap'])
                self.assertEqual(preview['cap_space_change'],after['cap_space']-before['payroll']['cap_space'])
                if p.get('contract_offer'):
                    self.assertEqual(preview['dead_cap_schedule'],[])
                    self.assertEqual(preview['total_obligation'],0)
                else:
                    years=p['contract']['expires_after_season']-1
                    self.assertEqual(preview['total_obligation'],years*p['contract']['annual_salary'])
                    self.assertEqual(preview['dead_cap_schedule'][0]['season'],2)
        self.assertEqual(self.camp,career_action('seattle',CareerRequest(action='camp',**self.request)))

    def test_required_replacement_and_expired_hold(self):
        context=lineup_context((),1234,26,rebuild_team='seattle')
        players=cpu_cuts(dict(context)['seattle'],31,31)
        kicker=next(p for p in players if p.position=='K')
        # A replacement is required even at the total/position minimum.
        preview=release_preview(players,kicker,'seattle',1,1234,context)
        self.assertTrue(preview['allowed'])
        self.assertEqual(preview['replacement_cost'],1_000_000)
        self.assertEqual(preview['cap_space_change'],-1_000_000)
        self.assertEqual(preview['replacements'],[dict(position='K',annual_salary=1_000_000)])
        expired=replace(kicker,contract=PlayerContract(4_000_000,1,1,'veteran'))
        players=[expired if p.id==kicker.id else p for p in players]
        preview=release_preview(players,expired,'seattle',2,1234,context)
        self.assertEqual(preview['total_obligation'],0)
        self.assertEqual(preview['new_dead_cap'],0)
        self.assertEqual(preview['cap_space_change'],2_950_000)

    def test_impossible_replacement_is_blocked_and_existing_dead_cap_is_not_new(self):
        context=lineup_context((),1234,26,rebuild_team='seattle')
        players=cpu_cuts(dict(context)['seattle'],31,31)
        kicker=next(p for p in players if p.position=='K')
        committed=sum(p.contract.annual_salary for p in players if not contract_expired(p,1))
        prior=replace(kicker,id='previous-cut',contract=PlayerContract(200_000_000-committed-500_000,1,4,'veteran'))
        context=record_release(context,'seattle',prior,1)
        original=context
        preview=release_preview(players,kicker,'seattle',1,1234,context)
        self.assertFalse(preview['allowed'])
        self.assertIn('guaranteed salary plus required replacement',preview['reason'])
        self.assertEqual(preview['new_dead_cap'],kicker.contract.annual_salary)
        self.assertEqual(preview['total_obligation'],kicker.contract.annual_salary*kicker.contract.years)
        self.assertEqual(original,context)

    def test_legacy_and_non_management_profiles(self):
        context=lineup_context((),1234,22,rebuild_team='seattle')
        players=dict(context)['seattle']
        p=next(p for p in players if p.position=='WR')
        players=(*players,replace(p,id='extra-receiver'))
        preview=release_preview(players,p,'seattle',1,1234,context)
        self.assertTrue(preview['allowed'])
        self.assertEqual(preview['dead_cap_schedule'],[])
        self.assertEqual(preview['cap_space_change'],p.contract.annual_salary)
        profile=career_action('seattle',CareerRequest(action='profile',**self.request))
        self.assertTrue(all('release_preview' not in p for p in profile['roster']))
        scout=career_action('seattle',CareerRequest(action='camp',view_team='miami',**self.request))
        self.assertTrue(all('release_preview' not in p for p in scout['profile']['roster']))
