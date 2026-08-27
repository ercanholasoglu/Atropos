#include "test.hpp"
#include "board/types.hpp"
#include "transposition_table/transposition_table.hpp"

TEST_CASE("transposition table probes stored entries by key") {
  atropos::tt::TranspositionTable table(1);
  const atropos::board::Move move{0, 1, std::nullopt, atropos::board::MoveFlag::Quiet};

  table.store(atropos::tt::Entry{42U, 3, 120, atropos::tt::Bound::Exact, move});
  const auto entry = table.probe(42U);

  REQUIRE(entry.has_value());
  REQUIRE_EQ(entry->depth, 3);
  REQUIRE_EQ(entry->score, 120);
  REQUIRE(entry->best_move.has_value());
  REQUIRE_EQ(*entry->best_move, move);
}

TEST_CASE("transposition table keeps deeper same-key entries") {
  atropos::tt::TranspositionTable table(1);

  table.store(atropos::tt::Entry{7U, 4, 400, atropos::tt::Bound::Exact, std::nullopt});
  table.store(atropos::tt::Entry{7U, 2, 200, atropos::tt::Bound::Exact, std::nullopt});
  const auto entry = table.probe(7U);

  REQUIRE(entry.has_value());
  REQUIRE_EQ(entry->depth, 4);
  REQUIRE_EQ(entry->score, 400);
}
