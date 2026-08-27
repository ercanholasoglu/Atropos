#include "test.hpp"
#include "board/state.hpp"
#include "evaluation/evaluate.hpp"

TEST_CASE("material evaluation is zero for bare kings") {
  const auto position = *atropos::board::Position::from_fen("8/8/8/8/8/8/8/4K2k w - - 0 1");

  REQUIRE_EQ(atropos::evaluation::evaluate_material(position), 0);
}

TEST_CASE("evaluation is from side to move perspective") {
  const auto white_to_move =
      *atropos::board::Position::from_fen("8/8/8/8/8/8/8/Q3K2k w - - 0 1");
  const auto black_to_move =
      *atropos::board::Position::from_fen("8/8/8/8/8/8/8/Q3K2k b - - 0 1");

  REQUIRE_EQ(atropos::evaluation::evaluate(white_to_move),
             -atropos::evaluation::evaluate(black_to_move));
  REQUIRE(atropos::evaluation::evaluate(white_to_move) > 900);
}

TEST_CASE("piece-square tables prefer centralized knights") {
  const auto center =
      *atropos::board::Position::from_fen("8/8/8/8/3N4/8/8/4K2k w - - 0 1");
  const auto rim = *atropos::board::Position::from_fen("8/8/8/8/8/8/N7/4K2k w - - 0 1");

  REQUIRE(atropos::evaluation::evaluate(center) > atropos::evaluation::evaluate(rim));
}

TEST_CASE("evaluation rewards bishop pair") {
  const auto pair = *atropos::board::Position::from_fen("8/8/8/8/8/8/8/2BBK2k w - - 0 1");
  const auto single = *atropos::board::Position::from_fen("8/8/8/8/8/8/8/2B1K2k w - - 0 1");

  REQUIRE(atropos::evaluation::evaluate(pair) > atropos::evaluation::evaluate(single) + 330);
}

TEST_CASE("pawn structure penalizes isolated pawns") {
  const auto connected =
      *atropos::board::Position::from_fen("8/8/8/8/8/8/PP6/4K2k w - - 0 1");
  const auto isolated =
      *atropos::board::Position::from_fen("8/8/8/8/8/8/P1P5/4K2k w - - 0 1");

  REQUIRE(atropos::evaluation::evaluate(connected) > atropos::evaluation::evaluate(isolated));
}
