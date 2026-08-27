#include "strength/selfplay.hpp"

#include "benchmark/bench.hpp"
#include "movegen/movegen.hpp"
#include "search/search.hpp"
#include "transposition_table/transposition_table.hpp"

#include <algorithm>
#include <cmath>
#include <memory>

namespace atropos::strength {
namespace {

enum class GameOutcome { WhiteWin, BlackWin, Draw };

struct GameResult {
  GameOutcome outcome = GameOutcome::Draw;
  int plies = 0;
  std::uint64_t nodes = 0;
};

[[nodiscard]] GameResult play_game(board::Position position, int depth, int max_plies) {
  GameResult result;
  auto table = std::make_shared<tt::TranspositionTable>(16);

  for (int ply = 0; ply < max_plies; ++ply) {
    const auto legal = movegen::generate_legal_moves(position);
    if (legal.empty()) {
      if (position.in_check(position.side_to_move())) {
        result.outcome = position.side_to_move() == board::Color::White ? GameOutcome::BlackWin
                                                                        : GameOutcome::WhiteWin;
      }
      return result;
    }
    if (position.halfmove_clock() >= 100 || position.repetition_count() >= 3) {
      return result;
    }

    search::SearchLimits limits;
    limits.depth = depth;
    limits.transposition_table = table;
    const auto searched = search::search_iterative(position, limits, {});
    result.nodes += searched.nodes;

    const auto move = searched.best_move.value_or(legal.front());
    const auto undo = position.make_move(move);
    if (!undo.has_value()) {
      return result;
    }
    result.plies = ply + 1;
  }

  return result;
}

} // namespace

int elo_difference_from_score(double score_rate) {
  const double clamped = std::clamp(score_rate, 0.01, 0.99);
  return static_cast<int>(std::lround(400.0 * std::log10(clamped / (1.0 - clamped))));
}

SelfPlayResult run_self_play(SelfPlayConfig config) {
  config.games = std::max(1, config.games);
  config.depth = std::max(0, config.depth);
  config.max_plies = std::max(1, config.max_plies);

  SelfPlayResult result;
  result.games = config.games;
  result.depth = config.depth;
  result.max_plies = config.max_plies;

  const auto starts = benchmark::default_positions();
  for (int game = 0; game < config.games; ++game) {
    const auto &start = starts[static_cast<std::size_t>(game) % starts.size()];
    const auto position = board::Position::from_fen(start.fen);
    if (!position.has_value()) {
      ++result.draws;
      continue;
    }

    const auto game_result = play_game(*position, config.depth, config.max_plies);
    result.plies += game_result.plies;
    result.nodes += game_result.nodes;
    switch (game_result.outcome) {
    case GameOutcome::WhiteWin:
      ++result.white_wins;
      break;
    case GameOutcome::BlackWin:
      ++result.black_wins;
      break;
    case GameOutcome::Draw:
      ++result.draws;
      break;
    }
  }

  const double white_points =
      static_cast<double>(result.white_wins) + (0.5 * static_cast<double>(result.draws));
  result.white_score_rate = white_points / static_cast<double>(result.games);
  result.white_elo_difference = elo_difference_from_score(result.white_score_rate);
  return result;
}

} // namespace atropos::strength
