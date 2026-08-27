#include "test.hpp"
#include "board/state.hpp"
#include "perft/perft.hpp"

#include <array>
#include <cstdint>
#include <fstream>
#include <sstream>
#include <string>

namespace {

struct PerftCase {
  std::string name;
  std::string fen;
  std::array<std::uint64_t, 4> expected{};
};

[[nodiscard]] std::uint64_t parse_uint64(const std::string &text) {
  std::istringstream input(text);
  std::uint64_t value = 0;
  input >> value;
  return value;
}

[[nodiscard]] PerftCase parse_case(const std::string &line) {
  std::istringstream row(line);
  PerftCase result;
  std::string value;

  std::getline(row, result.name, '|');
  std::getline(row, result.fen, '|');
  for (auto &expected : result.expected) {
    std::getline(row, value, '|');
    expected = parse_uint64(value);
  }
  return result;
}

} // namespace

TEST_CASE("perft fixture suite matches known node counts through depth three") {
  std::ifstream input("tests/fixtures/phase2/perft.epd");
  REQUIRE(input.good());

  std::string line;
  int checked = 0;
  while (std::getline(input, line)) {
    if (line.empty() || line.front() == '#') {
      continue;
    }

    const auto test_case = parse_case(line);
    auto position = atropos::board::Position::from_fen(test_case.fen);
    REQUIRE(position.has_value());

    for (int depth = 1; depth <= 3; ++depth) {
      auto copy = *position;
      REQUIRE_EQ(atropos::perft::count_nodes(copy, depth),
                 test_case.expected[static_cast<std::size_t>(depth - 1)]);
    }
    ++checked;
  }

  REQUIRE_EQ(checked, 4);
}

TEST_CASE("perft divide sums to the full node count") {
  auto position = atropos::board::Position::startpos();
  const auto entries = atropos::perft::divide(position, 3);
  std::uint64_t total = 0;
  for (const auto &entry : entries) {
    total += entry.nodes;
  }

  auto copy = atropos::board::Position::startpos();
  REQUIRE_EQ(entries.size(), 20U);
  REQUIRE_EQ(total, atropos::perft::count_nodes(copy, 3));
}
