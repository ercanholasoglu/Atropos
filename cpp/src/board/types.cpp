#include "board/types.hpp"

#include <cctype>

namespace atropos::board {

char piece_to_fen(Piece piece) {
  char text = '?';
  switch (piece.type) {
  case PieceType::Pawn:
    text = 'p';
    break;
  case PieceType::Knight:
    text = 'n';
    break;
  case PieceType::Bishop:
    text = 'b';
    break;
  case PieceType::Rook:
    text = 'r';
    break;
  case PieceType::Queen:
    text = 'q';
    break;
  case PieceType::King:
    text = 'k';
    break;
  }
  if (piece.color == Color::White) {
    text = static_cast<char>(std::toupper(static_cast<unsigned char>(text)));
  }
  return text;
}

std::optional<Piece> piece_from_fen(char text) {
  const Color color = std::isupper(static_cast<unsigned char>(text)) != 0 ? Color::White : Color::Black;
  switch (static_cast<char>(std::tolower(static_cast<unsigned char>(text)))) {
  case 'p':
    return Piece{color, PieceType::Pawn};
  case 'n':
    return Piece{color, PieceType::Knight};
  case 'b':
    return Piece{color, PieceType::Bishop};
  case 'r':
    return Piece{color, PieceType::Rook};
  case 'q':
    return Piece{color, PieceType::Queen};
  case 'k':
    return Piece{color, PieceType::King};
  default:
    return std::nullopt;
  }
}

std::string square_to_string(Square square) {
  if (!is_valid_square(square)) {
    return "-";
  }
  std::string text;
  text.push_back(static_cast<char>('a' + file_of(square)));
  text.push_back(static_cast<char>('1' + rank_of(square)));
  return text;
}

std::optional<Square> square_from_string(std::string_view text) {
  if (text.size() != 2) {
    return std::nullopt;
  }
  const char file = text[0];
  const char rank = text[1];
  if (file < 'a' || file > 'h' || rank < '1' || rank > '8') {
    return std::nullopt;
  }
  return make_square(file - 'a', rank - '1');
}

std::string move_to_uci(Move move) {
  std::string text = square_to_string(move.from) + square_to_string(move.to);
  if (move.promotion.has_value()) {
    switch (*move.promotion) {
    case PieceType::Knight:
      text.push_back('n');
      break;
    case PieceType::Bishop:
      text.push_back('b');
      break;
    case PieceType::Rook:
      text.push_back('r');
      break;
    case PieceType::Queen:
      text.push_back('q');
      break;
    case PieceType::Pawn:
    case PieceType::King:
      break;
    }
  }
  return text;
}

} // namespace atropos::board
