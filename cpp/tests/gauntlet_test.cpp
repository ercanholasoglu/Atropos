#include "test.hpp"
#include "strength/gauntlet.hpp"

TEST_CASE("match score summary computes score rate and Elo difference") {
  const auto score = atropos::strength::summarize_match_score(10, 5, 5);

  REQUIRE_EQ(score.games, 20);
  REQUIRE_EQ(score.wins, 10);
  REQUIRE_EQ(score.losses, 5);
  REQUIRE_EQ(score.draws, 5);
  REQUIRE(score.score_rate > 0.62);
  REQUIRE(score.elo_difference > 80);
}

TEST_CASE("cutechess score line parser reads win loss draw totals") {
  const auto parsed =
      atropos::strength::parse_cutechess_score_line("Score of Atropos vs Baseline: 10 - 5 - 5  [0.625] 20");

  REQUIRE(parsed.has_value());
  REQUIRE_EQ(parsed->games, 20);
  REQUIRE_EQ(parsed->wins, 10);
  REQUIRE_EQ(parsed->losses, 5);
  REQUIRE_EQ(parsed->draws, 5);
}

TEST_CASE("cutechess parser rejects malformed score lines") {
  REQUIRE(!atropos::strength::parse_cutechess_score_line("Finished match without score").has_value());
  REQUIRE(!atropos::strength::parse_cutechess_score_line("Score of A vs B: 1 - nope - 3").has_value());
}
