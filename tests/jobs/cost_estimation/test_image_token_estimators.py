import math
import pytest
from edsl.jobs.cost_estimation.image_token_estimators import (
    OpenAIImageEstimator,
    GoogleImageEstimator,
    AnthropicImageEstimator,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PATCH_MODEL = "gpt-4.1-mini"  # multiplier=1.62, budget=1536
TILE_MODEL = "gpt-4o"


# ---------------------------------------------------------------------------
# OpenAI patch-based — _patch_tokens
# ---------------------------------------------------------------------------


class TestPatchTokens:
    est = OpenAIImageEstimator()

    def test_normal_image_within_budget(self):
        # 512x512 → ceil(512/32)^2 = 16^2 = 256 patches ≤ 1536
        tokens = self.est.estimate(512, 512, PATCH_MODEL)
        assert tokens == round(256 * 1.62)

    def test_normal_image_over_budget_is_capped(self):
        # very large square → must shrink; result ≤ budget * multiplier
        tokens = self.est.estimate(4096, 4096, PATCH_MODEL)
        assert tokens <= round(1536 * 1.62)
        assert tokens > 0

    def test_extreme_aspect_ratio_tall_nonzero(self):
        # P1 regression: 1×49152 previously returned 0
        tokens = self.est.estimate(1, 49152, PATCH_MODEL)
        assert tokens > 0

    def test_extreme_aspect_ratio_wide_nonzero(self):
        # symmetric case: 49152×1
        tokens = self.est.estimate(49152, 1, PATCH_MODEL)
        assert tokens > 0

    def test_extreme_aspect_ratio_tall_uses_full_budget(self):
        # 1×49152: 1 patch wide is the minimum; tall dim fills the budget
        tokens = self.est.estimate(1, 49152, PATCH_MODEL)
        assert tokens == round(1536 * 1.62)

    def test_extreme_aspect_ratio_wide_uses_full_budget(self):
        tokens = self.est.estimate(49152, 1, PATCH_MODEL)
        assert tokens == round(1536 * 1.62)

    def test_moderately_narrow_image(self):
        # 16×2048 → ceil(16/32)=1, ceil(2048/32)=64 → 64 patches ≤ 1536
        tokens = self.est.estimate(16, 2048, PATCH_MODEL)
        assert tokens == round(64 * 1.62)

    def test_narrow_over_budget(self):
        # 16×65536 → original = 1 × 2048 = 2048 > 1536 → enters shrink path
        tokens = self.est.estimate(16, 65536, PATCH_MODEL)
        assert 0 < tokens <= round(1536 * 1.62)

    def test_symmetry(self):
        # rotating the image should give the same token count
        assert self.est.estimate(100, 800, PATCH_MODEL) == self.est.estimate(
            800, 100, PATCH_MODEL
        )

    def test_minimum_image(self):
        tokens = self.est.estimate(1, 1, PATCH_MODEL)
        assert tokens == round(1 * 1.62)


# ---------------------------------------------------------------------------
# OpenAI patch-based — breakdown consistency
# ---------------------------------------------------------------------------


class TestPatchBreakdown:
    est = OpenAIImageEstimator()

    def test_breakdown_total_matches_estimate_normal(self):
        w, h = 512, 512
        assert self.est.breakdown(w, h, PATCH_MODEL)["total"] == self.est.estimate(
            w, h, PATCH_MODEL
        )

    def test_breakdown_total_matches_estimate_extreme_tall(self):
        w, h = 1, 49152
        assert self.est.breakdown(w, h, PATCH_MODEL)["total"] == self.est.estimate(
            w, h, PATCH_MODEL
        )

    def test_breakdown_total_matches_estimate_extreme_wide(self):
        w, h = 49152, 1
        assert self.est.breakdown(w, h, PATCH_MODEL)["total"] == self.est.estimate(
            w, h, PATCH_MODEL
        )

    def test_breakdown_total_matches_estimate_large_square(self):
        w, h = 4096, 4096
        assert self.est.breakdown(w, h, PATCH_MODEL)["total"] == self.est.estimate(
            w, h, PATCH_MODEL
        )

    def test_breakdown_total_nonzero_extreme(self):
        result = self.est.breakdown(1, 49152, PATCH_MODEL)
        assert result["total"] > 0


# ---------------------------------------------------------------------------
# OpenAI tile-based
# ---------------------------------------------------------------------------


class TestTileTokens:
    est = OpenAIImageEstimator()

    def test_small_image(self):
        # 256x256 → fits in 2048 → short edge 256 → scale2 = 768/256 = 3
        # → 768x768 → ceil(768/512)^2 = 2^2 = 4 tiles → 85 + 170*4 = 765
        tokens = self.est.estimate(256, 256, TILE_MODEL)
        assert tokens == 85 + 170 * 4

    def test_large_image_downscaled(self):
        tokens = self.est.estimate(4096, 4096, TILE_MODEL)
        assert tokens > 0

    def test_symmetry(self):
        assert self.est.estimate(300, 900, TILE_MODEL) == self.est.estimate(
            900, 300, TILE_MODEL
        )

    def test_breakdown_matches_estimate(self):
        w, h = 1024, 768
        assert self.est.breakdown(w, h, TILE_MODEL)["total"] == self.est.estimate(
            w, h, TILE_MODEL
        )


# ---------------------------------------------------------------------------
# Google
# ---------------------------------------------------------------------------


class TestGoogleImageEstimator:
    est = GoogleImageEstimator()

    def test_small_image_flat_rate(self):
        assert self.est.estimate(100, 100) == 258

    def test_threshold_boundary(self):
        assert self.est.estimate(384, 384) == 258

    def test_just_over_threshold(self):
        tokens = self.est.estimate(385, 385)
        assert tokens > 258

    def test_larger_image(self):
        # 960x540 → crop_unit=floor(540/1.5)=360 → 3×2=6 tiles → 6*258=1548
        assert self.est.estimate(960, 540) == 1548

    def test_breakdown_matches_estimate(self):
        for w, h in [(100, 100), (960, 540), (1920, 1080)]:
            assert self.est.breakdown(w, h)["total"] == self.est.estimate(w, h)


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------


class TestAnthropicImageEstimator:
    est = AnthropicImageEstimator()

    def test_small_image(self):
        tokens = self.est.estimate(100, 100)
        assert tokens == round(100 * 100 / 750)

    def test_standard_cap(self):
        # enormous image → capped at 1568
        tokens = self.est.estimate(10000, 10000)
        assert tokens == 1568

    def test_long_edge_scaling(self):
        # 3136x1568 → long edge 3136 > 1568 → scale = 1568/3136 = 0.5
        # → 1568x784 → round(1568*784/750) = round(1638.5) = 1639 > 1568 → capped
        tokens = self.est.estimate(3136, 1568)
        assert tokens == 1568

    def test_high_res_model(self):
        model = "claude-opus-4-8"
        tokens = self.est.estimate(2576, 2576, model)
        assert tokens <= 4784
        assert tokens > 0

    def test_breakdown_matches_estimate(self):
        for w, h in [(100, 100), (1568, 1568), (3000, 2000)]:
            assert self.est.breakdown(w, h)["total"] == self.est.estimate(w, h)
