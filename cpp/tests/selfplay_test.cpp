#include "test.hpp"
#include "strength/selfplay.hpp"

TEST_CASE("elo difference from score is centered at equal score") {
  REQUIRE_EQ(atropos::strength::elo_difference_from_score(0.5), 0);
  REQUIRE(atropos::strength::elo_difference_from_score(0.75) > 0);
  REQUIRE(atropos::strength::elo_difference_from_score(0.25) < 0);
}

TEST_CASE("self-play runs deterministic short games") {
  atropos::strength::SelfPlayConfig config;
  config.games = 1;
  config.depth = 0;
  config.max_plies = 4;

  const auto result = atropos::strength::run_self_play(config);

  REQUIRE_EQ(result.games, 1);
  REQUIRE_EQ(result.depth, 0);
  REQUIRE_EQ(result.max_plies, 4);
  REQUIRE(result.plies <= 4);
  REQUIRE_EQ(result.white_wins + result.black_wins + result.draws, 1);
}
