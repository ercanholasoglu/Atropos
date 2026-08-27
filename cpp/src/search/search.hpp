#pragma once

#include "board/state.hpp"
#include "transposition_table/transposition_table.hpp"

#include <chrono>
#include <atomic>
#include <cstdint>
#include <functional>
#include <memory>
#include <optional>
#include <vector>

namespace atropos::search {

struct SearchResult {
  std::optional<board::Move> best_move;
  int score = 0;
  int depth = 0;
  std::uint64_t nodes = 0;
  std::uint64_t tt_hits = 0;
  std::uint64_t killer_updates = 0;
  std::uint64_t history_updates = 0;
  bool stopped = false;
  std::vector<board::Move> principal_variation;
};

struct SearchLimits {
  int depth = 1;
  std::optional<std::uint64_t> nodes;
  std::optional<std::chrono::steady_clock::time_point> deadline;
  std::shared_ptr<std::atomic_bool> stop;
  std::shared_ptr<tt::TranspositionTable> transposition_table;
};

[[nodiscard]] SearchResult search_depth(board::Position position, int depth);
[[nodiscard]] SearchResult search(board::Position position, SearchLimits limits);
[[nodiscard]] SearchResult search_iterative(board::Position position, SearchLimits limits,
                                            const std::function<void(const SearchResult &)> &on_depth);

} // namespace atropos::search
