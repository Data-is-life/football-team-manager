from dataclasses import replace
from unittest import TestCase
from app.development import DevelopmentState
from app.draft import build_draft, cpu_pick, draft_class, draft_value
from app.lineups import lineup_context
from app.simulation import roster_for


class DraftValueTests(TestCase):
    def setUp(self):
        self.context=lineup_context((),1234,30)
        self.roster=list(dict(self.context)['seattle'])
        self.template=self.roster[0]

    def prospect(self,position,current,potential,identity):
        player=replace(self.template,id=identity,position=position,rating=current,contract=None,rookie_offer=None)
        states=dict(self.context.development);states[identity]=DevelopmentState(potential,current)
        self.context=replace(self.context,development=tuple(sorted(states.items())))
        return player

    def room(self,position,rating):
        self.roster=[replace(p,rating=rating) if p.position==position else p for p in self.roster]

    def pick(self,*players):
        return cpu_pick(players,self.roster,{},True,context=self.context)

    def test_requested_qb_outranks_higher_rated_ol_without_hard_position_tiers(self):
        qb=self.prospect('QB',75,90,'qb')
        ol=self.prospect('OL',80,95,'ol')
        self.assertGreater(draft_value(qb),draft_value(ol))
        self.assertGreater(draft_value(replace(ol,rating=95)),draft_value(qb))

    def test_strong_qb_and_weak_backup_do_not_hide_line_need(self):
        self.room('OL',50)
        qbs=sorted((p for p in self.roster if p.position=='QB'),key=lambda p:p.id)
        self.roster=[replace(p,rating=95 if p.id==qbs[0].id else 40) if p.position=='QB' else p for p in self.roster]
        qb=self.prospect('QB',85,95,'qb')
        ol=self.prospect('OL',78,85,'ol')
        before=tuple(self.roster)
        self.assertEqual(self.pick(qb,ol),ol)
        self.assertEqual(tuple(self.roster),before)
        self.assertEqual(self.pick(ol,qb),ol)

    def test_weak_qb_takes_priority_over_already_strong_line(self):
        self.room('QB',50);self.room('OL',90)
        qb=self.prospect('QB',75,90,'qb')
        ol=self.prospect('OL',80,95,'ol')
        self.assertEqual(self.pick(qb,ol),qb)

    def test_receiver_need_overrides_redundant_qb_and_kicker(self):
        self.room('QB',95);self.room('WR',50);self.room('K',60)
        qb=self.prospect('QB',87,97,'qb')
        wr=self.prospect('WR',78,88,'wr')
        kicker=self.prospect('K',85,95,'k')
        self.assertEqual(self.pick(qb,wr,kicker),wr)

    def test_average_breaks_equal_current_position_value_ties(self):
        low=self.prospect('RB',75,80,'low')
        high=self.prospect('RB',75,95,'high')
        self.assertEqual(self.pick(low,high),high)
        self.assertEqual(self.pick(high,low),high)

    def test_drafted_starter_reduces_need_for_another_qb(self):
        self.room('QB',50);self.room('OL',60)
        first=self.prospect('QB',85,95,'first')
        second=self.prospect('QB',80,90,'second')
        ol=self.prospect('OL',78,85,'ol')
        self.roster.append(first)
        self.assertEqual(cpu_pick((second,ol),self.roster,{'QB':1},True,context=self.context),ol)

    def test_versioned_manual_replay_and_prospect_identity(self):
        for rules in (29,30):
            with self.subTest(rules=rules):
                context=lineup_context((),1234,rules)
                original=draft_class(1,1234)
                result,players=build_draft('seattle',1,1234,roster_context=context,auto_pick=True,draft_rounds=6)
                replay,replayed=build_draft('seattle',1,1234,tuple(result['manual_picks']),roster_context=context,draft_rounds=6)
                self.assertEqual((result,players),(replay,replayed))
                self.assertEqual(draft_class(1,1234),original)
