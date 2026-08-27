#include "strength/gauntlet.hpp"

#include "strength/selfplay.hpp"

#include <algorithm>
#include <charconv>
#include <string>

namespace atropos::strength {
namespace {

[[nodiscard]] std::string normalize_score_text(std::string_view text) {
  std::string normalized;
  normalized.reserve(text.size());
  for (const char ch : text) {
    if (ch >= '0' && ch <= '9') {
      normalized.push_back(ch);
    } else {
      normalized.push_back(' ');
    }
  }
  return normalized;
}

[[nodiscard]] std::optional<int> parse_int(std::string_view text) {
  int value = 0;
  const auto *begin = text.data();
  const auto *end = text.data() + text.size();
  const auto result = std::from_chars(begin, end, value);
  if (result.ec != std::errc{} || result.ptr != end) {
    return std::nullopt;
  }
  return value;
}

} // namespace

MatchScore summarize_match_score(int wins, int losses, int draws) {
  MatchScore score;
  score.wins = std::max(0, wins);
  score.losses = std::max(0, losses);
  score.draws = std::max(0, draws);
  score.games = score.wins + score.losses + score.draws;
  if (score.games == 0) {
    return score;
  }

  const double points = static_cast<double>(score.wins) + (0.5 * static_cast<double>(score.draws));
  score.score_rate = points / static_cast<double>(score.games);
  score.elo_difference = elo_difference_from_score(score.score_rate);
  return score;
}

std::optional<MatchScore> parse_cutechess_score_line(std::string_view line) {
  const auto marker = line.find(':');
  if (marker == std::string_view::npos) {
    return std::nullopt;
  }

  const auto normalized = normalize_score_text(line.substr(marker + 1));
  int values[3] = {0, 0, 0};
  int count = 0;
  std::size_t cursor = 0;
  while (cursor < normalized.size() && count < 3) {
    while (cursor < normalized.size() && normalized[cursor] == ' ') {
      ++cursor;
    }
    const std::size_t begin = cursor;
    while (cursor < normalized.size() && normalized[cursor] != ' ') {
      ++cursor;
    }
    if (begin == cursor) {
      continue;
    }
    const auto parsed = parse_int(std::string_view(normalized).substr(begin, cursor - begin));
    if (!parsed.has_value() || *parsed < 0) {
      return std::nullopt;
    }
    values[count] = *parsed;
    ++count;
  }

  if (count != 3) {
    return std::nullopt;
  }
  return summarize_match_score(values[0], values[1], values[2]);
}

} // namespace atropos::strength
