#include "test.hpp"
#include "board/state.hpp"
#include "board/types.hpp"

#include <fstream>
#include <random>
#include <sstream>
#include <string>
#include <vector>

#include "movegen/movegen.hpp"

namespace {

[[nodiscard]] atropos::board::Move simple_move(std::string_view from, std::string_view to) {
  return atropos::board::Move{*atropos::board::square_from_string(from),
                              *atropos::board::square_from_string(to), std::nullopt,
                              atropos::board::MoveFlag::Quiet};
}

} // namespace

TEST_CASE("FEN roundtrip preserves complete state fields") {
  const std::string fen = "r3k2r/pppq1ppp/2npbn2/3Np3/2B1P3/2N2Q2/PPP2PPP/R3K2R b KQkq - 7 12";
  const auto position = atropos::board::Position::from_fen(fen);

  REQUIRE(position.has_value());
  REQUIRE_EQ(position->to_fen(), fen);
}

TEST_CASE("Phase 1 FEN fixture file is parseable") {
  std::ifstream input("tests/fixtures/phase1/edge_cases.fen");
  REQUIRE(input.good());

  std::string line;
  int parsed = 0;
  while (std::getline(input, line)) {
    if (line.empty() || line.front() == '#') {
      continue;
    }
    std::istringstream row(line);
    std::string name;
    std::string fen;
    std::getline(row, name, '|');
    std::getline(row, fen, '|');
    const auto position = atropos::board::Position::from_fen(fen);
    REQUIRE(position.has_value());
    REQUIRE_EQ(position->to_fen(), fen);
    ++parsed;
  }
  REQUIRE_EQ(parsed, 4);
}

TEST_CASE("make and unmake roundtrip restores FEN and Zobrist hash") {
  auto position = atropos::board::Position::startpos();
  const auto before_fen = position.to_fen();
  const auto before_hash = position.hash();

  auto move = simple_move("e2", "e4");
  move.flag = atropos::board::MoveFlag::DoublePawnPush;
  const auto undo = position.make_move(move);
  REQUIRE(undo.has_value());
  REQUIRE_EQ(position.en_passant_square(), atropos::board::square_from_string("e3"));

  position.unmake_move(*undo);
  REQUIRE_EQ(position.to_fen(), before_fen);
  REQUIRE_EQ(position.hash(), before_hash);
}

TEST_CASE("cached hash matches reparsed FEN hash after legal moves") {
  auto position = atropos::board::Position::startpos();

  for (int ply = 0; ply < 24; ++ply) {
    const auto moves = atropos::movegen::generate_legal_moves(position);
    REQUIRE(!moves.empty());
    const auto move = moves[static_cast<std::size_t>(ply) % moves.size()];
    const auto undo = position.make_move(move);
    REQUIRE(undo.has_value());

    const auto reparsed = atropos::board::Position::from_fen(position.to_fen());
    REQUIRE(reparsed.has_value());
    REQUIRE_EQ(position.hash(), reparsed->hash());
  }
}

TEST_CASE("halfmove clock resets on pawn move and capture") {
  auto position = *atropos::board::Position::from_fen("8/8/8/8/8/8/4P3/4K2k w - - 9 20");
  auto pawn_move = simple_move("e2", "e3");
  const auto undo = position.make_move(pawn_move);
  REQUIRE(undo.has_value());
  REQUIRE_EQ(position.halfmove_clock(), 0);

  position = *atropos::board::Position::from_fen("8/8/8/8/8/8/4p3/4K2k b - - 9 20");
  auto capture = simple_move("e2", "e1");
  capture.flag = atropos::board::MoveFlag::Capture;
  const auto undo_capture = position.make_move(capture);
  REQUIRE(undo_capture.has_value());
  REQUIRE_EQ(position.halfmove_clock(), 0);
}

TEST_CASE("side to move and fullmove number update on make and unmake") {
  auto position = atropos::board::Position::startpos();
  auto white_move = simple_move("g1", "f3");
  const auto undo_white = position.make_move(white_move);
  REQUIRE(undo_white.has_value());
  REQUIRE_EQ(position.side_to_move(), atropos::board::Color::Black);
  REQUIRE_EQ(position.fullmove_number(), 1);

  auto black_move = simple_move("g8", "f6");
  const auto undo_black = position.make_move(black_move);
  REQUIRE(undo_black.has_value());
  REQUIRE_EQ(position.side_to_move(), atropos::board::Color::White);
  REQUIRE_EQ(position.fullmove_number(), 2);

  position.unmake_move(*undo_black);
  position.unmake_move(*undo_white);
  REQUIRE_EQ(position.to_fen(), std::string(atropos::board::Position::StartFen));
}

TEST_CASE("castling rights are removed after king or rook move") {
  auto position = *atropos::board::Position::from_fen("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1");

  const auto rook_undo = position.make_move(simple_move("h1", "h2"));
  REQUIRE(rook_undo.has_value());
  REQUIRE(!position.castling_rights().white_king_side);
  REQUIRE(position.castling_rights().white_queen_side);
  position.unmake_move(*rook_undo);

  const auto king_undo = position.make_move(simple_move("e1", "e2"));
  REQUIRE(king_undo.has_value());
  REQUIRE(!position.castling_rights().white_king_side);
  REQUIRE(!position.castling_rights().white_queen_side);
}

TEST_CASE("repetition keys track repeated state") {
  auto position = *atropos::board::Position::from_fen("8/8/8/8/8/8/6N1/4K2k w - - 0 1");

  const auto n_g2f4 = simple_move("g2", "f4");
  const auto k_h1g1 = simple_move("h1", "g1");
  const auto n_f4g2 = simple_move("f4", "g2");
  const auto k_g1h1 = simple_move("g1", "h1");

  REQUIRE(position.make_move(n_g2f4).has_value());
  REQUIRE(position.make_move(k_h1g1).has_value());
  REQUIRE(position.make_move(n_f4g2).has_value());
  REQUIRE(position.make_move(k_g1h1).has_value());

  REQUIRE_EQ(position.repetition_count(), 2);
}

TEST_CASE("deterministic random legal make and unmake restores every state") {
  auto position = atropos::board::Position::startpos();
  std::vector<atropos::board::Position::UndoState> undo_stack;
  std::vector<std::string> fen_stack;
  std::vector<std::uint64_t> hash_stack;
  std::mt19937 rng(20260823U);

  for (int ply = 0; ply < 64; ++ply) {
    const auto moves = atropos::movegen::generate_legal_moves(position);
    if (moves.empty()) {
      break;
    }
    fen_stack.push_back(position.to_fen());
    hash_stack.push_back(position.hash());
    const auto move = moves[static_cast<std::size_t>(rng()) % moves.size()];
    const auto undo = position.make_move(move);
    REQUIRE(undo.has_value());
    REQUIRE(!position.in_check(atropos::board::opposite(position.side_to_move())));
    undo_stack.push_back(*undo);
  }

  while (!undo_stack.empty()) {
    position.unmake_move(undo_stack.back());
    undo_stack.pop_back();
    REQUIRE_EQ(position.to_fen(), fen_stack.back());
    REQUIRE_EQ(position.hash(), hash_stack.back());
    fen_stack.pop_back();
    hash_stack.pop_back();
  }
}
