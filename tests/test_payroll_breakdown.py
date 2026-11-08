from dataclasses import replace
from unittest import TestCase
from app.lineups import lineup_context
from app.main import profile_payload, CareerRequest, career_action
from app.player_contracts import (PlayerContract, payroll_breakdown, payroll_payload, record_release)


class PayrollBreakdownTests(TestCase):
    def test_all_categories_reconcile_with_cap_and_filter_dead_charges(self):
        context=lineup_context((),1234,26,rebuild_team='seattle')
        players=list(dict(context)['seattle'])
        players[0]=replace(players[0],contract=PlayerContract(7_000_000,2,3,'young'))
        players[1]=replace(players[1],contract=PlayerContract(4_000_000,1,1,'veteran'))
        players[2]=replace(players[2],contract=None,rookie_offer=PlayerContract(3_150_000,2,3,'rookie',2,31))
        released=replace(players[0],id='released-player',name='Released Player',contract=PlayerContract(8_000_000,1,4,'veteran'))
        context=record_release(context,'seattle',released,2)
        context=record_release(context,'miami',replace(released,id='other-team'),2)
        context=record_release(context,'seattle',replace(released,id='old-charge',contract=PlayerContract(1_000_000,1,1,'veteran')),1)
        before=context
        data=payroll_breakdown(players,context,2,'seattle')['payroll_breakdown']
        categories={g['kind']:g for g in data['categories']}
        pay=payroll_payload(players,context,2,'seattle')['payroll']
        self.assertEqual(sum(g['total'] for g in data['categories']),pay['total'])
        for kind,key in [('signed','committed'),('rookie_holds','rookie_holds'),('expired_holds','expired_holds'),('dead_cap','dead_cap')]:
            self.assertEqual(categories[kind]['total'],pay[key])
            self.assertEqual(categories[kind]['total'],sum(p['amount'] for p in categories[kind]['players']))
            self.assertEqual([p['amount'] for p in categories[kind]['players']],sorted([p['amount'] for p in categories[kind]['players']],reverse=True))
        self.assertEqual(data['season'],2)
        self.assertEqual(data['floor_payroll'],pay['committed'])
        self.assertEqual(categories['dead_cap']['players'],[dict(player_id='released-player',name='Released Player',position=None,amount=8_000_000,expires_after_season=4)])
        self.assertEqual(data,payroll_breakdown(players,context,2,'seattle')['payroll_breakdown'])
        self.assertEqual(before,context)

    def test_legacy_rules_keep_accounting_and_pre_cap_profiles_hide_details(self):
        for rules in (15,16,19,20,22,23,24,25,26):
            context=lineup_context((),1234,rules,rebuild_team='seattle')
            players=dict(context)['seattle']
            result=payroll_breakdown(players,context,9,'seattle')
            if rules<16:
                self.assertEqual(result,{})
                self.assertNotIn('payroll_breakdown',profile_payload('seattle',players,1234,context))
                continue
            groups={g['kind']:g for g in result['payroll_breakdown']['categories']}
            pay=payroll_payload(players,context,9,'seattle')['payroll']
            self.assertEqual(sum(g['total'] for g in groups.values()),pay['total'])
            self.assertEqual(groups['dead_cap']['total'],0)
            self.assertEqual(groups['expired_holds']['total'],pay['total'] if rules>=20 else 0)
            self.assertEqual(result['payroll_breakdown']['floor_payroll'],pay.get('committed',pay['total']))

    def test_real_camp_release_and_scouting_use_the_viewed_owner_and_playing_season(self):
        request=dict(season=1,run_seed=1234,lineup_rules=26,rebuild_team='seattle',draft_rounds=6)
        draft=career_action('seattle',CareerRequest(action='draft',auto_draft=True,**request))
        request.update(manual_picks=draft['manual_picks'],training_camp=True)
        before=career_action('seattle',CareerRequest(action='camp',**request))
        profile=before['profile']
        self.assertEqual(profile['payroll_breakdown']['season'],2)
        player=next(p for p in profile['roster'] if p.get('contract',{}).get('status')=='active' and p['release_preview']['allowed'])
        request.update(dropped=[player['id']],roster_actions=[dict(kind='drop',player_id=player['id'])])
        after=career_action('seattle',CareerRequest(action='cuts',**request))['profile']
        dead=next(g for g in after['payroll_breakdown']['categories'] if g['kind']=='dead_cap')
        self.assertEqual(dead['total'],player['contract']['annual_salary'])
        self.assertEqual(dead['players'][0]['name'],player['name'])
        self.assertNotIn(player['id'],[p['id'] for p in after['roster']])
        scout=career_action('seattle',CareerRequest(action='camp',view_team='miami',**request))['profile']
        self.assertEqual(sum(g['total'] for g in scout['payroll_breakdown']['categories']),scout['payroll']['total'])
        self.assertTrue(all(p['player_id']!=player['id'] for g in scout['payroll_breakdown']['categories'] for p in g['players']))
