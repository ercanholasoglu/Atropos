#pragma once

#include <optional>
#include <string_view>

namespace atropos::strength {

struct MatchScore {
  int games = 0;
  int wins = 0;
  int losses = 0;
  int draws = 0;
  double score_rate = 0.5;
  int elo_difference = 0;
};

[[nodiscard]] MatchScore summarize_match_score(int wins, int losses, int draws);
[[nodiscard]] std::optional<MatchScore> parse_cutechess_score_line(std::string_view line);

} // namespace atropos::strength
