import math
import unittest

from tests.fixtures.landmarks import stable_pointing_hand, tracking_lost_hand


class FeatureNormalizerTests(unittest.TestCase):
    def test_normalizes_stable_hand_frame_to_feature_frame(self) -> None:
        from touchless_control.features import FeatureNormalizer

        hand_frame = stable_pointing_hand(timestamp_ms=200)
        features = FeatureNormalizer().to_features(hand_frame)

        self.assertEqual(features.timestamp_ms, 200)
        self.assertTrue(features.hand_present)
        self.assertFalse(features.tracking_lost)
        self.assertEqual(features.index_tip_norm, hand_frame.landmarks_img[8][:2])
        self.assertEqual(features.thumb_tip_norm, hand_frame.landmarks_img[4][:2])
        self.assertEqual(features.middle_tip_norm, hand_frame.landmarks_img[12][:2])
        self.assertGreater(features.palm_scale, 0)

    def test_computes_pinch_ratio_against_palm_scale(self) -> None:
        from touchless_control.features import FeatureNormalizer

        hand_frame = stable_pointing_hand(timestamp_ms=1)
        features = FeatureNormalizer().to_features(hand_frame)
        thumb = hand_frame.landmarks_img[4]
        index = hand_frame.landmarks_img[8]
        wrist = hand_frame.landmarks_img[0]
        middle_mcp = hand_frame.landmarks_img[9]
        pinch_distance = math.dist(thumb[:2], index[:2])
        palm_scale = math.dist(wrist[:2], middle_mcp[:2])

        self.assertAlmostEqual(features.pinch_ratio, pinch_distance / palm_scale)

    def test_low_confidence_frame_enters_tracking_lost_feature_state(self) -> None:
        from touchless_control.features import FeatureNormalizer

        features = FeatureNormalizer().to_features(tracking_lost_hand(timestamp_ms=9))

        self.assertFalse(features.hand_present)
        self.assertTrue(features.tracking_lost)
        self.assertLess(features.stability_score, 0.5)


if __name__ == "__main__":
    unittest.main()
