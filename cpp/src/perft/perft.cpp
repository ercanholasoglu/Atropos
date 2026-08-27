#include "perft/perft.hpp"

#include "movegen/movegen.hpp"

namespace atropos::perft {

std::uint64_t count_nodes(board::Position &position, int depth) {
  if (depth <= 0) {
    return 1;
  }

  const auto moves = movegen::generate_legal_moves(position);
  if (depth == 1) {
    return moves.size();
  }

  std::uint64_t nodes = 0;
  for (const auto move : moves) {
    const auto undo = position.make_move(move);
    if (!undo.has_value()) {
      continue;
    }
    nodes += count_nodes(position, depth - 1);
    position.unmake_move(*undo);
  }
  return nodes;
}

std::vector<DivideEntry> divide(board::Position &position, int depth) {
  std::vector<DivideEntry> entries;
  if (depth <= 0) {
    return entries;
  }

  const auto moves = movegen::generate_legal_moves(position);
  entries.reserve(moves.size());
  for (const auto move : moves) {
    const auto undo = position.make_move(move);
    if (!undo.has_value()) {
      continue;
    }
    entries.push_back(DivideEntry{move, count_nodes(position, depth - 1)});
    position.unmake_move(*undo);
  }
  return entries;
}

} // namespace atropos::perft
