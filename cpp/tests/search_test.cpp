#include "test.hpp"
#include "board/types.hpp"
#include "movegen/movegen.hpp"
#include "search/search.hpp"

#include <algorithm>
#include <memory>
#include <vector>

namespace {

[[nodiscard]] bool is_legal_result(const atropos::board::Position &position,
                                   atropos::board::Move move) {
  const auto legal = atropos::movegen::generate_legal_moves(position);
  return std::find(legal.begin(), legal.end(), move) != legal.end();
}

} // namespace

TEST_CASE("depth search returns a legal best move") {
  const auto position = atropos::board::Position::startpos();
  const auto result = atropos::search::search_depth(position, 2);

  REQUIRE(result.best_move.has_value());
  REQUIRE(is_legal_result(position, *result.best_move));
  REQUIRE(result.nodes > 0U);
}

TEST_CASE("search captures a free queen at depth one") {
  const auto position =
      *atropos::board::Position::from_fen("4k3/8/8/8/8/8/6q1/4K1R1 w - - 0 1");
  const auto result = atropos::search::search_depth(position, 1);

  REQUIRE(result.best_move.has_value());
  REQUIRE_EQ(atropos::board::move_to_uci(*result.best_move), "g1g2");
  REQUIRE(result.score > 400);
}

TEST_CASE("depth zero search uses quiescence for immediate tactics") {
  const auto position =
      *atropos::board::Position::from_fen("4k3/8/8/8/8/8/6q1/4K1R1 w - - 0 1");
  const auto result = atropos::search::search_depth(position, 0);

  REQUIRE(result.best_move.has_value());
  REQUIRE_EQ(atropos::board::move_to_uci(*result.best_move), "g1g2");
  REQUIRE(result.score > 400);
  REQUIRE(result.nodes > 1U);
}

TEST_CASE("search honors a small node limit") {
  atropos::search::SearchLimits limits;
  limits.depth = 5;
  limits.nodes = 3;
  const auto result = atropos::search::search(atropos::board::Position::startpos(), limits);

  REQUIRE(result.best_move.has_value());
  REQUIRE(result.stopped);
  REQUIRE(result.nodes >= 3U);
}

TEST_CASE("iterative search reports every completed depth") {
  atropos::search::SearchLimits limits;
  limits.depth = 3;
  std::vector<int> depths;

  const auto result = atropos::search::search_iterative(
      atropos::board::Position::startpos(), limits,
      [&depths](const atropos::search::SearchResult &depth_result) {
        depths.push_back(depth_result.depth);
      });

  REQUIRE_EQ(depths.size(), 3U);
  REQUIRE_EQ(depths[0], 1);
  REQUIRE_EQ(depths[1], 2);
  REQUIRE_EQ(depths[2], 3);
  REQUIRE_EQ(result.depth, 3);
  REQUIRE(result.best_move.has_value());
}

TEST_CASE("search reuses stored transposition table entries") {
  auto table = std::make_shared<atropos::tt::TranspositionTable>(1);
  atropos::search::SearchLimits limits;
  limits.depth = 3;
  limits.transposition_table = table;

  const auto first = atropos::search::search(atropos::board::Position::startpos(), limits);
  const auto second = atropos::search::search(atropos::board::Position::startpos(), limits);

  REQUIRE(first.best_move.has_value());
  REQUIRE(second.best_move.has_value());
  REQUIRE(second.tt_hits > 0U);
  REQUIRE_EQ(atropos::board::move_to_uci(*second.best_move),
             atropos::board::move_to_uci(*first.best_move));
}

TEST_CASE("search records killer and history updates after quiet cutoffs") {
  atropos::search::SearchLimits limits;
  limits.depth = 3;
  const auto result = atropos::search::search(atropos::board::Position::startpos(), limits);

  REQUIRE(result.killer_updates > 0U);
  REQUIRE(result.history_updates > 0U);
}

TEST_CASE("search reports no best move in checkmate") {
  const auto position =
      *atropos::board::Position::from_fen("7k/6Q1/7K/8/8/8/8/8 b - - 0 1");
  const auto result = atropos::search::search_depth(position, 2);

  REQUIRE(!result.best_move.has_value());
  REQUIRE(result.score < -800000);
}
