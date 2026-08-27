#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace atropos::benchmark {

struct BenchPosition {
  std::string name;
  std::string fen;
};

struct BenchResult {
  int depth = 0;
  int positions = 0;
  std::uint64_t nodes = 0;
  std::uint64_t tt_hits = 0;
  std::uint64_t elapsed_ms = 0;
};

[[nodiscard]] std::vector<BenchPosition> default_positions();
[[nodiscard]] BenchResult run(int depth);

} // namespace atropos::benchmark
