#include "search/search.hpp"

#include "evaluation/evaluate.hpp"
#include "movegen/movegen.hpp"

#include <algorithm>
#include <array>
#include <chrono>
#include <limits>
#include <vector>

namespace atropos::search {
namespace {

constexpr int Infinity = 1'000'000;
constexpr int MateScore = 900'000;
constexpr int MaxQuiescencePly = 8;
constexpr int MaxKillerPly = 128;
constexpr int MaxMoveBufferPly = 256;

struct SearchContext {
  SearchLimits limits;
  std::uint64_t nodes = 0;
  std::uint64_t tt_hits = 0;
  std::uint64_t killer_updates = 0;
  std::uint64_t history_updates = 0;
  bool stopped = false;
  std::array<std::array<std::optional<board::Move>, 2>, MaxKillerPly> killers{};
  std::array<int, 64 * 64> history{};
  std::array<std::vector<board::Move>, MaxMoveBufferPly> legal_move_buffers{};
  std::array<std::vector<board::Move>, MaxMoveBufferPly> pseudo_move_buffers{};
};

[[nodiscard]] std::size_t move_buffer_index(int ply) {
  if (ply <= 0) {
    return 0;
  }
  return static_cast<std::size_t>(std::min(ply, MaxMoveBufferPly - 1));
}

void generate_legal_moves(SearchContext &context, const board::Position &position, int ply,
                          std::vector<board::Move> *&moves) {
  const auto index = move_buffer_index(ply);
  auto &legal = context.legal_move_buffers[index];
  auto &pseudo = context.pseudo_move_buffers[index];
  movegen::generate_legal_moves_into(position, legal, pseudo);
  moves = &legal;
}

[[nodiscard]] bool should_stop(SearchContext &context) {
  if (context.limits.stop != nullptr && context.limits.stop->load(std::memory_order_relaxed)) {
    context.stopped = true;
    return true;
  }
  if (context.limits.nodes.has_value() && context.nodes >= *context.limits.nodes) {
    context.stopped = true;
    return true;
  }
  if (context.limits.deadline.has_value() && std::chrono::steady_clock::now() >= *context.limits.deadline) {
    context.stopped = true;
    return true;
  }
  return false;
}

void count_node(SearchContext &context) {
  ++context.nodes;
  if (context.limits.nodes.has_value() && context.nodes >= *context.limits.nodes) {
    context.stopped = true;
  }
}

[[nodiscard]] std::optional<board::Piece> captured_piece(const board::Position &position,
                                                         board::Move move) {
  if (move.flag == board::MoveFlag::EnPassant) {
    return board::Piece{board::opposite(position.side_to_move()), board::PieceType::Pawn};
  }
  return position.piece_at(move.to);
}

[[nodiscard]] bool is_tactical_move(const board::Position &position, board::Move move) {
  return captured_piece(position, move).has_value() || move.promotion.has_value();
}

[[nodiscard]] int history_index(board::Move move) { return (move.from * 64) + move.to; }

[[nodiscard]] bool is_killer(const SearchContext &context, int ply, board::Move move) {
  if (ply < 0 || ply >= MaxKillerPly) {
    return false;
  }
  const auto &slot = context.killers[static_cast<std::size_t>(ply)];
  return (slot[0].has_value() && slot[0] == move) || (slot[1].has_value() && slot[1] == move);
}

void record_quiet_cutoff(SearchContext &context, int ply, int depth, board::Move move) {
  if (ply >= 0 && ply < MaxKillerPly) {
    auto &slot = context.killers[static_cast<std::size_t>(ply)];
    if (!slot[0].has_value() || slot[0] != move) {
      slot[1] = slot[0];
      slot[0] = move;
      ++context.killer_updates;
    }
  }
  auto &history = context.history[static_cast<std::size_t>(history_index(move))];
  history += depth * depth;
  ++context.history_updates;
}

[[nodiscard]] int move_order_score(const board::Position &position, board::Move move,
                                   const SearchContext *context = nullptr, int ply = 0) {
  int score = 0;
  if (move.promotion.has_value()) {
    score += 10'000 + evaluation::piece_value(*move.promotion);
  }

  const auto victim = captured_piece(position, move);
  const auto attacker = position.piece_at(move.from);
  if (victim.has_value()) {
    score += 20'000 + (10 * evaluation::piece_value(victim->type));
    if (attacker.has_value()) {
      score -= evaluation::piece_value(attacker->type);
    }
  }

  if (move.flag == board::MoveFlag::KingCastle || move.flag == board::MoveFlag::QueenCastle) {
    score += 50;
  }
  if (context != nullptr && !is_tactical_move(position, move)) {
    if (is_killer(*context, ply, move)) {
      score += 15'000;
    }
    score += context->history[static_cast<std::size_t>(history_index(move))];
  }
  return score;
}

void order_moves(const board::Position &position, std::vector<board::Move> &moves,
                 std::optional<board::Move> tt_move = std::nullopt,
                 const SearchContext *context = nullptr, int ply = 0) {
  std::stable_sort(moves.begin(), moves.end(), [&position, tt_move, context, ply](board::Move left,
                                                                                  board::Move right) {
    if (tt_move.has_value()) {
      if (left == *tt_move) {
        return true;
      }
      if (right == *tt_move) {
        return false;
      }
    }
    return move_order_score(position, left, context, ply) > move_order_score(position, right, context, ply);
  });
}

[[nodiscard]] int terminal_score(const board::Position &position, int ply) {
  if (position.in_check(position.side_to_move())) {
    return -MateScore + ply;
  }
  return 0;
}

[[nodiscard]] int quiescence(board::Position &position, int ply, int alpha, int beta,
                             SearchContext &context) {
  count_node(context);
  if (should_stop(context)) {
    return evaluation::evaluate(position);
  }

  std::vector<board::Move> *moves = nullptr;
  generate_legal_moves(context, position, ply, moves);
  if (moves->empty()) {
    return terminal_score(position, ply);
  }
  order_moves(position, *moves);

  if (position.in_check(position.side_to_move())) {
    int best_score = -Infinity;
    for (const auto move : *moves) {
      const auto undo = position.make_move(move);
      if (!undo.has_value()) {
        continue;
      }
      const int score = -quiescence(position, ply + 1, -beta, -alpha, context);
      position.unmake_move(*undo);
      if (context.stopped) {
        return score;
      }

      best_score = std::max(best_score, score);
      alpha = std::max(alpha, score);
      if (alpha >= beta) {
        break;
      }
    }
    return best_score;
  }

  int stand_pat = evaluation::evaluate(position);
  if (stand_pat >= beta || ply >= MaxQuiescencePly) {
    return stand_pat;
  }
  alpha = std::max(alpha, stand_pat);

  for (const auto move : *moves) {
    if (!is_tactical_move(position, move)) {
      continue;
    }

    const auto undo = position.make_move(move);
    if (!undo.has_value()) {
      continue;
    }
    const int score = -quiescence(position, ply + 1, -beta, -alpha, context);
    position.unmake_move(*undo);
    if (context.stopped) {
      return score;
    }

    if (score >= beta) {
      return score;
    }
    alpha = std::max(alpha, score);
  }
  return alpha;
}

[[nodiscard]] int negamax(board::Position &position, int depth, int ply, int alpha, int beta,
                          SearchContext &context, std::vector<board::Move> &pv) {
  if (depth <= 0) {
    pv.clear();
    return quiescence(position, ply, alpha, beta, context);
  }

  count_node(context);
  if (should_stop(context)) {
    pv.clear();
    return evaluation::evaluate(position);
  }

  const int original_alpha = alpha;
  const auto key = position.hash();
  std::optional<board::Move> tt_move;
  if (context.limits.transposition_table != nullptr) {
    const auto entry = context.limits.transposition_table->probe(key);
    if (entry.has_value()) {
      tt_move = entry->best_move;
      if (entry->depth >= depth) {
        ++context.tt_hits;
        if (entry->bound == tt::Bound::Exact) {
          pv.clear();
          if (entry->best_move.has_value()) {
            pv.push_back(*entry->best_move);
          }
          return entry->score;
        }
        if (entry->bound == tt::Bound::Lower) {
          alpha = std::max(alpha, entry->score);
        } else if (entry->bound == tt::Bound::Upper) {
          beta = std::min(beta, entry->score);
        }
        if (alpha >= beta) {
          pv.clear();
          if (entry->best_move.has_value()) {
            pv.push_back(*entry->best_move);
          }
          return entry->score;
        }
      }
    }
  }

  std::vector<board::Move> *moves = nullptr;
  generate_legal_moves(context, position, ply, moves);
  if (moves->empty()) {
    pv.clear();
    return terminal_score(position, ply);
  }
  order_moves(position, *moves, tt_move, &context, ply);

  int best_score = -Infinity;
  std::vector<board::Move> best_line;
  std::optional<board::Move> best_move;

  for (const auto move : *moves) {
    const auto undo = position.make_move(move);
    if (!undo.has_value()) {
      continue;
    }

    std::vector<board::Move> child_pv;
    const int score = -negamax(position, depth - 1, ply + 1, -beta, -alpha, context, child_pv);
    position.unmake_move(*undo);
    if (context.stopped) {
      return score;
    }

    if (score > best_score) {
      best_score = score;
      best_move = move;
      best_line.clear();
      best_line.push_back(move);
      best_line.insert(best_line.end(), child_pv.begin(), child_pv.end());
    }
    alpha = std::max(alpha, score);
    if (alpha >= beta) {
      if (!is_tactical_move(position, move)) {
        record_quiet_cutoff(context, ply, depth, move);
      }
      break;
    }
  }

  pv = std::move(best_line);
  if (!context.stopped && context.limits.transposition_table != nullptr) {
    tt::Bound bound = tt::Bound::Exact;
    if (best_score <= original_alpha) {
      bound = tt::Bound::Upper;
    } else if (best_score >= beta) {
      bound = tt::Bound::Lower;
    }
    context.limits.transposition_table->store(tt::Entry{key, depth, best_score, bound, best_move});
  }
  return best_score;
}

} // namespace

SearchResult search(board::Position position, SearchLimits limits) {
  SearchResult result;
  result.depth = std::max(0, limits.depth);
  SearchContext context{limits};

  std::vector<board::Move> *moves = nullptr;
  generate_legal_moves(context, position, 0, moves);
  if (moves->empty()) {
    result.score = terminal_score(position, 0);
    result.nodes = 1;
    return result;
  }
  std::optional<board::Move> tt_move;
  if (limits.transposition_table != nullptr) {
    const auto entry = limits.transposition_table->probe(position.hash());
    if (entry.has_value()) {
      tt_move = entry->best_move;
    }
  }
  order_moves(position, *moves, tt_move, &context, 0);

  if (result.depth == 0) {
    const auto fallback = moves->front();
    result.score = quiescence(position, 0, -Infinity, Infinity, context);
    result.nodes = context.nodes;
    result.stopped = context.stopped;
    result.best_move = fallback;
    result.principal_variation.push_back(fallback);
    return result;
  }

  int alpha = -Infinity;
  int best_score = evaluation::evaluate(position);
  result.score = best_score;
  result.best_move = moves->front();
  result.principal_variation.push_back(moves->front());
  bool searched_any = false;

  for (const auto move : *moves) {
    if (should_stop(context)) {
      break;
    }

    const auto undo = position.make_move(move);
    if (!undo.has_value()) {
      continue;
    }

    std::vector<board::Move> child_pv;
    const int score =
        -negamax(position, result.depth - 1, 1, -Infinity, -alpha, context, child_pv);
    position.unmake_move(*undo);

    if (!searched_any || score > best_score) {
      best_score = score;
      result.best_move = move;
      result.principal_variation.clear();
      result.principal_variation.push_back(move);
      result.principal_variation.insert(result.principal_variation.end(), child_pv.begin(),
                                        child_pv.end());
    }
    searched_any = true;
    if (context.stopped) {
      break;
    }
    alpha = std::max(alpha, score);
  }

  result.score = best_score;
  result.nodes = context.nodes;
  result.tt_hits = context.tt_hits;
  result.killer_updates = context.killer_updates;
  result.history_updates = context.history_updates;
  result.stopped = context.stopped;
  if (!context.stopped && limits.transposition_table != nullptr) {
    limits.transposition_table->store(tt::Entry{position.hash(), result.depth, result.score,
                                                tt::Bound::Exact, result.best_move});
  }
  return result;
}

SearchResult search_depth(board::Position position, int depth) {
  SearchLimits limits;
  limits.depth = std::max(0, depth);
  return search(std::move(position), limits);
}

SearchResult search_iterative(board::Position position, SearchLimits limits,
                              const std::function<void(const SearchResult &)> &on_depth) {
  const int target_depth = std::max(0, limits.depth);
  if (target_depth == 0) {
    auto result = search(std::move(position), limits);
    if (on_depth) {
      on_depth(result);
    }
    return result;
  }

  SearchResult best_result;
  std::uint64_t consumed_nodes = 0;
  for (int depth = 1; depth <= target_depth; ++depth) {
    SearchLimits depth_limits = limits;
    depth_limits.depth = depth;
    if (limits.nodes.has_value()) {
      if (consumed_nodes >= *limits.nodes) {
        best_result.stopped = true;
        break;
      }
      depth_limits.nodes = *limits.nodes - consumed_nodes;
    }

    auto current = search(position, depth_limits);
    consumed_nodes += current.nodes;
    current.nodes = consumed_nodes;
    current.tt_hits += best_result.tt_hits;
    current.killer_updates += best_result.killer_updates;
    current.history_updates += best_result.history_updates;
    if (current.stopped) {
      current.depth = depth;
      if (best_result.best_move.has_value()) {
        current.best_move = best_result.best_move;
        current.score = best_result.score;
        current.principal_variation = best_result.principal_variation;
      }
      if (on_depth) {
        on_depth(current);
      }
      return current;
    }

    best_result = current;
    best_result.nodes = consumed_nodes;
    if (on_depth) {
      on_depth(best_result);
    }
  }

  return best_result;
}

} // namespace atropos::search
