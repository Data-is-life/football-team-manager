from dataclasses import replace
import unittest

from app.draft import draft_class, player_payload
from app.main import team_profile, CareerRequest, career_action
from app.ratings import rating_payload
from app.simulation import roster_for


class BasicRatingTests(unittest.TestCase):
    def test_youth_headroom_bounds_and_age_bands(self):
        sample = roster_for('seattle', 1234)['QB1']
        for age in (21, 24, 25, 29, 30, 36, 45):
            for current in (1, 65, 90, 99):
                player = replace(sample, age=age, rating=current)
                values = rating_payload(player)
                self.assertEqual(values['current_rating'], current)
                self.assertGreaterEqual(values['potential_rating'], current)
                self.assertLessEqual(values['potential_rating'], 99)
                if age >= 30:
                    self.assertEqual(values['potential_rating'], current)
                elif age <= 24 and current <= 81:
                    self.assertGreaterEqual(values['potential_rating'] - current, 6)
                    self.assertLessEqual(values['potential_rating'] - current, 18)
                else:
                    maximum = 18 if age <= 24 else 2 * (30 - age)
                    self.assertLessEqual(values['potential_rating'] - current, maximum)

    def test_potential_is_stable_across_depth_changes_and_identity_is_unchanged(self):
        player = draft_class(1, 1234)[0]
        self.assertEqual(rating_payload(player), rating_payload(player))
        self.assertEqual(rating_payload(player), rating_payload(replace(player, depth=8)))
        before = (player.id, player.rating, player.attributes, player.age, player.experience)
        player_payload(player)
        self.assertEqual(before, (player.id, player.rating, player.attributes, player.age, player.experience))

    def test_profiles_rookies_and_career_profiles_share_the_basic_ratings(self):
        for seed in (0, 1234):
            profile = team_profile('seattle', seed)
            career = career_action('seattle', CareerRequest(action='profile', run_seed=seed))
            self.assertEqual(profile, career)
            for player in roster_for('seattle', seed).values():
                api = next(p for p in profile['roster'] if p['id'] == player.id)
                self.assertEqual(api['rating'], player.rating)
                for key, value in rating_payload(player).items():
                    self.assertEqual(api[key], value)
            for player in draft_class(1, seed):
                api = player_payload(player)
                self.assertEqual(api['current_rating'], player.rating)
                self.assertGreaterEqual(api['potential_rating'], player.rating)


if __name__ == '__main__':
    unittest.main()
