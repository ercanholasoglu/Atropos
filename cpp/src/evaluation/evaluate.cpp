#include "evaluation/evaluate.hpp"

#include <array>
#include <cmath>

namespace atropos::evaluation {
namespace {

using board::Color;
using board::Piece;
using board::PieceType;
using board::Position;
using board::Square;

constexpr std::array<int, 64> PawnPst = {{
    0, 0, 0, 0, 0, 0, 0, 0,       5, 10, 10, -20, -20, 10, 10, 5,
    5, -5, -10, 0, 0, -10, -5, 5, 0, 0, 0, 20, 20, 0, 0, 0,
    5, 5, 10, 25, 25, 10, 5, 5,   10, 10, 20, 30, 30, 20, 10, 10,
    50, 50, 50, 50, 50, 50, 50, 50, 0, 0, 0, 0, 0, 0, 0, 0,
}};

constexpr std::array<int, 64> KnightPst = {{
    -50, -40, -30, -30, -30, -30, -40, -50, -40, -20, 0, 5, 5, 0, -20, -40,
    -30, 5, 10, 15, 15, 10, 5, -30,    -30, 0, 15, 20, 20, 15, 0, -30,
    -30, 5, 15, 20, 20, 15, 5, -30,    -30, 0, 10, 15, 15, 10, 0, -30,
    -40, -20, 0, 0, 0, 0, -20, -40,    -50, -40, -30, -30, -30, -30, -40, -50,
}};

constexpr std::array<int, 64> BishopPst = {{
    -20, -10, -10, -10, -10, -10, -10, -20, -10, 5, 0, 0, 0, 0, 5, -10,
    -10, 10, 10, 10, 10, 10, 10, -10,   -10, 0, 10, 10, 10, 10, 0, -10,
    -10, 5, 5, 10, 10, 5, 5, -10,       -10, 0, 5, 10, 10, 5, 0, -10,
    -10, 0, 0, 0, 0, 0, 0, -10,         -20, -10, -10, -10, -10, -10, -10, -20,
}};

constexpr std::array<int, 64> RookPst = {{
    0, 0, 0, 5, 5, 0, 0, 0,       -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,     -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,     -5, 0, 0, 0, 0, 0, 0, -5,
    5, 10, 10, 10, 10, 10, 10, 5, 0, 0, 0, 0, 0, 0, 0, 0,
}};

constexpr std::array<int, 64> QueenPst = {{
    -20, -10, -10, -5, -5, -10, -10, -20, -10, 0, 5, 0, 0, 0, 0, -10,
    -10, 5, 5, 5, 5, 5, 0, -10,       0, 0, 5, 5, 5, 5, 0, -5,
    -5, 0, 5, 5, 5, 5, 0, -5,         -10, 0, 5, 5, 5, 5, 0, -10,
    -10, 0, 0, 0, 0, 0, 0, -10,       -20, -10, -10, -5, -5, -10, -10, -20,
}};

constexpr std::array<int, 64> KingPst = {{
    20, 30, 10, 0, 0, 10, 30, 20,     20, 20, 0, 0, 0, 0, 20, 20,
    -10, -20, -20, -20, -20, -20, -20, -10, -20, -30, -30, -40, -40, -30, -30, -20,
    -30, -40, -40, -50, -50, -40, -40, -30, -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30, -30, -40, -40, -50, -50, -40, -40, -30,
}};

[[nodiscard]] bool on_board(int file, int rank) { return file >= 0 && file < 8 && rank >= 0 && rank < 8; }

[[nodiscard]] int pst_index(Square square, Color color) {
  const int file = board::file_of(square);
  const int rank = color == Color::White ? board::rank_of(square) : 7 - board::rank_of(square);
  return board::make_square(file, rank);
}

[[nodiscard]] int pst_value(Piece piece, Square square) {
  const auto index = static_cast<std::size_t>(pst_index(square, piece.color));
  switch (piece.type) {
  case PieceType::Pawn:
    return PawnPst[index];
  case PieceType::Knight:
    return KnightPst[index];
  case PieceType::Bishop:
    return BishopPst[index];
  case PieceType::Rook:
    return RookPst[index];
  case PieceType::Queen:
    return QueenPst[index];
  case PieceType::King:
    return KingPst[index];
  }
  return 0;
}

[[nodiscard]] int leaper_mobility(const Position &position, Square square, Piece piece,
                                  const std::array<std::pair<int, int>, 8> &offsets) {
  int count = 0;
  for (const auto &[df, dr] : offsets) {
    const int file = board::file_of(square) + df;
    const int rank = board::rank_of(square) + dr;
    if (!on_board(file, rank)) {
      continue;
    }
    const auto target = position.piece_at(board::make_square(file, rank));
    if (!target.has_value() || target->color != piece.color) {
      ++count;
    }
  }
  return count;
}

[[nodiscard]] int slider_mobility(const Position &position, Square square, Piece piece,
                                  const std::array<std::pair<int, int>, 8> &directions,
                                  int direction_count) {
  int count = 0;
  for (int i = 0; i < direction_count; ++i) {
    const auto [df, dr] = directions[static_cast<std::size_t>(i)];
    int file = board::file_of(square) + df;
    int rank = board::rank_of(square) + dr;
    while (on_board(file, rank)) {
      const auto target = position.piece_at(board::make_square(file, rank));
      if (!target.has_value()) {
        ++count;
      } else {
        if (target->color != piece.color) {
          ++count;
        }
        break;
      }
      file += df;
      rank += dr;
    }
  }
  return count;
}

[[nodiscard]] int mobility_score(const Position &position, Square square, Piece piece) {
  static constexpr std::array<std::pair<int, int>, 8> knight_offsets = {
      {{1, 2}, {2, 1}, {2, -1}, {1, -2}, {-1, -2}, {-2, -1}, {-2, 1}, {-1, 2}}};
  static constexpr std::array<std::pair<int, int>, 8> king_offsets = {
      {{1, 1}, {1, 0}, {1, -1}, {0, -1}, {-1, -1}, {-1, 0}, {-1, 1}, {0, 1}}};
  static constexpr std::array<std::pair<int, int>, 8> bishop_dirs = {
      {{1, 1}, {1, -1}, {-1, -1}, {-1, 1}, {0, 0}, {0, 0}, {0, 0}, {0, 0}}};
  static constexpr std::array<std::pair<int, int>, 8> rook_dirs = {
      {{1, 0}, {0, -1}, {-1, 0}, {0, 1}, {0, 0}, {0, 0}, {0, 0}, {0, 0}}};
  static constexpr std::array<std::pair<int, int>, 8> queen_dirs = {
      {{1, 1}, {1, 0}, {1, -1}, {0, -1}, {-1, -1}, {-1, 0}, {-1, 1}, {0, 1}}};

  switch (piece.type) {
  case PieceType::Knight:
    return 4 * leaper_mobility(position, square, piece, knight_offsets);
  case PieceType::Bishop:
    return 3 * slider_mobility(position, square, piece, bishop_dirs, 4);
  case PieceType::Rook:
    return 2 * slider_mobility(position, square, piece, rook_dirs, 4);
  case PieceType::Queen:
    return slider_mobility(position, square, piece, queen_dirs, 8);
  case PieceType::King:
    return leaper_mobility(position, square, piece, king_offsets);
  case PieceType::Pawn:
    return 0;
  }
  return 0;
}

[[nodiscard]] int pawn_structure_score(const std::array<std::array<int, 8>, 2> &pawns) {
  int score = 0;
  for (int color_index = 0; color_index < 2; ++color_index) {
    const int sign = color_index == 0 ? 1 : -1;
    for (int file = 0; file < 8; ++file) {
      const int count = pawns[static_cast<std::size_t>(color_index)][static_cast<std::size_t>(file)];
      if (count > 1) {
        score -= sign * 12 * (count - 1);
      }
      const bool left = file > 0 && pawns[static_cast<std::size_t>(color_index)][static_cast<std::size_t>(file - 1)] > 0;
      const bool right = file < 7 && pawns[static_cast<std::size_t>(color_index)][static_cast<std::size_t>(file + 1)] > 0;
      if (count > 0 && !left && !right) {
        score -= sign * 10;
      }
    }
  }
  return score;
}

} // namespace

int piece_value(board::PieceType type) noexcept {
  switch (type) {
  case board::PieceType::Pawn:
    return 100;
  case board::PieceType::Knight:
    return 320;
  case board::PieceType::Bishop:
    return 330;
  case board::PieceType::Rook:
    return 500;
  case board::PieceType::Queen:
    return 900;
  case board::PieceType::King:
    return 0;
  }
  return 0;
}

int evaluate_material(const board::Position &position) noexcept {
  int score = 0;
  for (board::Square square = 0; square < 64; ++square) {
    const auto piece = position.piece_at(square);
    if (!piece.has_value()) {
      continue;
    }
    const int value = piece_value(piece->type);
    score += piece->color == board::Color::White ? value : -value;
  }
  return score;
}

int evaluate(const board::Position &position) noexcept {
  int white_score = evaluate_material(position);
  std::array<int, 2> bishops{};
  std::array<std::array<int, 8>, 2> pawns{};

  for (board::Square square = 0; square < 64; ++square) {
    const auto piece = position.piece_at(square);
    if (!piece.has_value()) {
      continue;
    }
    const int sign = piece->color == board::Color::White ? 1 : -1;
    white_score += sign * pst_value(*piece, square);
    white_score += sign * mobility_score(position, square, *piece);

    const auto color_index = static_cast<std::size_t>(piece->color == board::Color::White ? 0 : 1);
    if (piece->type == board::PieceType::Bishop) {
      ++bishops[color_index];
    } else if (piece->type == board::PieceType::Pawn) {
      ++pawns[color_index][static_cast<std::size_t>(board::file_of(square))];
    }
  }

  if (bishops[0] >= 2) {
    white_score += 35;
  }
  if (bishops[1] >= 2) {
    white_score -= 35;
  }
  white_score += pawn_structure_score(pawns);

  return position.side_to_move() == board::Color::White ? white_score : -white_score;
}

} // namespace atropos::evaluation
