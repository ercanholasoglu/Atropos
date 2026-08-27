#include "test.hpp"
#include "board/state.hpp"
#include "board/types.hpp"
#include "search/search.hpp"

#include <fstream>
#include <sstream>
#include <string>

namespace {

struct TacticCase {
  std::string name;
  std::string fen;
  int depth = 0;
  std::string bestmove;
};

[[nodiscard]] TacticCase parse_case(const std::string &line) {
  std::istringstream row(line);
  TacticCase result;
  std::string depth;
  std::getline(row, result.name, '|');
  std::getline(row, result.fen, '|');
  std::getline(row, depth, '|');
  std::getline(row, result.bestmove, '|');
  result.depth = std::stoi(depth);
  return result;
}

} // namespace

TEST_CASE("tactical fixture suite returns expected best moves") {
  std::ifstream input("tests/fixtures/phase11/tactics.epd");
  REQUIRE(input.good());

  std::string line;
  int checked = 0;
  while (std::getline(input, line)) {
    if (line.empty() || line.front() == '#') {
      continue;
    }

    const auto test_case = parse_case(line);
    const auto position = atropos::board::Position::from_fen(test_case.fen);
    REQUIRE(position.has_value());

    const auto result = atropos::search::search_depth(*position, test_case.depth);
    const auto bestmove =
        result.best_move.has_value() ? atropos::board::move_to_uci(*result.best_move) : "0000";
    REQUIRE_EQ(bestmove, test_case.bestmove);
    ++checked;
  }

  REQUIRE_EQ(checked, 3);
}
