#include "benchmark/bench.hpp"

#include "board/state.hpp"
#include "search/search.hpp"
#include "transposition_table/transposition_table.hpp"

#include <chrono>
#include <memory>

namespace atropos::benchmark {

std::vector<BenchPosition> default_positions() {
  return {
      {"startpos", std::string(board::Position::StartFen)},
      {"kiwipete", "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"},
      {"endgame_rooks", "8/8/8/3k4/8/3K4/3R4/7r w - - 0 1"},
      {"promotion_race", "4k3/P7/8/8/8/8/7p/4K3 w - - 0 1"},
      {"tactical_capture", "4k3/8/8/8/8/8/6q1/4K1R1 w - - 0 1"},
  };
}

BenchResult run(int depth) {
  BenchResult result;
  result.depth = depth < 0 ? 0 : depth;
  const auto positions = default_positions();
  result.positions = static_cast<int>(positions.size());
  auto table = std::make_shared<tt::TranspositionTable>(16);

  const auto started = std::chrono::steady_clock::now();
  for (const auto &bench_position : positions) {
    const auto position = board::Position::from_fen(bench_position.fen);
    if (!position.has_value()) {
      continue;
    }
    search::SearchLimits limits;
    limits.depth = result.depth;
    limits.transposition_table = table;
    const auto search_result = search::search_iterative(*position, limits, {});
    result.nodes += search_result.nodes;
    result.tt_hits += search_result.tt_hits;
  }
  const auto elapsed = std::chrono::steady_clock::now() - started;
  result.elapsed_ms =
      static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::milliseconds>(elapsed).count());
  return result;
}

} // namespace atropos::benchmark
