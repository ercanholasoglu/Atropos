#pragma once

#include <cstdint>

namespace atropos::strength {

struct SelfPlayConfig {
  int games = 2;
  int depth = 1;
  int max_plies = 160;
};

struct SelfPlayResult {
  int games = 0;
  int depth = 0;
  int max_plies = 0;
  int white_wins = 0;
  int black_wins = 0;
  int draws = 0;
  int plies = 0;
  std::uint64_t nodes = 0;
  double white_score_rate = 0.5;
  int white_elo_difference = 0;
};

[[nodiscard]] int elo_difference_from_score(double score_rate);
[[nodiscard]] SelfPlayResult run_self_play(SelfPlayConfig config);

} // namespace atropos::strength
