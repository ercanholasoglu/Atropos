#pragma once

#include <array>
#include <cstdint>
#include <optional>
#include <string>
#include <string_view>

namespace atropos::board {

enum class Color : std::uint8_t { White, Black };
enum class PieceType : std::uint8_t { Pawn, Knight, Bishop, Rook, Queen, King };

struct Piece {
  Color color;
  PieceType type;

  [[nodiscard]] friend bool operator==(const Piece &, const Piece &) = default;
};

using Square = int;

struct CastlingRights {
  bool white_king_side = false;
  bool white_queen_side = false;
  bool black_king_side = false;
  bool black_queen_side = false;

  [[nodiscard]] friend bool operator==(const CastlingRights &, const CastlingRights &) = default;
};

enum class MoveFlag : std::uint8_t {
  Quiet,
  Capture,
  DoublePawnPush,
  KingCastle,
  QueenCastle,
  EnPassant,
  Promotion,
  PromotionCapture
};

struct Move {
  Square from = 0;
  Square to = 0;
  std::optional<PieceType> promotion;
  MoveFlag flag = MoveFlag::Quiet;

  [[nodiscard]] friend bool operator==(const Move &, const Move &) = default;
};

[[nodiscard]] constexpr Color opposite(Color color) {
  return color == Color::White ? Color::Black : Color::White;
}

[[nodiscard]] constexpr Square make_square(int file, int rank) { return rank * 8 + file; }
[[nodiscard]] constexpr int file_of(Square square) { return square % 8; }
[[nodiscard]] constexpr int rank_of(Square square) { return square / 8; }
[[nodiscard]] constexpr bool is_valid_square(Square square) { return square >= 0 && square < 64; }

[[nodiscard]] char piece_to_fen(Piece piece);
[[nodiscard]] std::optional<Piece> piece_from_fen(char text);
[[nodiscard]] std::string square_to_string(Square square);
[[nodiscard]] std::optional<Square> square_from_string(std::string_view text);
[[nodiscard]] std::string move_to_uci(Move move);

} // namespace atropos::board
