#include "test.hpp"
#include "board/state.hpp"
#include "board/types.hpp"
#include "movegen/movegen.hpp"

#include <algorithm>
#include <string>
#include <vector>

namespace {

[[nodiscard]] std::vector<std::string> move_text(std::vector<atropos::board::Move> moves) {
  std::vector<std::string> text;
  text.reserve(moves.size());
  for (const auto move : moves) {
    text.push_back(atropos::board::move_to_uci(move));
  }
  std::sort(text.begin(), text.end());
  return text;
}

[[nodiscard]] std::vector<std::string> legal_uci(const atropos::board::Position &position) {
  return move_text(atropos::movegen::generate_legal_moves(position));
}

[[nodiscard]] bool contains(const std::vector<std::string> &moves, std::string_view move) {
  return std::find(moves.begin(), moves.end(), move) != moves.end();
}

} // namespace

TEST_CASE("start position has twenty legal moves") {
  const auto moves = legal_uci(atropos::board::Position::startpos());

  REQUIRE_EQ(moves.size(), 20U);
  REQUIRE(contains(moves, "e2e4"));
  REQUIRE(contains(moves, "g1f3"));
}

TEST_CASE("into legal move generation matches value returning API") {
  const auto position = *atropos::board::Position::from_fen(
      "r3k2r/pppq1ppp/2npbn2/3Np3/2B1P3/2N2Q2/PPP2PPP/R3K2R b KQkq - 7 12");
  std::vector<atropos::board::Move> legal;
  std::vector<atropos::board::Move> pseudo;

  atropos::movegen::generate_legal_moves_into(position, legal, pseudo);

  REQUIRE_EQ(move_text(legal), legal_uci(position));
}

TEST_CASE("double check allows only king evasions") {
  const auto position = *atropos::board::Position::from_fen("4r3/8/8/8/4k3/8/3N4/4K3 b - - 0 1");
  const auto moves = legal_uci(position);

  for (const auto &move : moves) {
    REQUIRE(move.starts_with("e4"));
  }
}

TEST_CASE("castling rejects attacked transit squares") {
  const auto position = *atropos::board::Position::from_fen("r3k2r/8/8/8/2b5/8/8/R3K2R w KQkq - 0 1");
  const auto moves = legal_uci(position);

  REQUIRE(!contains(moves, "e1g1"));
  REQUIRE(contains(moves, "e1c1"));
}

TEST_CASE("en passant that exposes discovered check is illegal") {
  const auto position = *atropos::board::Position::from_fen("4r3/8/8/3pP3/8/8/8/4K3 w - d6 0 1");
  const auto moves = legal_uci(position);

  REQUIRE(!contains(moves, "e5d6"));
}

TEST_CASE("all four quiet promotion choices are generated") {
  const auto position = *atropos::board::Position::from_fen("4k3/P7/8/8/8/8/8/4K3 w - - 0 1");
  const auto moves = legal_uci(position);

  REQUIRE(contains(moves, "a7a8q"));
  REQUIRE(contains(moves, "a7a8r"));
  REQUIRE(contains(moves, "a7a8b"));
  REQUIRE(contains(moves, "a7a8n"));
}

TEST_CASE("all four capture promotion choices are generated") {
  const auto position = *atropos::board::Position::from_fen("1r2k3/P7/8/8/8/8/8/4K3 w - - 0 1");
  const auto moves = legal_uci(position);

  REQUIRE(contains(moves, "a7b8q"));
  REQUIRE(contains(moves, "a7b8r"));
  REQUIRE(contains(moves, "a7b8b"));
  REQUIRE(contains(moves, "a7b8n"));
}
