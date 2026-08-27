#include "test.hpp"
#include "benchmark/bench.hpp"

TEST_CASE("benchmark suite runs fixed positions") {
  const auto result = atropos::benchmark::run(2);

  REQUIRE_EQ(result.depth, 2);
  REQUIRE_EQ(result.positions, 5);
  REQUIRE(result.nodes > 0U);
}
