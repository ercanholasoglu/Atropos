#include "board/state.hpp"

#include "zobrist/zobrist.hpp"

#include <algorithm>
#include <cctype>
#include <charconv>
#include <sstream>
#include <string>
#include <vector>

namespace atropos::board {
namespace {

[[nodiscard]] std::vector<std::string> split(std::string_view text) {
  std::istringstream input{std::string(text)};
  std::vector<std::string> words;
  std::string word;
  while (input >> word) {
    words.push_back(word);
  }
  return words;
}

[[nodiscard]] std::optional<int> parse_nonnegative_int(std::string_view text) {
  int value = 0;
  const auto *begin = text.data();
  const auto *end = text.data() + text.size();
  const auto result = std::from_chars(begin, end, value);
  if (result.ec != std::errc{} || result.ptr != end || value < 0) {
    return std::nullopt;
  }
  return value;
}

[[nodiscard]] bool same_line(Square from, Square to, int delta) {
  if (delta == 1 || delta == -1) {
    return rank_of(from) == rank_of(to);
  }
  if (delta == 9 || delta == -9) {
    return std::abs(file_of(from) - file_of(to)) == std::abs(rank_of(from) - rank_of(to));
  }
  if (delta == 7 || delta == -7) {
    return std::abs(file_of(from) - file_of(to)) == std::abs(rank_of(from) - rank_of(to));
  }
  return true;
}

[[nodiscard]] bool is_rook_home_square(Square square, Color color, bool king_side) {
  if (color == Color::White) {
    return square == (king_side ? make_square(7, 0) : make_square(0, 0));
  }
  return square == (king_side ? make_square(7, 7) : make_square(0, 7));
}

} // namespace

Position Position::startpos() { return *from_fen(StartFen); }

std::optional<Position> Position::from_fen(std::string_view fen) {
  const auto fields = split(fen);
  if (fields.size() != 6) {
    return std::nullopt;
  }

  Position position;
  int rank = 7;
  int file = 0;
  for (const char text : fields[0]) {
    if (text == '/') {
      if (file != 8 || rank == 0) {
        return std::nullopt;
      }
      --rank;
      file = 0;
      continue;
    }
    if (std::isdigit(static_cast<unsigned char>(text)) != 0) {
      const int empty_count = text - '0';
      if (empty_count < 1 || empty_count > 8 || file + empty_count > 8) {
        return std::nullopt;
      }
      file += empty_count;
      continue;
    }
    const auto piece = piece_from_fen(text);
    if (!piece.has_value() || file >= 8) {
      return std::nullopt;
    }
    position.board_[static_cast<std::size_t>(make_square(file, rank))] = *piece;
    ++file;
  }
  if (rank != 0 || file != 8) {
    return std::nullopt;
  }

  if (fields[1] == "w") {
    position.side_to_move_ = Color::White;
  } else if (fields[1] == "b") {
    position.side_to_move_ = Color::Black;
  } else {
    return std::nullopt;
  }

  if (fields[2] != "-") {
    for (const char right : fields[2]) {
      switch (right) {
      case 'K':
        position.castling_.white_king_side = true;
        break;
      case 'Q':
        position.castling_.white_queen_side = true;
        break;
      case 'k':
        position.castling_.black_king_side = true;
        break;
      case 'q':
        position.castling_.black_queen_side = true;
        break;
      default:
        return std::nullopt;
      }
    }
  }

  if (fields[3] != "-") {
    const auto ep = square_from_string(fields[3]);
    if (!ep.has_value() || (rank_of(*ep) != 2 && rank_of(*ep) != 5)) {
      return std::nullopt;
    }
    position.en_passant_ = *ep;
  }

  const auto halfmove = parse_nonnegative_int(fields[4]);
  const auto fullmove = parse_nonnegative_int(fields[5]);
  if (!halfmove.has_value() || !fullmove.has_value() || *fullmove < 1) {
    return std::nullopt;
  }
  position.halfmove_clock_ = *halfmove;
  position.fullmove_number_ = *fullmove;
  position.hash_ = position.compute_hash();
  position.repetition_keys_.push_back(position.hash());
  return position;
}

std::string Position::to_fen() const {
  std::ostringstream out;
  for (int rank = 7; rank >= 0; --rank) {
    int empty_count = 0;
    for (int file = 0; file < 8; ++file) {
      const auto piece = piece_at(make_square(file, rank));
      if (!piece.has_value()) {
        ++empty_count;
        continue;
      }
      if (empty_count != 0) {
        out << empty_count;
        empty_count = 0;
      }
      out << piece_to_fen(*piece);
    }
    if (empty_count != 0) {
      out << empty_count;
    }
    if (rank != 0) {
      out << '/';
    }
  }

  out << (side_to_move_ == Color::White ? " w " : " b ");
  std::string castling;
  if (castling_.white_king_side) {
    castling.push_back('K');
  }
  if (castling_.white_queen_side) {
    castling.push_back('Q');
  }
  if (castling_.black_king_side) {
    castling.push_back('k');
  }
  if (castling_.black_queen_side) {
    castling.push_back('q');
  }
  out << (castling.empty() ? "-" : castling);
  out << ' ' << (en_passant_.has_value() ? square_to_string(*en_passant_) : "-");
  out << ' ' << halfmove_clock_ << ' ' << fullmove_number_;
  return out.str();
}

std::optional<Piece> Position::piece_at(Square square) const {
  if (!is_valid_square(square)) {
    return std::nullopt;
  }
  return board_[static_cast<std::size_t>(square)];
}

void Position::set_piece(Square square, std::optional<Piece> piece) {
  if (is_valid_square(square)) {
    auto &slot = board_[static_cast<std::size_t>(square)];
    if (slot.has_value()) {
      hash_ ^= zobrist::piece_key(*slot, square);
    }
    slot = piece;
    if (slot.has_value()) {
      hash_ ^= zobrist::piece_key(*slot, square);
    }
  }
}

std::optional<Square> Position::king_square(Color color) const {
  for (Square square = 0; square < 64; ++square) {
    const auto piece = piece_at(square);
    if (piece.has_value() && piece->color == color && piece->type == PieceType::King) {
      return square;
    }
  }
  return std::nullopt;
}

bool Position::is_square_attacked(Square square, Color by_color) const {
  const int pawn_rank_delta = by_color == Color::White ? -1 : 1;
  for (const int file_delta : {-1, 1}) {
    const int file = file_of(square) + file_delta;
    const int rank = rank_of(square) + pawn_rank_delta;
    if (file >= 0 && file < 8 && rank >= 0 && rank < 8) {
      const auto piece = piece_at(make_square(file, rank));
      if (piece == std::optional<Piece>{Piece{by_color, PieceType::Pawn}}) {
        return true;
      }
    }
  }

  for (const auto &[df, dr] : std::array<std::pair<int, int>, 8>{
           {{1, 2}, {2, 1}, {2, -1}, {1, -2}, {-1, -2}, {-2, -1}, {-2, 1}, {-1, 2}}}) {
    const int file = file_of(square) + df;
    const int rank = rank_of(square) + dr;
    if (file >= 0 && file < 8 && rank >= 0 && rank < 8) {
      const auto piece = piece_at(make_square(file, rank));
      if (piece == std::optional<Piece>{Piece{by_color, PieceType::Knight}}) {
        return true;
      }
    }
  }

  for (const auto &[df, dr] : std::array<std::pair<int, int>, 8>{
           {{1, 1}, {1, 0}, {1, -1}, {0, -1}, {-1, -1}, {-1, 0}, {-1, 1}, {0, 1}}}) {
    const int file = file_of(square) + df;
    const int rank = rank_of(square) + dr;
    if (file >= 0 && file < 8 && rank >= 0 && rank < 8) {
      const auto piece = piece_at(make_square(file, rank));
      if (piece == std::optional<Piece>{Piece{by_color, PieceType::King}}) {
        return true;
      }
    }
  }

  for (const int delta : {1, -1, 8, -8, 9, -9, 7, -7}) {
    Square current = square + delta;
    while (is_valid_square(current) && same_line(current - delta, current, delta)) {
      const auto piece = piece_at(current);
      if (piece.has_value()) {
        if (piece->color == by_color) {
          const bool diagonal = delta == 9 || delta == -9 || delta == 7 || delta == -7;
          const bool orthogonal = !diagonal;
          if ((diagonal && (piece->type == PieceType::Bishop || piece->type == PieceType::Queen)) ||
              (orthogonal && (piece->type == PieceType::Rook || piece->type == PieceType::Queen))) {
            return true;
          }
        }
        break;
      }
      current += delta;
    }
  }

  return false;
}

bool Position::in_check(Color color) const {
  const auto king = king_square(color);
  return king.has_value() && is_square_attacked(*king, opposite(color));
}

std::uint64_t Position::compute_hash() const {
  std::uint64_t key = 0;
  for (Square square = 0; square < 64; ++square) {
    const auto piece = piece_at(square);
    if (piece.has_value()) {
      key ^= zobrist::piece_key(*piece, square);
    }
  }
  if (side_to_move_ == Color::Black) {
    key ^= zobrist::side_key();
  }
  key ^= zobrist::castling_key(castling_);
  key ^= zobrist::en_passant_key(en_passant_);
  return key;
}

void Position::xor_position_state() {
  if (side_to_move_ == Color::Black) {
    hash_ ^= zobrist::side_key();
  }
  hash_ ^= zobrist::castling_key(castling_);
  hash_ ^= zobrist::en_passant_key(en_passant_);
}

int Position::repetition_count() const {
  const auto current = hash();
  return static_cast<int>(std::count(repetition_keys_.begin(), repetition_keys_.end(), current));
}

std::optional<Position::UndoState> Position::make_move(Move move) {
  const auto moved = piece_at(move.from);
  if (!moved.has_value() || moved->color != side_to_move_) {
    return std::nullopt;
  }

  Square captured_square = move.to;
  auto captured = piece_at(move.to);
  if (move.flag == MoveFlag::EnPassant) {
    captured_square = move.to + (moved->color == Color::White ? -8 : 8);
    captured = piece_at(captured_square);
  }

  UndoState undo{move, moved, captured, captured_square, castling_, en_passant_, halfmove_clock_,
                 fullmove_number_, hash_};

  xor_position_state();

  set_piece(move.from, std::nullopt);
  if (move.flag == MoveFlag::EnPassant) {
    set_piece(captured_square, std::nullopt);
  }

  Piece placed = *moved;
  if (move.promotion.has_value()) {
    placed.type = *move.promotion;
  }
  set_piece(move.to, placed);

  if (move.flag == MoveFlag::KingCastle) {
    const int rank = moved->color == Color::White ? 0 : 7;
    set_piece(make_square(7, rank), std::nullopt);
    set_piece(make_square(5, rank), Piece{moved->color, PieceType::Rook});
  } else if (move.flag == MoveFlag::QueenCastle) {
    const int rank = moved->color == Color::White ? 0 : 7;
    set_piece(make_square(0, rank), std::nullopt);
    set_piece(make_square(3, rank), Piece{moved->color, PieceType::Rook});
  }

  update_castling_rights(move, moved, captured, captured_square);
  en_passant_.reset();
  if (move.flag == MoveFlag::DoublePawnPush) {
    en_passant_ = move.from + (moved->color == Color::White ? 8 : -8);
  }

  halfmove_clock_ = (moved->type == PieceType::Pawn || captured.has_value()) ? 0 : halfmove_clock_ + 1;
  if (side_to_move_ == Color::Black) {
    ++fullmove_number_;
  }
  side_to_move_ = opposite(side_to_move_);
  xor_position_state();
  repetition_keys_.push_back(hash());
  return undo;
}

void Position::unmake_move(const UndoState &undo) {
  repetition_keys_.pop_back();
  xor_position_state();
  side_to_move_ = opposite(side_to_move_);
  castling_ = undo.castling;
  en_passant_ = undo.en_passant;
  halfmove_clock_ = undo.halfmove_clock;
  fullmove_number_ = undo.fullmove_number;

  set_piece(undo.move.to, std::nullopt);
  set_piece(undo.move.from, undo.moved_piece);
  if (undo.captured_piece.has_value()) {
    set_piece(undo.captured_square, undo.captured_piece);
  }

  if (undo.move.flag == MoveFlag::KingCastle) {
    const int rank = undo.moved_piece->color == Color::White ? 0 : 7;
    set_piece(make_square(5, rank), std::nullopt);
    set_piece(make_square(7, rank), Piece{undo.moved_piece->color, PieceType::Rook});
  } else if (undo.move.flag == MoveFlag::QueenCastle) {
    const int rank = undo.moved_piece->color == Color::White ? 0 : 7;
    set_piece(make_square(3, rank), std::nullopt);
    set_piece(make_square(0, rank), Piece{undo.moved_piece->color, PieceType::Rook});
  }
  xor_position_state();
  hash_ = undo.hash;
}

void Position::update_castling_rights(Move move, std::optional<Piece> moved,
                                      std::optional<Piece> captured, Square captured_square) {
  if (moved.has_value() && moved->type == PieceType::King) {
    if (moved->color == Color::White) {
      castling_.white_king_side = false;
      castling_.white_queen_side = false;
    } else {
      castling_.black_king_side = false;
      castling_.black_queen_side = false;
    }
  }

  if (moved.has_value() && moved->type == PieceType::Rook) {
    if (is_rook_home_square(move.from, Color::White, true)) {
      castling_.white_king_side = false;
    }
    if (is_rook_home_square(move.from, Color::White, false)) {
      castling_.white_queen_side = false;
    }
    if (is_rook_home_square(move.from, Color::Black, true)) {
      castling_.black_king_side = false;
    }
    if (is_rook_home_square(move.from, Color::Black, false)) {
      castling_.black_queen_side = false;
    }
  }

  if (captured.has_value() && captured->type == PieceType::Rook) {
    if (is_rook_home_square(captured_square, Color::White, true)) {
      castling_.white_king_side = false;
    }
    if (is_rook_home_square(captured_square, Color::White, false)) {
      castling_.white_queen_side = false;
    }
    if (is_rook_home_square(captured_square, Color::Black, true)) {
      castling_.black_king_side = false;
    }
    if (is_rook_home_square(captured_square, Color::Black, false)) {
      castling_.black_queen_side = false;
    }
  }
}

} // namespace atropos::board
