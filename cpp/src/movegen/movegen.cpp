#include "movegen/movegen.hpp"

#include <array>
#include <span>

namespace atropos::movegen {
namespace {

using atropos::board::Color;
using atropos::board::Move;
using atropos::board::MoveFlag;
using atropos::board::Piece;
using atropos::board::PieceType;
using atropos::board::Position;
using atropos::board::Square;

[[nodiscard]] bool on_board(int file, int rank) { return file >= 0 && file < 8 && rank >= 0 && rank < 8; }

void add_promotions(std::vector<Move> &moves, Square from, Square to, bool capture) {
  const auto flag = capture ? MoveFlag::PromotionCapture : MoveFlag::Promotion;
  moves.push_back(Move{from, to, PieceType::Queen, flag});
  moves.push_back(Move{from, to, PieceType::Rook, flag});
  moves.push_back(Move{from, to, PieceType::Bishop, flag});
  moves.push_back(Move{from, to, PieceType::Knight, flag});
}

void add_pawn_moves(const Position &position, Square square, Piece piece, std::vector<Move> &moves) {
  const int direction = piece.color == Color::White ? 1 : -1;
  const int start_rank = piece.color == Color::White ? 1 : 6;
  const int promotion_rank = piece.color == Color::White ? 7 : 0;
  const int file = board::file_of(square);
  const int rank = board::rank_of(square);

  const int one_rank = rank + direction;
  if (on_board(file, one_rank)) {
    const Square one = board::make_square(file, one_rank);
    if (!position.piece_at(one).has_value()) {
      if (one_rank == promotion_rank) {
        add_promotions(moves, square, one, false);
      } else {
        moves.push_back(Move{square, one, std::nullopt, MoveFlag::Quiet});
        const int two_rank = rank + (2 * direction);
        if (rank == start_rank && on_board(file, two_rank)) {
          const Square two = board::make_square(file, two_rank);
          if (!position.piece_at(two).has_value()) {
            moves.push_back(Move{square, two, std::nullopt, MoveFlag::DoublePawnPush});
          }
        }
      }
    }
  }

  for (const int file_delta : {-1, 1}) {
    const int target_file = file + file_delta;
    const int target_rank = rank + direction;
    if (!on_board(target_file, target_rank)) {
      continue;
    }
    const Square target = board::make_square(target_file, target_rank);
    const auto target_piece = position.piece_at(target);
    if (target_piece.has_value() && target_piece->color != piece.color) {
      if (target_rank == promotion_rank) {
        add_promotions(moves, square, target, true);
      } else {
        moves.push_back(Move{square, target, std::nullopt, MoveFlag::Capture});
      }
    }
    if (position.en_passant_square() == std::optional<Square>{target}) {
      moves.push_back(Move{square, target, std::nullopt, MoveFlag::EnPassant});
    }
  }
}

void add_leaper_moves(const Position &position, Square square, Piece piece,
                      std::span<const std::pair<int, int>> offsets, std::vector<Move> &moves) {
  for (const auto &[df, dr] : offsets) {
    const int file = board::file_of(square) + df;
    const int rank = board::rank_of(square) + dr;
    if (!on_board(file, rank)) {
      continue;
    }
    const Square target = board::make_square(file, rank);
    const auto target_piece = position.piece_at(target);
    if (!target_piece.has_value()) {
      moves.push_back(Move{square, target, std::nullopt, MoveFlag::Quiet});
    } else if (target_piece->color != piece.color) {
      moves.push_back(Move{square, target, std::nullopt, MoveFlag::Capture});
    }
  }
}

void add_slider_moves(const Position &position, Square square, Piece piece,
                      std::span<const std::pair<int, int>> directions, std::vector<Move> &moves) {
  for (const auto &[df, dr] : directions) {
    int file = board::file_of(square) + df;
    int rank = board::rank_of(square) + dr;
    while (on_board(file, rank)) {
      const Square target = board::make_square(file, rank);
      const auto target_piece = position.piece_at(target);
      if (!target_piece.has_value()) {
        moves.push_back(Move{square, target, std::nullopt, MoveFlag::Quiet});
      } else {
        if (target_piece->color != piece.color) {
          moves.push_back(Move{square, target, std::nullopt, MoveFlag::Capture});
        }
        break;
      }
      file += df;
      rank += dr;
    }
  }
}

void add_castles(const Position &position, Square square, Piece piece, std::vector<Move> &moves) {
  const int rank = piece.color == Color::White ? 0 : 7;
  if (square != board::make_square(4, rank) || position.in_check(piece.color)) {
    return;
  }
  const auto rights = position.castling_rights();
  const Color opponent = board::opposite(piece.color);

  const bool king_side = piece.color == Color::White ? rights.white_king_side : rights.black_king_side;
  if (king_side && position.piece_at(board::make_square(5, rank)) == std::nullopt &&
      position.piece_at(board::make_square(6, rank)) == std::nullopt &&
      position.piece_at(board::make_square(7, rank)) ==
          std::optional<Piece>{Piece{piece.color, PieceType::Rook}} &&
      !position.is_square_attacked(board::make_square(5, rank), opponent) &&
      !position.is_square_attacked(board::make_square(6, rank), opponent)) {
    moves.push_back(Move{square, board::make_square(6, rank), std::nullopt, MoveFlag::KingCastle});
  }

  const bool queen_side = piece.color == Color::White ? rights.white_queen_side : rights.black_queen_side;
  if (queen_side && position.piece_at(board::make_square(1, rank)) == std::nullopt &&
      position.piece_at(board::make_square(2, rank)) == std::nullopt &&
      position.piece_at(board::make_square(3, rank)) == std::nullopt &&
      position.piece_at(board::make_square(0, rank)) ==
          std::optional<Piece>{Piece{piece.color, PieceType::Rook}} &&
      !position.is_square_attacked(board::make_square(3, rank), opponent) &&
      !position.is_square_attacked(board::make_square(2, rank), opponent)) {
    moves.push_back(Move{square, board::make_square(2, rank), std::nullopt, MoveFlag::QueenCastle});
  }
}

void add_piece_moves(const Position &position, Square square, Piece piece, std::vector<Move> &moves) {
  static constexpr std::array<std::pair<int, int>, 8> knight_offsets = {
      {{1, 2}, {2, 1}, {2, -1}, {1, -2}, {-1, -2}, {-2, -1}, {-2, 1}, {-1, 2}}};
  static constexpr std::array<std::pair<int, int>, 8> king_offsets = {
      {{1, 1}, {1, 0}, {1, -1}, {0, -1}, {-1, -1}, {-1, 0}, {-1, 1}, {0, 1}}};
  static constexpr std::array<std::pair<int, int>, 4> bishop_dirs = {{{1, 1}, {1, -1}, {-1, -1}, {-1, 1}}};
  static constexpr std::array<std::pair<int, int>, 4> rook_dirs = {{{1, 0}, {0, -1}, {-1, 0}, {0, 1}}};
  static constexpr std::array<std::pair<int, int>, 8> queen_dirs = {
      {{1, 1}, {1, 0}, {1, -1}, {0, -1}, {-1, -1}, {-1, 0}, {-1, 1}, {0, 1}}};

  switch (piece.type) {
  case PieceType::Pawn:
    add_pawn_moves(position, square, piece, moves);
    break;
  case PieceType::Knight:
    add_leaper_moves(position, square, piece, knight_offsets, moves);
    break;
  case PieceType::Bishop:
    add_slider_moves(position, square, piece, bishop_dirs, moves);
    break;
  case PieceType::Rook:
    add_slider_moves(position, square, piece, rook_dirs, moves);
    break;
  case PieceType::Queen:
    add_slider_moves(position, square, piece, queen_dirs, moves);
    break;
  case PieceType::King:
    add_leaper_moves(position, square, piece, king_offsets, moves);
    add_castles(position, square, piece, moves);
    break;
  }
}

} // namespace

std::vector<Move> generate_pseudo_legal_moves(const Position &position) {
  std::vector<Move> moves;
  moves.reserve(256);
  generate_pseudo_legal_moves_into(position, moves);
  return moves;
}

void generate_pseudo_legal_moves_into(const Position &position, std::vector<Move> &moves) {
  moves.clear();
  moves.reserve(256);
  for (Square square = 0; square < 64; ++square) {
    const auto piece = position.piece_at(square);
    if (piece.has_value() && piece->color == position.side_to_move()) {
      add_piece_moves(position, square, *piece, moves);
    }
  }
}

bool is_legal_move(const Position &position, Move move) {
  auto copy = position;
  const Color moving_side = copy.side_to_move();
  const auto undo = copy.make_move(move);
  if (!undo.has_value()) {
    return false;
  }
  return !copy.in_check(moving_side);
}

std::vector<Move> generate_legal_moves(const Position &position) {
  std::vector<Move> legal;
  generate_legal_moves_into(position, legal);
  return legal;
}

void generate_legal_moves_into(const Position &position, std::vector<Move> &legal) {
  std::vector<Move> pseudo;
  generate_legal_moves_into(position, legal, pseudo);
}

void generate_legal_moves_into(const Position &position, std::vector<Move> &legal, std::vector<Move> &pseudo) {
  generate_pseudo_legal_moves_into(position, pseudo);
  legal.clear();
  legal.reserve(pseudo.size());
  for (const auto move : pseudo) {
    if (is_legal_move(position, move)) {
      legal.push_back(move);
    }
  }
}

} // namespace atropos::movegen
