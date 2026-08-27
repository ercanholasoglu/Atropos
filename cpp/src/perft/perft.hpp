#pragma once

#include "board/state.hpp"

#include <cstdint>
#include <vector>

namespace atropos::perft {

struct DivideEntry {
  board::Move move;
  std::uint64_t nodes = 0;
};

[[nodiscard]] std::uint64_t count_nodes(board::Position &position, int depth);
[[nodiscard]] std::vector<DivideEntry> divide(board::Position &position, int depth);

} // namespace atropos::perft
