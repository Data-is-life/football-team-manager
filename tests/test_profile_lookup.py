"""Optimized roster reads must preserve player fields and salary decisions."""
from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch

from app.development import rating_view
from app.lineups import lineup_context, replace_lineup_rosters
from app.main import profile_payload
from app.player_contracts import cap_payroll, public_player_fields, contract_expired
from app.ratings import rating_payload


class ProfileLookupTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = lineup_context((), 1234, 28, rebuild_team='seattle')

    def test_development_lookup_matches_legacy_per_player_reads(self):
        context = self.context
        lookup = dict(context.development)
        for _, players in context:
            for player in players:
                self.assertEqual(rating_view(player, context, lookup),
                                 rating_view(player, context))
                self.assertEqual(rating_payload(player, context, lookup),
                                 rating_payload(player, context))
                self.assertEqual(public_player_fields(player, context,
                                 development_states=lookup),
                                 public_player_fields(player, context))

    def test_expired_player_profile_reuses_one_payroll_total_without_changing_offers(self):
        context = self.context
        owner = 'seattle'
        original = list(dict(context)[owner])
        expired = []
        for player in original[:3]:
            expired.append(replace(player, contract=replace(
                player.contract, signed_season=0, years=1)))
        players = tuple(expired + original[3:])
        rosters = tuple((team, players if team == owner else group)
                        for team, group in context)
        context = replace_lineup_rosters(context, rosters)
        self.assertTrue(all(contract_expired(player, context.season)
                            for player in expired))
        expected = [public_player_fields(player, context) for player in players]
        payroll = cap_payroll(players, context, owner=owner)

        with patch('app.main.cap_payroll', wraps=cap_payroll) as total:
            response = profile_payload(owner, players, 1234, context)
        self.assertEqual(total.call_count, 1)
        for old, actual in zip(expected, response['roster']):
            for key, value in old.items():
                self.assertEqual(actual[key], value)
        self.assertEqual(
            {player['id']: player['renewal_offer']['affordable']
             for player in response['roster'] if 'renewal_offer' in player},
            {player['id']: payroll + player['renewal_offer']['annual_salary']
             - player['contract']['annual_salary'] <= response['payroll']['cap']
             for player in response['roster'] if 'renewal_offer' in player})
