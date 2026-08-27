#pragma once

#include "board/types.hpp"

#include <array>
#include <optional>
#include <string>
#include <vector>

namespace atropos::board {

class Position {
public:
  static constexpr std::string_view StartFen =
      "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

  struct UndoState {
    Move move;
    std::optional<Piece> moved_piece;
    std::optional<Piece> captured_piece;
    Square captured_square = -1;
    CastlingRights castling;
    std::optional<Square> en_passant;
    int halfmove_clock = 0;
    int fullmove_number = 1;
    std::uint64_t hash = 0;
  };

  [[nodiscard]] static std::optional<Position> from_fen(std::string_view fen);
  [[nodiscard]] static Position startpos();

  [[nodiscard]] std::string to_fen() const;
  [[nodiscard]] std::optional<Piece> piece_at(Square square) const;
  void set_piece(Square square, std::optional<Piece> piece);

  [[nodiscard]] Color side_to_move() const noexcept { return side_to_move_; }
  [[nodiscard]] CastlingRights castling_rights() const noexcept { return castling_; }
  [[nodiscard]] std::optional<Square> en_passant_square() const noexcept { return en_passant_; }
  [[nodiscard]] int halfmove_clock() const noexcept { return halfmove_clock_; }
  [[nodiscard]] int fullmove_number() const noexcept { return fullmove_number_; }
  [[nodiscard]] const std::vector<std::uint64_t> &repetition_keys() const noexcept {
    return repetition_keys_;
  }

  [[nodiscard]] bool in_check(Color color) const;
  [[nodiscard]] bool is_square_attacked(Square square, Color by_color) const;
  [[nodiscard]] std::optional<Square> king_square(Color color) const;

  [[nodiscard]] std::uint64_t hash() const noexcept { return hash_; }
  [[nodiscard]] int repetition_count() const;

  [[nodiscard]] std::optional<UndoState> make_move(Move move);
  void unmake_move(const UndoState &undo);

private:
  std::array<std::optional<Piece>, 64> board_{};
  Color side_to_move_ = Color::White;
  CastlingRights castling_{};
  std::optional<Square> en_passant_;
  int halfmove_clock_ = 0;
  int fullmove_number_ = 1;
  std::uint64_t hash_ = 0;
  std::vector<std::uint64_t> repetition_keys_;

  [[nodiscard]] std::uint64_t compute_hash() const;
  void xor_position_state();
  void update_castling_rights(Move move, std::optional<Piece> moved,
                              std::optional<Piece> captured, Square captured_square);
};

} // namespace atropos::board
